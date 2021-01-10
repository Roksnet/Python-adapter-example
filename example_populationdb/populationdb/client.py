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
        res = self.call('personquery', params, list_path)
        # res is Xresult object containing response data
        return res

    def detailquery(self, personcode):
        # service parameters
        request = E.request(E.personcode(personcode))
        # this becomes wrapper element
        params = E.Request(request)
        # call the service
        res = self.call('detailquery', params)
        # res is Xresult object containing response data        
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
        # settings for X-road protocol 4.0 <client> header as xRoadInstance/memberClass/memberCode/subsystemCode
        'xroad.client': 'roksnet-dev/COM/12998179/roksnet-consumer',
        # populationdb settings for X-road protocol 4.0 <service> header as xRoadInstance/memberClass/memberCode/subsystemCode
        'xroad.server.population': 'roksnet-dev/COM/12998179/population',
        }
    userId = 'EE30101010007' # authenticated user's country code + person code, REPLACE WITH YOUR DATA ABOUT AUTHENTICATED USER!

    # Service client
    reg = PopulationdbClient(userId=userId, settings=settings)

    try:
        # Call X-road service to find person code
        print('Call personquery...')
        res = reg.personquery(None, 'H%', None)
        pprint.pprint(res)
        persons = res.find('response/persons/person')
        try:
            # find first person in response list
            first_person = persons[0]
        except:
            print('No persons found')
        else:
            personcode = first_person['personcode']

            # Call X-road service to get details about given person
            print('Call detailquery for %s...' % personcode)
            res, attachments = reg.detailquery(personcode)
            pprint.pprint(res)
            for att in attachments:
                # save attachment somewhere, for simplicity we will use log directory 
                prefix = make_log_day_path(settings['xroad.log_dir'])
                fn = '%s.%s' % (prefix, att.filename)
                with open(fn, 'wb') as file:
                    file.write(att.data)
                    print('Attachment saved as %s' % fn)
            
    except SoapFault as e:
        print(reg.xml_response)
        print(e.faultstring)
