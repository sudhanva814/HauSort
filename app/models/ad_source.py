import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import utc_now
from app.models.enums import SourceStatus, SourceType

if TYPE_CHECKING:
    from app.models.housing_ad import HousingAd


class AdSource(SQLModel, table=True):
    """Tracks origin, raw inputs, and extraction attempts for housing ads."""
    __tablename__ = "ad_sources"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        description="Source ID",
    )
    housing_ad_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="housing_ads.id",
        index=True,
        ondelete="CASCADE",
        nullable=True,
        description="Associated housing ad ID",
    )
    source_type: str = Field(
        default=SourceType.URL,
        max_length=20,
        description="Submission method: url, pasted_text, manual",
    )
    source_url: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Original listing URL if applicable",
    )
    source_domain: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Website domain (e.g. wg-gesucht.de, immoscout24.de)",
    )
    raw_text: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Raw scraped or pasted text",
    )
    raw_content_hash: Optional[str] = Field(
        default=None,
        max_length=64,
        index=True,
        description="SHA-256 hash of raw input to detect duplicates",
    )
    scraped_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp of last successful fetch (UTC)",
    )
    last_attempt_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp of last extraction attempt (UTC)",
    )
    status: str = Field(
        default=SourceStatus.PENDING,
        max_length=20,
        description="Status: pending, processing, succeeded, failed",
    )
    error_message: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Extraction or scraping error details",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False,
        description="Record creation timestamp (UTC)",
    )

    # Relationships
    housing_ad: Optional["HousingAd"] = Relationship(back_populates="sources")
