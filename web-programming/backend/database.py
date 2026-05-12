"""Database engine and session dependency."""

from sqlmodel import create_engine, Session, SQLModel
from backend.config import DATABASE_URL as _RAW_URL

# Railway legacy scheme fix
DATABASE_URL = _RAW_URL.replace("postgres://", "postgresql://", 1) if _RAW_URL.startswith("postgres://") else _RAW_URL

_is_sqlite = DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    echo=_is_sqlite,
    pool_pre_ping=True,
    pool_recycle=300,
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
