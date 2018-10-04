"""
Base class of a X-road SOAP client
Author: Ahti Kelder
"""

import string
from random import Random
import os
import httplib2
import socket
from datetime import datetime
import re
import stat
from lxml import etree
from lxml.builder import ElementMaker

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

# X-road protocol version
XVER4 = 4
XVER3 = 3

class XroadClient(object):
    security_server = None # security server IP (may be with :port)
    security_server_uri = '/cgi-bin/consumer_proxy' 
    userId = None # user ID value in SOAP header
    handler = None # view handler
    producer = None # data provider ID (used in configuration)
    namespace = None # data provider's namespace
    settings = {} # configuration settings
    xver = XVER4 # X-road protocol version

    _consumer = None # X-road 3.1 <consumer> header value
    _producer = None # X-road 3.1 <producer> header value
    _caller = {} # X-road 4.0 <client> header values
    _service = {} # X-road 4.0 <service> header values
    xml_response = None # response XML
    
    def __init__(self, handler=None, security_server=None, userId=None, settings=None):
        """
        Parameters:
        handler - view handler (to obtain settings from)
        security_server - HOST or HOST:PORT
        userId - user ID with country prefix (ISO2)
        settings - config settings dict; if missing, will be obtained from handler
        """
        if handler:
            self.handler = handler
            if not settings:
                settings = handler.request.registry.settings
            
        if settings:
            self.settings = settings

            db = self.producer

            self._caller = self._get_client_data(db)
            self._service = self._get_server_data(db)
            self._consumer = self._get_setting('consumer', db)
            self._producer = self._get_setting('producer', db) or db           
            
            self.security_server = self._get_setting('security_server', db)
            self.security_server_uri = self._get_setting('security_server_uri', db) or \
                                       self.security_server_uri

            self.key = self._get_setting('key', db)
            self.cert = self._get_setting('cert', db)
            
            self.log_dir = self._get_setting('log_dir', db)
        else:
            self.security_server = security_server

        self.userId = userId

    def _get_client_data(self, db):
        # consumer's data in header
        return dict(
            xRoadInstance = self._get_setting('client.xRoadInstance', db),
            memberClass = self._get_setting('client.memberClass', db),
            memberCode = self._get_setting('client.memberCode', db),
            subsystemCode = self._get_setting('client.subsystemCode', db),
            )
    
    def _get_server_data(self, db):
        # provider's data in header
        return dict(
            xRoadInstance = self._get_db_setting('xRoadInstance', db) or self._caller['xRoadInstance'],
            memberClass = self._get_db_setting('memberClass', db),
            memberCode = self._get_db_setting('memberCode', db),
            subsystemCode = self._get_db_setting('subsystemCode', db),
            )
        
    def _get_db_setting(self, key, db):
        return self.settings.get('%s.xroad.%s' % (db, key))

    def _get_setting(self, key, db):
        return self._get_db_setting(key, db) or self.settings.get('xroad.%s' % key)

    def allowedMethods(self):
        "Ask list of permitted services"
        items = []
        if self.xver == XVER3:
            list_path = ['/response/service']
            res = self.call('allowedMethods', E.allowedMethods(), None, list_path=list_path)
            items = res['response'].get('service') or []
        elif self.xver == XVER4:
            list_path = ['/response/service']
            res = self.call('allowedMethods', E.allowedMethods(), 'v1', list_path=list_path)
            items = res['response'].get('service') or []
        return items
    
    def call(self, service_name, params, service_version='v1', attachments=[], list_path=[]):
        """
        Call X-road service
        - service_name - short name of service
        - params - input parameters as XML object
        """

        self.xml_response = ''
        self.response_attachments = []        

        if service_name == 'allowedMethods':
            # meta service belongs to X-road namespace
            ns = self.xver == XVER3 and NS.XROAD3 or NS.XROAD4
        else:
            # data service belongs to data provider's own namespace
            ns = self.namespace

        # generate SOAP envelope
        xml_request = self._gen_envelope(service_name, params, service_version, ns)

        try:
            # execute call
            xml_response = self.send_xml(service_name, xml_request, attachments, ns)

            # create XML object for response envelope and find Body element
            root = etree.fromstring(xml_response.encode('utf-8')) 
            body = root.find(NS._SOAPENV+'Body')
            if body is not None:
                # detect SOAP fault message
                response = body.find('*')
                if response.tag == NS._SOAPENV+'Fault':
                    try:
                        detail = response.find('detail').find('message').text
                    except:
                        detail = None
                    raise SoapFault(response.find('faultcode').text,
                                    response.find('faultstring').text,
                                    detail)

                if response is not None:
                    # convert XML to dict
                    return tree_to_dict(response, '', list_path)
        
        except SoapFault as e:
            msg = 'X-road SOAP fault'
            buf = '%s (%s, %s)' % (msg, self.producer, service_name) +\
                '\n' + e.faultstring +\
                '\nSecurity server: %s' % (self.security_server) +\
                '\n\n' + self.xml_response +\
                '\n\nInput:\n' + xml_request

            log.error(buf)
            raise SoapFault(None, 'X-road service failed (%s: %s)' % (self.producer, e.faultstring))
        
        except httplib2.ServerNotFoundError as e:
            msg = 'X-road server not found'
            buf = '%s\nSecurity server: %s' % (msg, self.security_server)
            buf += '\n' + str(e)
            log.error(buf)
            raise SoapFault(None, msg)

        except socket.error as e:
            msg = 'No access to X-road'
            buf = '%s (socket.error)\nSecurity server: %s' % (msg, self.security_server)
            log.error(buf)
            raise SoapFault(None, msg)

    def send_xml(self, service_name, xml, attachments=[], namespace=None):
        "Send input message to security server and receive output message"

        args = {}
        prot = 'http'

        # SOAP server URL (at security server)
        url = '%s://%s%s' % (prot, self.security_server, self.security_server_uri)
        
        self.xml_request = xml
        self._trace_msg(service_name, 'in.xml', xml)

        # compose HTTP message
        payload, headers, body = attachment.encode_soap(self.xml_request, attachments)

        # send message
        response = self._send_http(url, body, headers)

        # decode envelope and attachments
        self.xml_response, self.response_attachments = attachment.decode(response)
        self._trace_msg(service_name, 'out.xml', self.xml_response)
        #log.debug('REQUEST:\n%s\nRESPONSE:\n%s\n' % (self.xml_request, self.xml_response))

        return self.xml_response

    def _send_http(self, url, xml, headers):
        "Send message over HTTP"
        kwargs = {}
        response, response_body = httplib2.Http().request(
            url, "POST", body=xml, headers=headers, **kwargs)

        # reconstruct whole message for MIME parsing later
        buf = ''
        for key, value in response.items():
            buf += '%s: %s\r\n' % (key, value)

        response = buf + '\r\n' + response_body.decode('utf-8')
        return response

    def _gen_envelope(self, service_name, params, service_version, namespace):
        "Compose SOAP envelope"
        # params is SOAP doc/literal wrapper element and must be named by name of the service
        params.tag = '{%s}%s' % (namespace, service_name) 
        nsmap = {'soap': NS.SOAP11,
                 'soapenc': NS.SOAPENC,
                 'xsi': NS.XSI,
                 'xsd': NS.XSD,
                 'a': namespace
                 }
        if self.xver == XVER3:
            nsmap['xrd'] = NS.XROAD3
        else:
            nsmap['xrd'] = NS.XROAD4
            nsmap['id'] = NS.XROAD4ID
            
        e = ElementMaker(namespace=NS.SOAP11, nsmap=nsmap)
        header = self._gen_header(service_name, service_version)
        envelope = e.Envelope(header, e.Body(params))
        return outer_xml(envelope, True)

    def _gen_header(self, service_name, service_version): 
        "Compose SOAP header"
        if self.xver == XVER3:
            soap = ElementMaker(namespace=NS.SOAP11)
            xrd = ElementMaker(namespace=NS.XROAD3)
            service = '%s.%s.%s' % (self._producer, service_name, service_version)
            header = soap.Header(xrd.consumer(self._consumer),
                                 xrd.producer(self._producer),
                                 xrd.service(service),
                                 xrd.id(self._gen_nonce()),
                                 xrd.userId(self.userId)
                                 )

        elif self.xver == XVER4:
            soap = ElementMaker(namespace=NS.SOAP11)
            xrd = ElementMaker(namespace=NS.XROAD4)
            xid = ElementMaker(namespace=NS.XROAD4ID)

            c = self._caller
            client = xrd.client(xid.xRoadInstance(c['xRoadInstance']),
                                xid.memberClass(c['memberClass']),
                                xid.memberCode(c['memberCode']),
                                xid.subsystemCode(c['subsystemCode']))
            client.set('{%s}objectType' % NS.XROAD4ID, 'SUBSYSTEM')
            
            s = self._service
            service = xrd.service(xid.xRoadInstance(s['xRoadInstance']),
                                  xid.memberClass(s['memberClass']),
                                  xid.memberCode(s['memberCode']),
                                  xid.subsystemCode(s['subsystemCode']),
                                  xid.serviceCode(service_name),
                                  xid.serviceVersion(service_version))
            service.set('{%s}objectType' % NS.XROAD4ID, 'SERVICE')

            header = soap.Header(client,
                                 service,
                                 xrd.userId(self.userId),
                                 xrd.id(self._gen_nonce()),
                                 xrd.protocolVersion('4.0'))

        return header
        
    def _gen_nonce(self):
        "Generate unique id for service call"
        return ''.join(Random().sample(string.ascii_letters+string.digits, 32))
   
    def _trace_msg(self, method, ext, data):
        "Log input and output messages"
        if self.log_dir:
            prefix = make_log_day_path(self.log_dir)
            fn = '%s.%s.%s.%s' % (prefix, self.producer, method, ext)
            with open(fn, 'w') as file:
                file.write(data)
            os.chmod(fn, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

