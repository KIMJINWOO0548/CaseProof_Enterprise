"""DB initialization. SQLite for 1-process offline demonstrations only."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .models import Base

def make_engine(url: str):
    opts = {'connect_args': {'check_same_thread': False, 'timeout': 20}} if url.startswith('sqlite') else {}
    engine = create_engine(url, pool_pre_ping=True, **opts)
    if url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def _sqlite_fk(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.execute('PRAGMA busy_timeout=20000')
            cursor.close()
    return engine

def create_tables(engine):
    Base.metadata.create_all(engine)

def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
