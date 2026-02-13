"""Database connection and session management."""
import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import get_settings


def get_database_url() -> str:
    """Build database URL from environment variables.

    For local development, uses Cloud SQL Proxy on localhost.
    For Cloud Run, uses Unix socket connection.
    """
    # Check for explicit DATABASE_URL first
    if url := os.getenv("DATABASE_URL"):
        return url

    settings = get_settings()
    user = settings.DB_USER
    password = settings.DB_PASSWORD
    host = settings.DB_HOST
    port = settings.DB_PORT
    database = settings.DB_NAME

    # Cloud Run uses Unix socket via Cloud SQL connector
    instance_connection = settings.INSTANCE_CONNECTION_NAME
    if instance_connection:
        return f"postgresql://{user}:{password}@/{database}?host=/cloudsql/{instance_connection}"

    # Standard TCP connection (local dev with Cloud SQL Proxy)
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


@lru_cache
def get_engine():
    """Create SQLAlchemy engine (cached)."""
    return create_engine(
        get_database_url(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


def get_session() -> Session:
    """Create a new database session."""
    SessionLocal = sessionmaker(bind=get_engine())
    return SessionLocal()


def get_db():
    """Dependency for FastAPI routes that need a database session."""
    db = get_session()
    try:
        yield db
    finally:
        db.close()
