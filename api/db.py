from __future__ import annotations
from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
import os

_IS_SQLITE = "sqlite" in DATABASE_URL
_IS_MEMORY_SQLITE = _IS_SQLITE and ":memory:" in DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30} if _IS_SQLITE else {},
    poolclass=NullPool if (_IS_SQLITE and not _IS_MEMORY_SQLITE) else None,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if _IS_SQLITE:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def reset_database():
    from models import Base
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def init_db():
    from models import Base
    if os.getenv("RESET_DB", "").strip().lower() in ("true", "1", "yes"):
        reset_database()
    else:
        Base.metadata.create_all(bind=engine)
    from services.card_draw import seed_cards
    db = SessionLocal()
    try:
        seed_cards(db)
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
