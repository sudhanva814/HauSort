import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse
from sqlmodel import Session

from app.models.ad_source import AdSource
from app.models.enums import ExtractionStatus, SourceStatus, SourceType
from app.models.housing_ad import HousingAd
from app.schemas.scraping import (
    ExtractedPage,
    NormalizedHousingAdData,
    ScrapedAdResult,
    ScrapeJobResponse,
)
from app.services.housing_ad_parser import housing_ad_parser
from app.services.scraping.browser_fetcher import BrowserFetcher
from app.services.scraping.fetcher import HTTPXFetcher
from app.services.scraping.html_parser import HTMLParser
from app.services.scraping.site_adapters.registry import adapter_registry
from app.services.scraping.text_extractor import TextExtractor


class ScraperOrchestrator:
    """
    Coordinates the complete scraping pipeline:
    URL security -> Fetching (HTTPX -> Adapter -> Trafilatura -> Browser) ->
    Parsing & Normalization -> Database persistence (ad_sources & housing_ads).
    """

    def __init__(self):
        self.fetcher = HTTPXFetcher()
        self.html_parser = HTMLParser()
        self.text_extractor = TextExtractor()
        self.browser_fetcher = BrowserFetcher()
        self.ad_parser = housing_ad_parser

    async def scrape_urls(self, urls: List[str], session: Session) -> ScrapeJobResponse:
        """Processes a batch of URLs and returns structured scraping results."""
        job_id = uuid.uuid4()
        results: List[ScrapedAdResult] = []

        for url in urls:
            result = await self.scrape_single_url(url, session)
            results.append(result)

        succeeded_count = sum(1 for r in results if r.status in {"succeeded", "partial"})
        failed_count = sum(1 for r in results if r.status == "failed")

        return ScrapeJobResponse(
            job_id=job_id,
            total_submitted=len(urls),
            total_succeeded=succeeded_count,
            total_failed=failed_count,
            results=results,
        )

    async def scrape_single_url(self, url: str, session: Session) -> ScrapedAdResult:
        """Runs the scraping pipeline for a single listing URL with database persistence."""
        extracted_at = datetime.now(timezone.utc)
        parsed_url = urlparse(url)
        domain = parsed_url.hostname or ""

        # 1. Create initial AdSource record
        ad_source = AdSource(
            housing_ad_id=None,
            source_type=SourceType.URL,
            source_url=url,
            source_domain=domain,
            status=SourceStatus.PENDING,
            created_at=extracted_at,
        )

        # 2. Fetch HTML using HTTPX
        fetch_res = await self.fetcher.fetch(url)
        ad_source.last_attempt_at = datetime.now(timezone.utc)

        if not fetch_res.success:
            ad_source.status = SourceStatus.FAILED
            ad_source.error_message = fetch_res.error_message
            session.add(ad_source)
            session.commit()
            session.refresh(ad_source)

            return ScrapedAdResult(
                source_id=ad_source.id,
                housing_ad_id=None,
                submitted_url=url,
                final_url=fetch_res.final_url,
                status="failed",
                extracted_at=extracted_at,
                error_code=fetch_res.error_code,
                error_message=fetch_res.error_message,
            )

        html = fetch_res.html
        ad_source.scraped_at = datetime.now(timezone.utc)
        content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
        ad_source.raw_content_hash = content_hash

        # 3. Extraction: Check site adapter first
        extracted_page: Optional[ExtractedPage] = None
        adapter = adapter_registry.get_adapter(fetch_res.final_url)
        if adapter:
            extracted_page = adapter.extract(html, fetch_res.final_url)

        # Fallback to general HTML parsing
        if not extracted_page or not extracted_page.description:
            extracted_page = self.html_parser.parse(html, fetch_res.final_url)

        # Fallback to Trafilatura if main text is noisy or sparse
        if self.text_extractor.should_use_fallback(extracted_page):
            extracted_page = self.text_extractor.extract_with_trafilatura(html, extracted_page)

        # Optional browser fallback if still insufficient
        if (
            self.text_extractor.should_use_fallback(extracted_page)
            and self.browser_fetcher.timeout_seconds > 0
        ):
            browser_res = await self.browser_fetcher.fetch(url)
            if browser_res.success:
                extracted_page = self.html_parser.parse(browser_res.html, browser_res.final_url)
                extracted_page.extraction_method = "playwright"

        # 4. Parse into normalized housing ad fields
        normalized_ad = self.ad_parser.parse(extracted_page)

        # 5. Persist HousingAd and link AdSource
        housing_ad = HousingAd(
            title=normalized_ad.title,
            description=normalized_ad.description,
            property_type=normalized_ad.property_type,
            city=normalized_ad.city,
            cold_rent=normalized_ad.cold_rent,
            additional_costs=normalized_ad.additional_costs,
            warm_rent=normalized_ad.warm_rent,
            deposit=normalized_ad.deposit,
            room_size_sqm=normalized_ad.room_size_sqm,
            furnished=normalized_ad.furnished,
            available_from=normalized_ad.available_from,
            minimum_contract_months=normalized_ad.minimum_contract_months,
            registration_status=normalized_ad.registration_status,
            amenities=normalized_ad.amenities,
            extraction_status=ExtractionStatus.SUCCEEDED if normalized_ad.warm_rent else ExtractionStatus.PARTIAL,
            created_at=extracted_at,
            updated_at=extracted_at,
        )

        session.add(housing_ad)
        session.commit()
        session.refresh(housing_ad)

        # Update AdSource with housing_ad_id and raw text snippet
        ad_source.housing_ad_id = housing_ad.id
        ad_source.status = SourceStatus.SUCCEEDED
        ad_source.raw_text = (extracted_page.main_text or extracted_page.description or "")[:20000]
        session.add(ad_source)
        session.commit()
        session.refresh(ad_source)

        normalized_ad.id = housing_ad.id

        return ScrapedAdResult(
            source_id=ad_source.id,
            housing_ad_id=housing_ad.id,
            submitted_url=url,
            final_url=fetch_res.final_url,
            status="succeeded" if housing_ad.extraction_status == ExtractionStatus.SUCCEEDED else "partial",
            title=housing_ad.title,
            description=housing_ad.description[:500] if housing_ad.description else None,
            site_name=extracted_page.site_name,
            extracted_at=extracted_at,
            warnings=extracted_page.warnings,
            housing_ad=normalized_ad,
        )

    def process_pasted_text(
        self,
        raw_text: str,
        title: Optional[str],
        source_url: Optional[str],
        session: Session,
    ) -> ScrapedAdResult:
        """Processes directly pasted listing text (fallback when scraping is unavailable)."""
        extracted_at = datetime.now(timezone.utc)
        clean_title = (title or raw_text.splitlines()[0][:100] if raw_text else "Pasted Housing Ad").strip()

        extracted_page = ExtractedPage(
            submitted_url=source_url or "manual://pasted-text",
            final_url=source_url,
            site_name="Pasted Text",
            title=clean_title,
            description=raw_text,
            main_text=raw_text,
            extraction_method="pasted_text",
        )

        normalized_ad = self.ad_parser.parse(extracted_page)

        # Persist HousingAd
        housing_ad = HousingAd(
            title=normalized_ad.title,
            description=normalized_ad.description,
            property_type=normalized_ad.property_type,
            city=normalized_ad.city,
            cold_rent=normalized_ad.cold_rent,
            additional_costs=normalized_ad.additional_costs,
            warm_rent=normalized_ad.warm_rent,
            deposit=normalized_ad.deposit,
            room_size_sqm=normalized_ad.room_size_sqm,
            furnished=normalized_ad.furnished,
            available_from=normalized_ad.available_from,
            minimum_contract_months=normalized_ad.minimum_contract_months,
            registration_status=normalized_ad.registration_status,
            amenities=normalized_ad.amenities,
            extraction_status=ExtractionStatus.SUCCEEDED if normalized_ad.warm_rent else ExtractionStatus.PARTIAL,
            created_at=extracted_at,
            updated_at=extracted_at,
        )

        session.add(housing_ad)
        session.commit()
        session.refresh(housing_ad)

        # Persist AdSource
        ad_source = AdSource(
            housing_ad_id=housing_ad.id,
            source_type=SourceType.PASTED_TEXT,
            source_url=source_url,
            raw_text=raw_text[:20000],
            raw_content_hash=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            status=SourceStatus.SUCCEEDED,
            created_at=extracted_at,
            scraped_at=extracted_at,
            last_attempt_at=extracted_at,
        )
        session.add(ad_source)
        session.commit()
        session.refresh(ad_source)

        normalized_ad.id = housing_ad.id

        return ScrapedAdResult(
            source_id=ad_source.id,
            housing_ad_id=housing_ad.id,
            submitted_url=source_url or "manual://pasted-text",
            final_url=source_url,
            status="succeeded" if housing_ad.extraction_status == ExtractionStatus.SUCCEEDED else "partial",
            title=housing_ad.title,
            description=housing_ad.description[:500] if housing_ad.description else None,
            site_name="Pasted Text",
            extracted_at=extracted_at,
            housing_ad=normalized_ad,
        )


# Global orchestrator instance
scraper_orchestrator = ScraperOrchestrator()
