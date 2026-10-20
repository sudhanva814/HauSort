import pytest
from unittest.mock import AsyncMock
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.ad_source import AdSource
from app.models.housing_ad import HousingAd
from app.services.scraping.fetcher import FetchResult
from app.services.scraping.orchestrator import ScraperOrchestrator


@pytest.fixture
def in_memory_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.mark.asyncio
async def test_scraper_orchestrator_successful_scrape(in_memory_session: Session):
    orchestrator = ScraperOrchestrator()

    mock_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WG Zimmer Trier Uni</title>
        <meta property="og:title" content="Schönes WG Zimmer in Trier" />
        <meta property="og:description" content="Warmmiete: 390 Euro. Kaution: 700 Euro. Größe: 16 m2. Anmeldung möglich." />
    </head>
    <body>
        <p>Main content for Trier WG room near university.</p>
    </body>
    </html>
    """

    orchestrator.fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            html=mock_html,
            final_url="https://www.wg-gesucht.de/ad/123",
            status_code=200,
            duration_ms=150.0,
            response_size=len(mock_html),
            success=True,
        )
    )

    result = await orchestrator.scrape_single_url("https://www.wg-gesucht.de/ad/123", in_memory_session)

    assert result.status == "succeeded"
    assert result.title == "Schönes WG Zimmer in Trier"
    assert result.housing_ad is not None
    assert result.housing_ad.warm_rent == 390
    assert result.housing_ad.city == "Trier"

    # Verify database persistence
    saved_ad = in_memory_session.exec(select(HousingAd).where(HousingAd.id == result.housing_ad_id)).first()
    assert saved_ad is not None
    assert saved_ad.warm_rent == 390

    saved_source = in_memory_session.exec(select(AdSource).where(AdSource.id == result.source_id)).first()
    assert saved_source is not None
    assert saved_source.housing_ad_id == saved_ad.id


def test_scraper_orchestrator_pasted_text(in_memory_session: Session):
    orchestrator = ScraperOrchestrator()
    pasted_text = (
        "Zimmer in 3er WG in Berlin Mitte.\n"
        "Warmmiete: 550 €, Kaution: 1000 €.\n"
        "Größe: 20 qm, voll möbliert.\n"
        "Anmeldung möglich ab sofort."
    )

    result = orchestrator.process_pasted_text(
        raw_text=pasted_text,
        title="WG Berlin Mitte",
        source_url="https://example.com/ad",
        session=in_memory_session,
    )

    assert result.status == "succeeded"
    assert result.housing_ad is not None
    assert result.housing_ad.city == "Berlin"
    assert result.housing_ad.warm_rent == 550
    assert result.housing_ad.deposit == 1000
    assert result.housing_ad.registration_status == "yes"

    # Verify persistence
    ad = in_memory_session.exec(select(HousingAd).where(HousingAd.id == result.housing_ad_id)).first()
    assert ad is not None
    assert ad.city == "Berlin"
