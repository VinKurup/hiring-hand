"""SQLite engine, schema creation, and the FastAPI session dependency."""

from typing import Iterator

from sqlmodel import SQLModel, Session, create_engine

DATABASE_URL = "sqlite:///resume_booster.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    """Create all tables. Importing db_models registers them on SQLModel.metadata."""
    import db_models  # noqa: F401  (registers tables)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
