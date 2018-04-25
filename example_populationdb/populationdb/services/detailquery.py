from pyxadapterlib.xutils import *
from pyxadapterlib.attachment import Attachment
from ..models.populationdb import *
import logging
log = logging.getLogger(__name__)

def serve(wrapper, header=None, attachments=[], context=None):
    # input: person code
    # output: detail information about a person, including photo
    error = None
    request = wrapper.find('request')
    if request is None:
        raise SoapFault('Server.Adapter.Error',
                        'Request parameter is missing')
    personcode = get_text(request, 'personcode')
    
    q = DBSession.query(Person)
    if personcode:
        q = q.filter(Person.personcode==personcode)
    else:
        error = 'Parameter is missing'

    if not error and q.count() == 0:
        error = 'No data match you query.'

    if error:
        res = E.response(E.error(error))
    else:
        p = q.first()
        item = E.person()
        item.append(E.personcode(p.personcode))
        item.append(E.givenname(p.givenname))
        item.append(E.surname(p.surname))
        item.append(E.full_address(p.full_address))
        item.append(E.doc_no(p.docno))
        item.append(E.status(p.status))
        res = E.response(item)
        attachments = list()
        if p.photo:
            att = Attachment(p.photo, use_gzip=False)
            att.filename = 'photo.jpg'
            content_id = att.gen_content_id()
            attachments = [att]
            item.append(E.photo('', href='cid:%s' % (content_id)))

    return E.Response(request, res), attachments

