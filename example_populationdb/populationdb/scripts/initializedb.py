import os
import sys
import transaction
from datetime import date
from sqlalchemy import engine_from_config

from pyramid.paster import (
    get_appsettings,
    setup_logging,
    )

from pyramid.scripts.common import parse_vars

def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri> [var=value]\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def main(argv=sys.argv):
    if len(argv) < 2:
        usage(argv)
    config_uri = argv[1]
    options = parse_vars(argv[2:])
    setup_logging(config_uri)
    settings = get_appsettings(config_uri, options=options)
    engine = engine_from_config(settings, 'sqlalchemy.')

    init_population(engine) # model for population and passport

def init_population(engine):
    from ..models.populationdb import (
        DBSession,
        ABase,
        Person,
        Document,
    )
    DBSession.configure(bind=engine)
    ABase.metadata.create_all(engine)

    path = os.path.dirname(os.path.realpath(__file__))
    photo = open(os.path.join(path, 'init_photo.jpg'), 'rb').read()
    signature = open(os.path.join(path, 'init_signature.jpg'), 'rb').read()
    
    item = Person(givenname='EDMUND',
                  surname='HACTENUS',
                  personcode='37001196628',
                  full_address='JÄRVA MAAKOND, PAIDE LINN, RISTMIKU TN 25A',
                  docno='29342429',
                  status='E',
                  birthdate=date(1970,1,19),
                  photo=photo,
                  signature=signature,
                  documents=[Document(doc_type=1,
                                      doc_no='100200',
                                      valid_from=date(2011,12,14),
                                      valid_until=date(2015,12,14)),
                             Document(doc_type=1,
                                      doc_no='200300',
                                      valid_from=date(2015,12,10),
                                      valid_until=date(2029,12,10)),
                             ],
                  )
    DBSession.add(item)
    item = Person(givenname='PILLE',
                  surname='HUQUAESTUM',
                  personcode='45803029574',
                  birthdate=date(1958,3,2),
                  full_address='TARTU MAAKOND, TARTU LINN, KARUKÜLA TEE 14',
                  docno='29342429',
                  status='E',
                  photo=photo,
                  signature=signature,
                  documents=[Document(doc_type=1,
                                      doc_no='100100',
                                      valid_from=date(2012,2,4),
                                      valid_until=date(2025,2,4)),
                             Document(doc_type=2,
                                      doc_no='300100',
                                      valid_from=date(2012,2,5),
                                      valid_until=date(2025,2,5)),
                             ],
                  )
    DBSession.add(item)    
    transaction.commit()
