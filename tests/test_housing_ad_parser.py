from decimal import Decimal
from app.models.enums import PropertyType, RegistrationStatus
from app.schemas.scraping import ExtractedPage
from app.services.housing_ad_parser import HousingAdParser


def test_housing_ad_parser_extraction():
    parser = HousingAdParser()
    extracted_page = ExtractedPage(
        submitted_url="https://www.wg-gesucht.de/wg-zimmer-in-Trier.98765.html",
        title="Sonniges WG-Zimmer in Trier Tarforst",
        description="Warmmiete: 420 € (Kaltmiete: 320 €, Nebenkosten: 100 €). Kaution: 800 €.\n"
                    "Größe: 19 m².\n"
                    "Anmeldung möglich!\n"
                    "Zimmer ist voll möbliert mit Bett, Schreibtisch und Schrank.\n"
                    "Ausstattung: Balkon, Waschmaschine, WLAN vorhanden.\n"
                    "Mindestmietdauer: 6 Monate.",
        main_text="",
    )

    result = parser.parse(extracted_page)

    assert result.city == "Trier"
    assert result.warm_rent == Decimal("420")
    assert result.cold_rent == Decimal("320")
    assert result.additional_costs == Decimal("100")
    assert result.deposit == Decimal("800")
    assert result.room_size_sqm == Decimal("19")
    assert result.registration_status == RegistrationStatus.YES
    assert result.furnished is True
    assert result.property_type == PropertyType.WG_ROOM
    assert result.minimum_contract_months == 6
    assert result.amenities.get("balcony") is True
    assert result.amenities.get("washing_machine") is True
    assert result.amenities.get("wifi") is True


def test_housing_ad_parser_no_anmeldung():
    parser = HousingAdParser()
    extracted_page = ExtractedPage(
        submitted_url="https://example.com/listing",
        title="Zwischenmiete München",
        description="Miete: 650 Euro warm. 25 qm. Keine Anmeldung möglich! Unmöbliert.",
    )

    result = parser.parse(extracted_page)

    assert result.city == "München"
    assert result.warm_rent == Decimal("650")
    assert result.room_size_sqm == Decimal("25")
    assert result.registration_status == RegistrationStatus.NO
    assert result.furnished is False
