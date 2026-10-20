import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import CheckConstraint, Column, Text, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import JSON_TYPE
from app.models.enums import ScoreDetailStatus

if TYPE_CHECKING:
    from app.models.comparison_ad import ComparisonAd


class ComparisonScoreDetail(SQLModel, table=True):
    """Stores granular per-criterion evaluation details for explainable scoring."""
    __tablename__ = "comparison_score_details"
    __table_args__ = (
        UniqueConstraint(
            "comparison_ad_id",
            "criterion_key",
            name="uq_comparison_score_details_ad_criterion",
        ),
        CheckConstraint(
            "criterion_score IS NULL OR (criterion_score >= 0 AND criterion_score <= 100)",
            name="chk_score_detail_score_range",
        ),
        CheckConstraint(
            "weight >= 0",
            name="chk_score_detail_weight_non_neg",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        description="Score detail ID",
    )
    comparison_ad_id: uuid.UUID = Field(
        foreign_key="comparison_ads.id",
        index=True,
        ondelete="CASCADE",
        description="Associated comparison ad evaluation ID",
    )
    criterion_key: str = Field(
        max_length=50,
        description="Identifier of the criterion, e.g. price, university_commute, anmeldung",
    )
    criterion_score: Optional[Decimal] = Field(
        default=None,
        max_digits=5,
        decimal_places=2,
        description="Score between 0.00 and 100.00",
    )
    weight: Decimal = Field(
        default=Decimal("0.00"),
        max_digits=5,
        decimal_places=2,
        description="Relative weight used for this criterion in the comparison run",
    )
    weighted_contribution: Optional[Decimal] = Field(
        default=None,
        max_digits=7,
        decimal_places=3,
        description="Points contributed to final score after weight application",
    )
    status: str = Field(
        default=ScoreDetailStatus.UNKNOWN,
        max_length=20,
        description="Status: pass, fail, unknown, not_applicable",
    )
    explanation: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Human-readable reason or justification",
    )
    evidence: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON_TYPE, nullable=True),
        description="Extracted value and supporting evidence from the advertisement",
    )

    # Relationships
    comparison_ad: Optional["ComparisonAd"] = Relationship(back_populates="score_details")
