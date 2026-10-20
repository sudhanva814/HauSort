import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.db import get_session
from app.models.housing_ad import HousingAd
from app.schemas.scraping import (
    NormalizedHousingAdData,
    PastedTextRequest,
    ScrapedAdResult,
    ScrapeJobRequest,
    ScrapeJobResponse,
)
from app.services.scraping.orchestrator import scraper_orchestrator

router = APIRouter(tags=["Scraping & Housing Ads"])


@router.post(
    "/scrape-jobs",
    response_model=ScrapeJobResponse,
    status_code=status.HTTP_200_OK,
    summary="Scrape and extract housing advertisements from URLs",
)
async def create_scrape_job(
    request: ScrapeJobRequest,
    session: Session = Depends(get_session),
):
    """
    Submits up to 10 housing listing URLs to be fetched, parsed, and normalized.
    Results and sources are persisted in the database.
    """
    return await scraper_orchestrator.scrape_urls(request.urls, session)


@router.post(
    "/housing-ads/from-text",
    response_model=ScrapedAdResult,
    status_code=status.HTTP_201_CREATED,
    summary="Create a normalized housing ad from pasted text",
)
async def create_ad_from_text(
    request: PastedTextRequest,
    session: Session = Depends(get_session),
):
    """
    Fallback endpoint for submitting raw pasted listing text when a website is
    unsupported, blocked, or requires manual review.
    """
    return scraper_orchestrator.process_pasted_text(
        raw_text=request.raw_text,
        title=request.title,
        source_url=request.source_url,
        session=session,
    )


@router.get(
    "/housing-ads/{ad_id}",
    response_model=NormalizedHousingAdData,
    summary="Retrieve normalized housing ad details",
)
async def get_housing_ad(
    ad_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    """Retrieves a normalized housing ad by its unique ID."""
    housing_ad = session.exec(select(HousingAd).where(HousingAd.id == ad_id)).first()
    if not housing_ad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Housing ad with ID '{ad_id}' not found.",
        )

    return NormalizedHousingAdData(
        id=housing_ad.id,
        title=housing_ad.title,
        description=housing_ad.description,
        property_type=housing_ad.property_type,
        city=housing_ad.city,
        district=housing_ad.district,
        postal_code=housing_ad.postal_code,
        street_address=housing_ad.street_address,
        latitude=housing_ad.latitude,
        longitude=housing_ad.longitude,
        cold_rent=housing_ad.cold_rent,
        additional_costs=housing_ad.additional_costs,
        heating_costs=housing_ad.heating_costs,
        warm_rent=housing_ad.warm_rent,
        deposit=housing_ad.deposit,
        room_size_sqm=housing_ad.room_size_sqm,
        furnished=housing_ad.furnished,
        available_from=housing_ad.available_from,
        minimum_contract_months=housing_ad.minimum_contract_months,
        registration_status=housing_ad.registration_status,
        flatmates_count=housing_ad.flatmates_count,
        amenities=housing_ad.amenities,
        extraction_status=housing_ad.extraction_status,
    )
