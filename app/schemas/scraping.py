import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScrapeJobRequest(BaseModel):
    """Request model for submitting URLs to be scraped and parsed."""
    urls: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of 1 to 10 housing listing URLs to scrape.",
    )


class PastedTextRequest(BaseModel):
    """Fallback request model for submitting raw pasted listing text."""
    raw_text: str = Field(
        ...,
        min_length=20,
        description="Raw listing text copied from a website or advertisement.",
    )
    title: Optional[str] = Field(
        default=None,
        description="Optional title for the listing.",
    )
    source_url: Optional[str] = Field(
        default=None,
        description="Optional original URL the text was copied from.",
    )


class ExtractedPage(BaseModel):
    """Internal model holding scraped text, structured metadata, and provenance."""
    submitted_url: str
    final_url: Optional[str] = None
    site_name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    main_text: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    extraction_method: str = "unknown"
    warnings: List[str] = Field(default_factory=list)


class NormalizedHousingAdData(BaseModel):
    """Structured fields extracted and normalized from listing content."""
    id: Optional[uuid.UUID] = None
    title: str
    description: str
    property_type: str = "wg_room"
    city: str
    district: Optional[str] = None
    postal_code: Optional[str] = None
    street_address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    cold_rent: Optional[Decimal] = None
    additional_costs: Optional[Decimal] = None
    heating_costs: Optional[Decimal] = None
    warm_rent: Optional[Decimal] = None
    deposit: Optional[Decimal] = None
    room_size_sqm: Optional[Decimal] = None
    furnished: Optional[bool] = None
    available_from: Optional[date] = None
    minimum_contract_months: Optional[int] = None
    registration_status: str = "unknown"
    flatmates_count: Optional[int] = None
    amenities: Dict[str, Any] = Field(default_factory=dict)
    extraction_status: str = "succeeded"


class ScrapedAdResult(BaseModel):
    """Detailed per-URL scraping and parsing result."""
    source_id: uuid.UUID
    housing_ad_id: Optional[uuid.UUID] = None
    submitted_url: str
    final_url: Optional[str] = None
    status: str  # succeeded, partial, failed
    title: Optional[str] = None
    description: Optional[str] = None
    site_name: Optional[str] = None
    extracted_at: datetime
    warnings: List[str] = Field(default_factory=list)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    housing_ad: Optional[NormalizedHousingAdData] = None


class ScrapeJobResponse(BaseModel):
    """Batch response for scrape jobs."""
    job_id: uuid.UUID
    total_submitted: int
    total_succeeded: int
    total_failed: int
    results: List[ScrapedAdResult]
