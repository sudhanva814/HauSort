from typing import Generator
from sqlmodel import Session, SQLModel, create_engine

import app.models  # Ensures all models are registered in SQLModel.metadata
from app.core.config import settings

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)


def init_db() -> None:
    """Creates database tables based on registered SQLModel metadata."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Dependency for providing database sessions to FastAPI routes."""
    with Session(engine) as session:
        yield session
