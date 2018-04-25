from pyxadapterlib.xutils import *
from ..models.populationdb import *

import logging
log = logging.getLogger(__name__)

MAX_ITEMS = 20

def serve(wrapper, header=None, attachments=[], context=None):
    # input: search criteria (name, code)
    # output: list of persons matching search criteria
    
    error = None
    request = wrapper.find('request')
    if request is None:
        raise SoapFault('Server.Adapter.Error',
                        'Request parameter is missing')
    givenname = get_text(request, 'givenname')
    surname = get_text(request, 'surname')    
    personcode = get_text(request, 'personcode')
    max_results = get_int(request, 'max_results') or MAX_ITEMS
    
    q = DBSession.query(Person)
    if givenname:
        q = q.filter(Person.givenname.ilike(givenname))
    if surname:
        q = q.filter(Person.surname.ilike(surname))
    if personcode:
        q = q.filter(Person.personcode==personcode)

    if not personcode and not surname:
        error = 'Parameters are missing or invalid.'
    elif q.count() == 0:
        error = 'No data match you query. Use % instead of surname to get some demo data.'

    if error:
        res = E.response(E.error(error))
    else:
        q = q.limit(max_results)
        persons = E.persons()
        for p in q.all():
            item = _person(p)
            persons.append(item)
        res = E.response(persons)

    return E.Response(request, res), []

def _person(p):
    item = E.person()
    item.append(E.personcode(p.personcode))
    item.append(E.givenname(p.givenname))
    item.append(E.surname(p.surname))
    item.append(E.full_address(p.full_address))
    item.append(E.doc_no(p.docno))
    item.append(E.status(p.status))
    return item
