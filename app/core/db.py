from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _normalize_database_url(url: str) -> str:
    """Prefer SQLAlchemy's psycopg (v3) driver for PostgreSQL URLs.

    Render/Supabase commonly expose a plain ``postgresql://`` URL. SQLAlchemy
    otherwise defaults that URL to the legacy psycopg2 dialect, which is not
    installed in this project. Normalizing here keeps local and hosted URLs
    interchangeable and avoids provider-specific manual edits.
    """
    if url.startswith('postgres://'):
        return 'postgresql+psycopg://' + url[len('postgres://'):]
    if url.startswith('postgresql://'):
        return 'postgresql+psycopg://' + url[len('postgresql://'):]
    if url.startswith('postgresql+psycopg2://'):
        return 'postgresql+psycopg://' + url[len('postgresql+psycopg2://'):]
    return url


database_url = _normalize_database_url(settings.database_url)
connect_args = {'check_same_thread': False} if database_url.startswith('sqlite') else {}
engine = create_engine(database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def prepare_database() -> None:
    Base.metadata.create_all(bind=engine)
    # Small, deterministic SQLite migrations for databases carried forward from V6.x.
    if settings.database_url.startswith('sqlite'):
        inspector = inspect(engine)
        columns = {c['name'] for c in inspector.get_columns('transfers')}
        with engine.begin() as conn:
            if 'match_id' not in columns:
                conn.execute(text('ALTER TABLE transfers ADD COLUMN match_id INTEGER'))
            if 'need_id' not in columns:
                conn.execute(text('ALTER TABLE transfers ADD COLUMN need_id INTEGER'))
            if 'driver_accepted_at' not in columns:
                conn.execute(text('ALTER TABLE transfers ADD COLUMN driver_accepted_at DATETIME'))
