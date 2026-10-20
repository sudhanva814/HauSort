import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import JSON_TYPE, utc_now
from app.models.enums import ComparisonStatus

if TYPE_CHECKING:
    from app.models.comparison_ad import ComparisonAd
    from app.models.user import User
    from app.models.user_preference import UserPreference


class Comparison(SQLModel, table=True):
    """Represents a comparison session evaluating multiple housing ads against criteria."""
    __tablename__ = "comparisons"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        description="Unique comparison session ID",
    )
    user_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        ondelete="SET NULL",
        description="Owner user ID if authenticated",
    )
    preference_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="user_preferences.id",
        index=True,
        ondelete="SET NULL",
        description="Source user preference profile ID if used",
    )
    name: Optional[str] = Field(
        default=None,
        max_length=150,
        description="Session name, e.g. 'Trier WG shortlist'",
    )
    status: str = Field(
        default=ComparisonStatus.DRAFT,
        max_length=20,
        description="Status: draft, processing, completed, failed",
    )
    criteria_snapshot: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON_TYPE, nullable=False),
        description="Immutable snapshot of the exact criteria used for this run",
    )
    scoring_version: str = Field(
        default="1.0.0",
        max_length=30,
        description="Version identifier of the scoring algorithm",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False,
        description="Comparison start timestamp (UTC)",
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Comparison completion timestamp (UTC)",
    )

    # Relationships
    user: Optional["User"] = Relationship(back_populates="comparisons")
    preference: Optional["UserPreference"] = Relationship(back_populates="comparisons")
    comparison_ads: List["ComparisonAd"] = Relationship(
        back_populates="comparison",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
