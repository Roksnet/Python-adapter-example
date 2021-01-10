from pyxadapterlib.xutils import E
import logging
log = logging.getLogger(__name__)

def serve(wrapper, header=None, attachments=[], context=None):
    request = wrapper.find('request')    
    if request is None:
        raise SoapFault('Server.Adapter.Error',
                        'Request parameter is missing')
    name = request.text or 'world'
    res = E.response(f'Hello, {name}')
    return E.Response(request, res), []

