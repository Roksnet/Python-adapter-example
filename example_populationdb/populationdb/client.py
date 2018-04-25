"X-road client example"
from datetime import datetime
from pyxadapterlib.xroadclient import (
    XroadClient,
    SoapFault,
    E,
    make_log_day_path,
)

class PopulationdbClient(XroadClient):
    """Client class for using services.
    For each service here is a method which composes input message,
    calls the method and returns response data.
    """
    producer = 'population'
    namespace = 'http://iw-demo-db.x-road.eu/producer/'
    
    def personquery(self, givenname, surname, personcode):
        # service parameters
        request = E.request(E.givenname(givenname),
                            E.surname(surname),
                            E.personcode(personcode),
                            E.max_results(10))

        # this becomes wrapper element
        params = E.Request(request)
        # define path to response elements which may occur multiple times
        # (should be parsed as a list)
        list_path = ['/response/persons/person',]
        # call the service
        res = self.call('personquery', params, list_path=list_path)
        # res is dict of response data
        return res

    def detailquery(self, personcode):
        # service parameters
        request = E.request(E.personcode(personcode))
        # this becomes wrapper element
        params = E.Request(request)
        # call the service
        res = self.call('detailquery', params)
        # res is dict of response data
        return res, self.response_attachments

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
        # populationdb settings for X-road protocol 4.0 (<service> header)
        'population.xroad.xRoadInstance': 'roksnet-dev',
        'population.xroad.memberClass': 'COM',
        'population.xroad.memberCode': '12998179',
        'population.xroad.subsystemCode': 'population',
        }
    userId = 'EE30101010007' # authenticated user's country code + personcode, replace with your data

    # Service client
    reg = PopulationdbClient(userId=userId, settings=settings)

    try:
        print('Call personquery...')
        res = reg.personquery(None, 'H%', None)
        pprint.pprint(res)

        try:
            # find first person in response list
            first_person = res['response']['persons']['person'][0]
        except:
            print('No persons found')
        else:
            personcode = first_person['personcode']
            print('Call detailquery for %s...' % personcode)
            res, attachments = reg.detailquery(personcode)
            pprint.pprint(res)
            for att in attachments:
                # save attachment
                prefix = make_log_day_path(settings['xroad.log_dir'])
                fn = '%s.%s' % (prefix, att.filename)
                with open(fn, 'wb') as file:
                    file.write(att.data)
                    print('Attachment saved as %s' % fn)
            
    except SoapFault as e:
        print(reg.xml_response)
        print(e.faultstring)
