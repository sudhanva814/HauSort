import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import CheckConstraint, Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import JSON_TYPE, utc_now

if TYPE_CHECKING:
    from app.models.comparison import Comparison
    from app.models.user import User


class UserPreference(SQLModel, table=True):
    """Stores reusable housing-search criteria and priority weights."""
    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint(
            "max_warm_rent IS NULL OR max_warm_rent >= 0",
            name="chk_user_pref_max_warm_rent_non_neg",
        ),
        CheckConstraint(
            "max_cold_rent IS NULL OR max_cold_rent >= 0",
            name="chk_user_pref_max_cold_rent_non_neg",
        ),
        CheckConstraint(
            "max_deposit IS NULL OR max_deposit >= 0",
            name="chk_user_pref_max_deposit_non_neg",
        ),
        CheckConstraint(
            "max_commute_minutes IS NULL OR max_commute_minutes >= 0",
            name="chk_user_pref_commute_non_neg",
        ),
        CheckConstraint(
            "min_contract_months IS NULL OR min_contract_months >= 0",
            name="chk_user_pref_contract_non_neg",
        ),
        CheckConstraint(
            "max_flatmates IS NULL OR max_flatmates >= 0",
            name="chk_user_pref_flatmates_non_neg",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        description="Preference profile ID",
    )
    user_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        ondelete="CASCADE",
        description="Owner user ID",
    )
    name: str = Field(
        max_length=100,
        description="Profile name, e.g. 'Trier student housing'",
    )
    max_warm_rent: Optional[Decimal] = Field(
        default=None,
        max_digits=10,
        decimal_places=2,
        description="Maximum monthly warm rent",
    )
    max_cold_rent: Optional[Decimal] = Field(
        default=None,
        max_digits=10,
        decimal_places=2,
        description="Optional cold-rent ceiling",
    )
    max_deposit: Optional[Decimal] = Field(
        default=None,
        max_digits=10,
        decimal_places=2,
        description="Maximum deposit (Kaution)",
    )
    preferred_city: str = Field(
        max_length=100,
        description="Preferred search city, e.g. 'Trier'",
    )
    target_location: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON_TYPE, nullable=True),
        description="Target destination, coordinates, university info",
    ) 
    max_commute_minutes: Optional[int] = Field(
        default=None,
        description="Travel-time ceiling in minutes",
    )
    require_anmeldung: bool = Field(
        default=False,
        description="Whether official city registration is mandatory",
    )
    require_furnished: Optional[bool] = Field(
        default=None,
        description="True = mandatory, False = not required, None = no preference",
    )
    min_contract_months: Optional[int] = Field(
        default=None,
        description="Minimum contract duration in months",
    )
    max_flatmates: Optional[int] = Field(
        default=None,
        description="Maximum preferred flatmates",
    )
    weights: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON_TYPE, nullable=False),
        description="Relative importance weights of criteria",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False,
        description="Creation timestamp (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False,
        sa_column_kwargs={"onupdate": utc_now},
        description="Last update timestamp (UTC)",
    )

    # Relationships
    user: Optional["User"] = Relationship(back_populates="preferences")
    comparisons: List["Comparison"] = Relationship(back_populates="preference")
