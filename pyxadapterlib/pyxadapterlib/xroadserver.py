"""
X-road SOAP server
Author: Ahti Kelder

SOAP input message is received by adapter
which calls XroadServer.dispatch() here
which calls serve() at implementation module of a service.

For each service there must be an implementation module with function serve().

Function serve() must have parameters:
- input data - wrapper node from input message, typically contains element <request>
- header as a dict
- list of attachments of the input message
- context object

Function serve() must return tuple of:
- output data - response wrapper node, typically contains elements <request> and <response>.
  Wrapper element does not need to have correct tag/namespace as it will be fixed by server.
- list of attachments to use in output message

In case of unexpected errors serve() may raise SoapFault(faultcode, faultstring)
"""

import re
import os
import stat
from datetime import datetime
from pyramid.response import Response
from lxml import etree
from lxml.builder import ElementMaker
from lxml.builder import E
import traceback
import logging
log = logging.getLogger(__name__)

from .xutils import (
    NS,
    E,
    SoapFault,
    get_text,
    get_int,
    get_boolean,
    outer_xml,
    tree_to_dict,
    make_log_day_path,
    )
from . import attachment

# X-road protocol version 4.0
XVER4 = 4

# X-road protocol version 3.1
XVER3 = 3

class XroadServer(object):
    "SOAP server"
    
    def __init__(self, settings, producer, namespace):
        self.settings = settings
        self.producer = producer
        self.namespace = namespace

        # optional directory for tracing input and output messages
        self.log_dir = settings.get('adapter.log_dir')

        # service map
        self.services = {}
        
    def register(self, service, name=None, version='v1'):
        """
        Service registration (build the service map)
        - service - python module which has function serve()
        - version - version of a service         
        """
        if not name:
            name = service.__name__.split('.')[-1]
        full_name = '%s.%s.%s' % (self.producer, name, version)
        self.services[full_name] = service.serve
        
    def dispatch(self, request, error_handler=None, context=None, reuse=None):
        """Dispatch and run the service
        request - WebOb request, contains input message
        error_handler - function to be called in case of exceptions (params: exception, message)
        context - optional context object that will be accessible by service
        reuse - for debugging: 1 - save input message; 2 - reuse saved input message
        """

        can_log = True # do we need to log the message
        http_headers = None
        name = None
        try:
            data = request.body
            if not data:
                # in case of chunked encoding
                data = b''
                while True:
                    try:
                        data += request.body_file_raw.read(1)
                    except OSError:
                        break
            if reuse:
                data = self._test_reuse_input(reuse, data)

            if not data:
                http_body = self._create_fault('Server.Adapter.Error',
                                               'No input message')
            else:
                # log
                self._trace_msg('input', 'in.txt', data)

                # extract SOAP envelope and possible attachments
                xml, attachments = attachment.decode(data)

                # transform SOAP envelope text to XML object
                if isinstance(xml, str):
                   xml = xml.encode('utf-8')
                request = etree.XML(xml) 

                # get SOAP header and body
                header = request.find(NS._SOAP11+'Header')            
                body = request.find(NS._SOAP11+'Body')

                # get wrapper element (tag is same as service name)
                wrapper = body.getchildren()[0] 

                request_namespace, name = _split_tag(wrapper.tag)
                if name == 'testSystem':
                    # we prefer not to log monitoring traffic
                    can_log = False

                if can_log:
                    log.debug('INPUT:\n%s\n' % xml)
                    self._trace_msg(name, 'in.xml', xml)

                if context is None:
                    context = request
                # run service
                http_headers, http_body = self._execute(header, wrapper, attachments, context, request_namespace, name, can_log)

        except SoapFault as e:
            http_body = self._create_fault('Server.Adapter.Error',
                                           e.faultstring)

        except Exception as e:
            if not error_handler:
                error_handler = _default_error_handler
            error_handler(e, 'Adapter error ')
            http_body = self._create_fault('Server.Adapter.Error',
                                           'Adapter server error')

        if not http_headers:
            http_headers = {'Content-Type': 'text/xml',
                            }

        if 'Content-Length' in http_headers:
            # remove header as pyramid framework will add it later
            http_headers.pop('Content-Length') 
        ctype = http_headers.pop('Content-Type') # text/xml or multipart/related or application/xop+xml
        res = Response(http_body, content_type=ctype, charset='UTF-8')

        for key, value in http_headers.items():
            res.headers.add(key, value)

        if can_log:
            out_data = str(res)
            log.debug('OUTPUT:\n%s\n' % (out_data))
            self._trace_msg(name, 'out.txt', out_data)
        return res

    def _execute(self, header, params, attachments, context, request_namespace, name, can_log):
        "Run service function"

        if name == 'testSystem':
            # monitoring service initiated by our own security server
            request = None
            xver = XVER3
            namespace = NS.XROAD3
            response = E.Response()
            attachments = []
        elif name == 'listMethods' or name == 'allowedMethods':
            # meta services initiated by our own security server (protocol 3.1)
            request = None
            xver = XVER3
            namespace = NS.XROAD3
            response = self._listMethods()
            attachments = []
        else:
            # data services
            if header is None:
                xml = self._create_fault('Server.Adapter.Error', 'SOAP header is missing')
                return None, xml                

            # turn header XML element into dict
            header_dict = tree_to_dict(header)
            protocol = header_dict.get('protocolVersion')

            # find service full name (we use it as index into service map)
            try:
                if protocol == '4.0':
                    xver = XVER4
                    value = header_dict['service']
                    fullname = '%s.%s.%s' % (self.producer, value['serviceCode'], value['serviceVersion'])
                else:
                    xver = XVER3
                    fullname = header_dict['service']
            except KeyError:
                raise SoapFault('Server.Adapter.Error',
                                'X-road SOAP header is incorrect')
              
            # get service implementation 
            service = self.services.get(fullname)
            if not service:
                raise SoapFault('Server.Adapter.Error',
                                'Adapter does not provide service %s' % (fullname))

            namespace = self.namespace
            # call the service
            response, attachments = service(params, header_dict, attachments=attachments, context=context)

        # compose SOAP envelope
        # response will become wrapper element of the output message
        xml = self._create_response_envelope(header, response, name, namespace, xver)

        if can_log:
            self._trace_msg(name, 'out.xml', xml)

        # compose response payload
        payload, http_headers, http_body = \
            attachment.encode_soap(xml, attachments, False)
        return http_headers, http_body
    
    def _create_response_envelope(self, header, response, name, namespace, xver):
        "Compose response envelope"
        # response is wrapper element of the output message
        response.tag = '{%s}%sResponse' % (namespace, name)
        nsmap = {'soap': NS.SOAP11,
                 'soapenc': NS.SOAPENC,
                 'xsi': NS.XSI,
                 'xsd': NS.XSD,
                 'a': namespace
                 }
        e = ElementMaker(namespace=NS.SOAP11, nsmap=nsmap)
        envelope = e.Envelope()
        if header is not None:
            envelope.append(header)
        envelope.append(e.Body(response))
        return outer_xml(envelope, True)
    
    def _create_fault(self, faultcode, faultstring):
        "Compose SOAP fault message"
        nsmap = {'soap': NS.SOAP11,
                 'soapenc': NS.SOAPENC,
                 'xsi': NS.XSI,
                 'xsd': NS.XSD,
                 }
        e = ElementMaker(namespace=NS.SOAP11, nsmap=nsmap)
        envelope = e.Envelope(
            e.Body(
                e.Fault(
                    E.faultcode(faultcode),
                    E.faultstring(faultstring)
                    )
                )
            )
        return outer_xml(envelope, True)
    
    def _listMethods(self):
        "Implementation of meta-service listMethods (X-road protocol 3.1)"
        response = E.response()
        for name in self.services.keys():
            response.append(E.service(name))
        return E.Response(response)

    def _test_reuse_input(self, reuse, body):
        """For debugging purposes:
        - if reuse == 2: handle last posted input again
        - if reuse == 1: save input message for using later
        """
        
        fn_last_input = '/tmp/test.input.xml'
        if reuse == 2:
            # read  
            f = open(fn_last_input, 'rb')
            body = f.read()
            f.close()
        elif reuse == 1 and body:
            # save
            f = open(fn_last_input, 'wb')
            f.write(body)
            f.close()
        return body      
  
    def _trace_msg(self, method, ext, data):
        "Log input and output messages into files in log_dir"
        if self.log_dir:
            prefix = make_log_day_path(self.log_dir)
            fn = '%s.adapter.%s.%s' % (prefix, method, ext)
            with open(fn, isinstance(data, bytes) and 'wb' or 'w') as file:
                file.write(data)
            os.chmod(fn, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

def _default_error_handler(exc, message):
    log.error(message + str(exc))
    traceback.print_exc()
    
def _split_tag(tag):
    "Extract namespace and tag name"
    m = re.match(r'{(.+)}(.+)', tag)
    return m.groups()

