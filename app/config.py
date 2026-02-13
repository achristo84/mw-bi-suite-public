"""Centralized configuration from environment variables.

All configuration that varies between environments (local dev, CI, production)
is read from environment variables here. Import from this module instead of
reading os.environ directly in service code.
"""
import os
from functools import lru_cache


class Settings:
    """Application settings loaded from environment variables."""

    # GCP Configuration
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "")
    INSTANCE_CONNECTION_NAME: str = os.getenv("INSTANCE_CONNECTION_NAME", "")

    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "mw_bi_suite")
    DB_USER: str = os.getenv("DB_USER", "mw_app")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # API Keys (optional - can also come from Secret Manager)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # CORS
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(",")

    # Cloud Run URL (for self-referencing, optional)
    CLOUD_RUN_URL: str = os.getenv("CLOUD_RUN_URL", "http://localhost:8000")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
