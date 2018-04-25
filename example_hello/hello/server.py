from pyramid.config import Configurator
from pyxadapterlib.xroadserver import XroadServer
from .services import helloservice

# SOAP server instance
srv = None

def register_services(settings):
    "Service registration for using by dispatcher"
    global srv
    namespace = "http://hello.x-road.eu/producer/"
    srv = XroadServer(settings, 'hello', namespace)
    # register services
    srv.register(helloservice)

def adapter(request):
    "SOAP server and service dispatcher"
    return srv.dispatch(request)
   
def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application to run a SOAP server.
    """
    config = Configurator(settings=settings)
    # declare static view to publish WSDL
    config.add_static_view('static', 'static', cache_max_age=3600)

    # register services
    register_services(settings)

    # declare adapter view for SOAP server
    config.add_route('adapter', '/adapter')
    config.add_view(adapter, route_name='adapter')
    
    return config.make_wsgi_app()
