from datetime import datetime, timezone
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# Use Postgres JSONB when running on PostgreSQL, fallback to standard JSON on SQLite
JSON_TYPE = JSONB().with_variant(JSON, "sqlite")


def utc_now() -> datetime:
    """Returns the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)
