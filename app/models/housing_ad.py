import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import CheckConstraint, Column, Date, DateTime, Float, Text
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import JSON_TYPE, utc_now
from app.models.enums import ExtractionStatus, PropertyType, RegistrationStatus

if TYPE_CHECKING:
    from app.models.ad_source import AdSource
    from app.models.comparison_ad import ComparisonAd


class HousingAd(SQLModel, table=True):
    """Central table storing normalized housing advertisement information."""
    __tablename__ = "housing_ads"
    __table_args__ = (
        CheckConstraint(
            "cold_rent IS NULL OR cold_rent >= 0",
            name="chk_housing_ad_cold_rent_non_neg",
        ),
        CheckConstraint(
            "additional_costs IS NULL OR additional_costs >= 0",
            name="chk_housing_ad_additional_costs_non_neg",
        ),
        CheckConstraint(
            "heating_costs IS NULL OR heating_costs >= 0",
            name="chk_housing_ad_heating_costs_non_neg",
        ),
        CheckConstraint(
            "warm_rent IS NULL OR warm_rent >= 0",
            name="chk_housing_ad_warm_rent_non_neg",
        ),
        CheckConstraint(
            "deposit IS NULL OR deposit >= 0",
            name="chk_housing_ad_deposit_non_neg",
        ),
        CheckConstraint(
            "room_size_sqm IS NULL OR room_size_sqm >= 0",
            name="chk_housing_ad_room_size_non_neg",
        ),
        CheckConstraint(
            "minimum_contract_months IS NULL OR minimum_contract_months >= 0",
            name="chk_housing_ad_min_contract_non_neg",
        ),
        CheckConstraint(
            "flatmates_count IS NULL OR flatmates_count >= 0",
            name="chk_housing_ad_flatmates_non_neg",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        description="Unique ad ID",
    )
    title: str = Field(
        sa_column=Column(Text, nullable=False),
        description="Advertisement title",
    )
    description: str = Field(
        sa_column=Column(Text, nullable=False),
        description="Cleaned full description",
    )
    property_type: str = Field(
        default=PropertyType.WG_ROOM,
        max_length=30,
        description="WG room, apartment, studio, etc.",
    )
    city: str = Field(
        max_length=100,
        index=True,
        description="City name",
    )
    district: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Neighborhood / district name",
    )
    postal_code: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Postal code",
    )
    street_address: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Street address if available",
    )
    latitude: Optional[float] = Field(
        default=None,
        sa_type=Float,
        description="Geocoded latitude",
    )
    longitude: Optional[float] = Field(
        default=None,
        sa_type=Float,
        description="Geocoded longitude",
    )
    cold_rent: Optional[Decimal] = Field(
        default=None,
        max_digits=10,
        decimal_places=2,
        description="Monthly Kaltmiete",
    )
    additional_costs: Optional[Decimal] = Field(
        default=None,
        max_digits=10,
        decimal_places=2,
        description="Nebenkosten",
    )
    heating_costs: Optional[Decimal] = Field(
        default=None,
        max_digits=10,
        decimal_places=2,
        description="Heating costs if separately stated",
    )
    warm_rent: Optional[Decimal] = Field(
        default=None,
        max_digits=10,
        decimal_places=2,
        index=True,
        description="Total monthly Warmmiete",
    )
    deposit: Optional[Decimal] = Field(
        default=None,
        max_digits=10,
        decimal_places=2,
        description="Kaution",
    )
    room_size_sqm: Optional[Decimal] = Field(
        default=None,
        max_digits=8,
        decimal_places=2,
        description="Room or property size in square meters",
    )
    furnished: Optional[bool] = Field(
        default=None,
        description="Furnishing status (True, False, None if unstated)",
    )
    available_from: Optional[date] = Field(
        default=None,
        sa_type=Date,
        index=True,
        description="Availability date",
    )
    minimum_contract_months: Optional[int] = Field(
        default=None,
        description="Minimum contract duration in months",
    )
    registration_status: str = Field(
        default=RegistrationStatus.UNKNOWN,
        max_length=20,
        description="Anmeldung status: yes, no, likely, unknown",
    )
    flatmates_count: Optional[int] = Field(
        default=None,
        description="Number of other residents / flatmates",
    )
    amenities: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON_TYPE, nullable=False),
        description="Amenities like balcony, washing machine, basement, etc.",
    )
    extraction_status: str = Field(
        default=ExtractionStatus.PENDING,
        max_length=20,
        description="Extraction status: pending, succeeded, failed, partial",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False,
        description="Record creation timestamp (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False,
        sa_column_kwargs={"onupdate": utc_now},
        description="Last update timestamp (UTC)",
    )

    # Relationships
    sources: List["AdSource"] = Relationship(
        back_populates="housing_ad",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    comparison_ads: List["ComparisonAd"] = Relationship(
        back_populates="housing_ad",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
