from sqlalchemy import (
    Column,
    Index,
    Integer,
    Text,
    String,
    Date,
    DateTime,
    Float,
    Boolean,
    LargeBinary,
    ForeignKey,
    ForeignKeyConstraint,
    DefaultClause,
    event,
    and_,
    or_,
    MetaData,
    )

from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    relationship,
    backref,
    mapper,
    )

from zope.sqlalchemy import ZopeTransactionExtension
import transaction

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()

