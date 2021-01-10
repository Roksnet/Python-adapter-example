"X-road client example"
from pyxadapterlib.xroadclient import XroadClient, SoapFault, E

class HelloClient(XroadClient):
    """Client class for using services.
    For each service here is a method which composes input message,
    calls the method and returns response data.
    """
    producer = 'hello'
    namespace = 'http://hello.x-road.eu/producer/'
    
    def helloservice(self, name):
        # service parameters
        request = E.request(name)
        # this becomes wrapper element
        params = E.Request(request)
        # call the service
        res = self.call('helloservice', params)
        # res is dict of response data
        return res

if __name__ == '__main__':
    import pprint
    import logging
    logging.basicConfig(level=logging.DEBUG)

    # Settings to identify service consumer and provider etc
    settings = {
        # values when testing with pserve server at localhost
        'xroad.security_server': 'localhost:6543',
        'xroad.security_server_uri': '/adapter',

        # values when testing with Apache server at localhost
        #'xroad.security_server': 'localhost',
        #'xroad.security_server_uri': '/populationdb/adapter',

        # values when using with real X-road
        #'xroad.security_server': 'YOUR SECURITY SERVER IP',
        #'xroad.security_server_uri': '/cgi-bin/consumer_proxy',

        # directory where to log input and output messages
        'xroad.log_dir': 'tmp',
        # X-road protocol 4.0 <client> header values as xRoadInstance/memberClass/memberCode/subsystemCode
        'xroad.client': 'roksnet-dev/COM/12998179/roksnet-consumer',
        # hello settings for X-road protocol 4.0 <service> header as xRoadInstance/memberClass/memberCode/subsystemCode
        'xroad.server.hello': 'roksnet-dev/COM/12998179/hello',
        }
    userId = 'EE30101010007' # authenticated user's country code + person code

    # Service client
    reg = HelloClient(userId=userId, settings=settings)

    try:
        # call helloservice service
        res = reg.helloservice('World')
        pprint.pprint(res)

    except SoapFault as e:
        print(e.faultstring)
