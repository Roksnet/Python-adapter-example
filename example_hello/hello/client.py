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
        # global settings for X-road protocol 4.0 (<client> header):
        'xroad.client.xRoadInstance': 'roksnet-dev',
        'xroad.client.memberClass': 'COM',
        'xroad.client.memberCode': '12998179',
        'xroad.client.subsystemCode': 'roksnet-consumer',
        # hello settings for X-road protocol 4.0 (<service> header)
        'hello.xroad.xRoadInstance': 'roksnet-dev',
        'hello.xroad.memberClass': 'COM',
        'hello.xroad.memberCode': '12998179',
        'hello.xroad.subsystemCode': 'hello',
        }
    userId = 'EE30101010007' # authenticated user's country code + personcode

    # Service client
    reg = HelloClient(userId=userId, settings=settings)

    try:
        # call helloservice service
        res = reg.helloservice('Jaan')
        pprint.pprint(res)

    except SoapFault as e:
        print(e.faultstring)
