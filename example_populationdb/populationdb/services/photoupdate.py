from pyxadapterlib.xutils import *
from pyxadapterlib.attachment import Attachment
from ..models.populationdb import *
import logging
log = logging.getLogger(__name__)

def serve(wrapper, header=None, attachments=[], context=None):
    # input: person code and person's photo (to be saved in database)
    # output: message 
    
    error = message = None
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
        error = 'Person not found.'
    elif len(attachments) == 0:
        error = 'Photo missing'
    else:
        p = q.first()
        att = attachments[0]
        p.photo = att.data
        transaction.commit()
        message = 'File saved successfully'

    res = E.response(E.message(error or message))
    attachments = []
    return E.Response(res), attachments

