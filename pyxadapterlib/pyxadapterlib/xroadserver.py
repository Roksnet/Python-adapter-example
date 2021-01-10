"""
X-road SOAP server
Author: Ahti Kelder

SOAP input message is received by adapter
which calls XroadServer.dispatch() here
which calls serve() at implementation module of a service.

For each service there must be an implementation module with function serve().

Function serve() must have parameters:
- input data - wrapper node from input message, typically contains element <request>
- header as a Xresult
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
    tree_to_xresult,
    make_log_day_path,
    )
from . import attachment

class XroadServer:
    "SOAP server"

    # turn off if you do not want logging individual messages into files
    # turn on and set adapter.log_dir if you want logging into files
    is_log_msg = True
    
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
   
    def dispatch(self, request, context=None, error_handler=None, header_handler=None):
        """Dispatch and run the service
        request - WebOb request, contains input message
        error_handler - function to be called in case of exceptions (params: exception, message)
        context - optional context object that will be accessible by service
        """
        started = datetime.now()
        http_body = xrheader = input_xml = output_xml = name = None
        http_headers = None
        is_log_msg = self.is_log_msg
        try:
            input_data = self._read_input(request)
            if not input_data:
                http_body = self._create_fault('Server.Adapter.Error',
                                               'No input message')
            else:
                # log
                self._log_msg('input', 'in.txt', input_data)

                # extract SOAP envelope and possible attachments
                input_xml, attachments = attachment.decode(input_data)

                # transform SOAP envelope text to XML object
                if isinstance(input_xml, str):
                    input_xml = input_xml.encode('utf-8')
                if context is None:
                    context = request
                # run service
                http_headers, http_body, output_xml, xrheader, name, is_log_msg = \
                    self._execute(input_xml, attachments, context, header_handler)                

        except SoapFault as e:
            output_xml = http_body = self._create_fault('Server.Adapter.Error',
                                                        e.faultstring)
        except Exception as e:
            if not error_handler:
                error_handler = _default_error_handler
            error_handler(e, 'Adapter error ')
            output_xml = http_body = self._create_fault('Server.Adapter.Error',
                                                        'Adapter server error')
        finally:
            if isinstance(input_xml, bytes):
                input_xml = input_xml.decode()
            self._log_call(xrheader,
                           input_xml,
                           output_xml,                          
                           input_data,
                           http_body,
                           started,
                           request)
            
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

        if is_log_msg:
            out_data = str(res)
            log.debug('OUTPUT:\n%s\n' % (out_data))
            self._log_msg(name, 'out.txt', out_data)
        return res

    def _execute(self, xml, attachments, context, header_handler):
        "Run service function"

        xrheader = None
        request = etree.XML(xml) 
        # get SOAP header and body
        header = request.find(NS._SOAP11+'Header')            
        body = request.find(NS._SOAP11+'Body')

        # get wrapper element (tag is same as service name)
        wrapper = body.getchildren()[0] 

        request_namespace, name = _split_tag(wrapper.tag)

        is_log_msg = self.is_log_msg
        if name == 'testSystem':
            # monitoring service initiated by our own security server
            request = None
            namespace = NS.XROAD4
            response = E.Response()
            attachments = []
            # we prefer not to log monitoring traffic
            is_log_msg = False
        elif name == 'allowedMethods':
            # local test only
            request = None
            namespace = NS.XROAD4
            response = self._allowedMethods()
            attachments = []
        else:
            # data services
            if header is None:
                xml = self._create_fault('Server.Adapter.Error', 'SOAP header is missing')
                return None, xml, xml, None, name, True                

            # turn header XML element into Xresult object
            xrheader = tree_to_xresult(header)
            if is_log_msg:
                log.debug('INPUT:\n%s\n' % xml)
                self._log_msg(name, 'in.xml', xml)

            protocol = xrheader.protocolVersion
            if protocol != '4.0':
                raise SoapFault('Server.Adapter.Error', f'Unsupported protocol version {protocol}')

            service = self._get_service(xrheader)

            namespace = self.namespace

            # in case we need to use header data for some purpose
            if header_handler is not None:
                header_handler(xrheader)
            
            # call the service
            response, attachments = service(wrapper, xrheader, attachments=attachments, context=context)

        # compose SOAP envelope
        # response will become wrapper element of the output message
        xml = self._create_response_envelope(header, response, name, namespace)

        if is_log_msg:
            self._log_msg(name, 'out.xml', xml)

        # compose response payload
        payload, http_headers, http_body = \
            attachment.encode_soap(xml, attachments, False)
        return http_headers, http_body, xml, xrheader, name, is_log_msg

    def _get_service(self, xrheader):
        "Get service function"
        # get full name of the service (we use it as index into service map)
        try:
            value = xrheader.service
            fullname = '%s.%s.%s' % (self.producer, value.serviceCode, value.serviceVersion)
        except KeyError:
            raise SoapFault('Server.Adapter.Error', 'X-road SOAP header is incorrect')

        # get service implementation 
        service = self.services.get(fullname)
        if not service:
            raise SoapFault('Server.Adapter.Error',
                            f'Adapter does not provide service {fullname}')
        return service
    
    def _create_response_envelope(self, header, response, name, namespace):
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
    
    def _allowedMethods(self):
        "For testing client against local SOAP server without X-road"
        response = E.response()
        for name in self.services.keys():
            response.append(E.service(name))
        return response

    def _read_input(self, request):
        "Read input message"
        input_data = ''

        # HTTP headers
        for key, value in request.headers.items():
            input_data += '%s: %s\r\n' % (key, value)
        input_data += '\r\n'
        input_data = input_data.encode('utf-8')
            
        # read input until the end of chunked encoding
        while True:
            try:
                ch = request.body_file_raw.read(1)
                if not ch:
                    break
                input_data += ch
            except OSError:
                break

        return input_data

    def _log_msg(self, method, ext, data):
        "Log input and output messages into files in log_dir"
        if self.log_dir:
            prefix = make_log_day_path(self.log_dir)
            fn = '%s.adapter.%s.%s' % (prefix, method, ext)
            with open(fn, isinstance(data, bytes) and 'wb' or 'w') as file:
                file.write(data)
            os.chmod(fn, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

    def _log_call(self, xrheader, input_xml, output_xml, input_data, output_data, started, request):
        "Overload for custom logging"
        pass

def _default_error_handler(exc, message):
    "Default handler for errors before responding with SoapFault"
    log.error(message + str(exc))
    traceback.print_exc()
    
def _split_tag(tag):
    "Extract namespace and tag name"
    m = re.match(r'{(.+)}(.+)', tag)
    return m.groups()

