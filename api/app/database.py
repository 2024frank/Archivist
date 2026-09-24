from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


database_url = get_settings().database_url
if database_url == "sqlite:///:memory:":
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def run_migrations() -> None:
    """Idempotent schema updates for deployments created before 'completed' existed."""
    if engine.dialect.name != "postgresql":
        return
    statements = (
        "ALTER TABLE videos ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ",
        "ALTER TABLE videos DROP CONSTRAINT IF EXISTS videos_status_check",
        "ALTER TABLE videos ADD CONSTRAINT videos_status_check "
        "CHECK (status IN ('uploading', 'ready', 'failed', 'completed'))",
    )
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
