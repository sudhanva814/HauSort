import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, List, Optional
from sqlalchemy import CheckConstraint, Column, DateTime, Text, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import JSON_TYPE, utc_now

if TYPE_CHECKING:
    from app.models.comparison import Comparison
    from app.models.comparison_score_detail import ComparisonScoreDetail
    from app.models.housing_ad import HousingAd


class ComparisonAd(SQLModel, table=True):
    """Join table connecting comparisons to housing ads with scores, ranks, and explanations."""
    __tablename__ = "comparison_ads"
    __table_args__ = (
        UniqueConstraint(
            "comparison_id",
            "housing_ad_id",
            name="uq_comparison_ads_comparison_housing_ad",
        ),
        CheckConstraint(
            "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 100)",
            name="chk_comp_ad_score_range",
        ),
        CheckConstraint(
            "rank IS NULL OR rank >= 1",
            name="chk_comp_ad_rank_positive",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        description="Result entry ID",
    )
    comparison_id: uuid.UUID = Field(
        foreign_key="comparisons.id",
        index=True,
        ondelete="CASCADE",
        description="Associated comparison session ID",
    )
    housing_ad_id: uuid.UUID = Field(
        foreign_key="housing_ads.id",
        index=True,
        ondelete="CASCADE",
        description="Associated housing ad ID",
    )
    overall_score: Optional[Decimal] = Field(
        default=None,
        max_digits=5,
        decimal_places=2,
        description="Overall match percentage (0.00 to 100.00)",
    )
    rank: Optional[int] = Field(
        default=None,
        description="Relative rank position in this comparison (1 = top match)",
    )
    eligible: bool = Field(
        default=True,
        description="Whether all mandatory/hard constraints passed",
    )
    exclusion_reasons: List[Any] = Field(
        default_factory=list,
        sa_column=Column(JSON_TYPE, nullable=False),
        description="Reasons for failing hard constraints if ineligible",
    )
    summary: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="AI-generated qualitative summary for this ad",
    )
    pros: List[Any] = Field(
        default_factory=list,
        sa_column=Column(JSON_TYPE, nullable=False),
        description="Identified positive aspects of the ad",
    )
    cons: List[Any] = Field(
        default_factory=list,
        sa_column=Column(JSON_TYPE, nullable=False),
        description="Identified drawbacks / cons of the ad",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False,
        description="Record creation timestamp (UTC)",
    )

    # Relationships
    comparison: Optional["Comparison"] = Relationship(back_populates="comparison_ads")
    housing_ad: Optional["HousingAd"] = Relationship(back_populates="comparison_ads")
    score_details: List["ComparisonScoreDetail"] = Relationship(
        back_populates="comparison_ad",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
