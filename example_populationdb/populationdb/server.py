import traceback
import logging
log = logging.getLogger(__name__)
from sqlalchemy import engine_from_config
from .models import (
    DBSession,
    Base,
    )
from pyramid.config import Configurator
from pyxadapterlib.xroadserver import XroadServer

from .services import (
    personquery,
    detailquery,
    photoupdate,
    )

# SOAP server instance
srv = None

def register_services(settings):
    "Service registration for using by dispatcher"
    global srv
    namespace = "http://population.x-road.eu/producer/"
    srv = XroadServer(settings, 'population', namespace)
    # register services
    srv.register(personquery)
    srv.register(detailquery)
    srv.register(photoupdate)   

def adapter(request):
    "SOAP server and service dispatcher"
    def _error_handler(exc, msg):
        DBSession.rollback()
        DBSession.remove()
        log.error(msg + '\n' + traceback.format_exc())
        
    return srv.dispatch(request, _error_handler)

def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application to run a SOAP server.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    
    config = Configurator(settings=settings)
    # declare static view to publish WSDL
    config.add_static_view('static', 'static', cache_max_age=3600)

    # register services
    register_services(settings)

    # declare adapter view for SOAP server
    config.add_route('adapter', '/adapter')
    config.add_view(adapter, route_name='adapter')
    
    return config.make_wsgi_app()
