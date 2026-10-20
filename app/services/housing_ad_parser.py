import re
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.models.enums import PropertyType, RegistrationStatus
from app.schemas.scraping import ExtractedPage, NormalizedHousingAdData


class HousingAdParser:
    """
    Parses unstructured text, title, and metadata into a normalized
    housing advertisement structure adhering to project domain rules.
    """

    GERMAN_CITIES = [
        "Trier", "Berlin", "München", "Munich", "Hamburg", "Köln", "Cologne",
        "Frankfurt", "Stuttgart", "Düsseldorf", "Leipzig", "Dresden", "Bremen",
        "Hannover", "Nürnberg", "Heidelberg", "Freiburg", "Aachen", "Bonn",
        "Münster", "Mainz", "Saarbrücken", "Kaiserslautern", "Koblenz",
    ]

    def parse(self, extracted: ExtractedPage) -> NormalizedHousingAdData:
        title = (extracted.title or "Untitled Housing Listing").strip()
        full_text = f"{title}\n\n{extracted.description or ''}\n\n{extracted.main_text or ''}"

        # 1. Rent extraction
        warm_rent = self._extract_amount(
            full_text,
            [
                r"(?:Warmmiete|Warm|Gesamtmiete|Miete\s+warm)[\s:]*([0-9]+(?:[.,][0-9]{2})?)\s*€?",
                r"([0-9]+(?:[.,][0-9]{2})?)\s*€?\s*(?:warm|Warmmiete|Gesamtmiete)",
            ],
        )

        cold_rent = self._extract_amount(
            full_text,
            [
                r"(?:Kaltmiete|Kalt)[\s:]*([0-9]+(?:[.,][0-9]{2})?)\s*€?",
                r"([0-9]+(?:[.,][0-9]{2})?)\s*€?\s*(?:kalt|Kaltmiete)",
            ],
        )

        # If warm rent is not explicitly labeled, search for generic 'Miete: XXX €'
        if not warm_rent and not cold_rent:
            generic_rent = self._extract_amount(
                full_text,
                [r"(?:Miete|Kosten)[\s:]*([0-9]+(?:[.,][0-9]{2})?)\s*€?"],
            )
            warm_rent = generic_rent

        # Additional costs (Nebenkosten)
        additional_costs = self._extract_amount(
            full_text,
            [r"(?:Nebenkosten|NK)[\s:]*([0-9]+(?:[.,][0-9]{2})?)\s*€?"],
        )

        # Deposit (Kaution)
        deposit = self._extract_amount(
            full_text,
            [
                r"(?:Kaution)[\s:]*([0-9]+(?:[.,][0-9]{2})?)\s*€?",
                r"([0-9]+(?:[.,][0-9]{2})?)\s*€?\s*(?:Kaution)",
            ],
        )

        # 2. Room / Property Size
        room_size_sqm = self._extract_size(full_text)

        # 3. City / Location
        city = self._extract_city(full_text, extracted.submitted_url)

        # 4. Registration (Anmeldung) status
        registration_status = self._extract_anmeldung_status(full_text)

        # 5. Furnished status
        furnished = self._extract_furnished(full_text)

        # 6. Property Type
        property_type = self._extract_property_type(full_text)

        # 7. Minimum Contract Duration
        min_contract_months = self._extract_contract_months(full_text)

        # 8. Amenities detection
        amenities = self._extract_amenities(full_text)

        return NormalizedHousingAdData(
            title=title,
            description=extracted.description or extracted.main_text or title,
            property_type=property_type,
            city=city,
            cold_rent=cold_rent,
            additional_costs=additional_costs,
            warm_rent=warm_rent,
            deposit=deposit,
            room_size_sqm=room_size_sqm,
            furnished=furnished,
            minimum_contract_months=min_contract_months,
            registration_status=registration_status,
            amenities=amenities,
            extraction_status="succeeded" if (warm_rent or room_size_sqm or city) else "partial",
        )

    def _extract_amount(self, text: str, patterns: List[str]) -> Optional[Decimal]:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_val = match.group(1).replace(".", "").replace(",", ".")
                try:
                    val = Decimal(raw_val)
                    if 50 <= val <= 10000:  # Sensible rent/deposit range filter
                        return val
                except Exception:
                    continue
        return None

    def _extract_size(self, text: str) -> Optional[Decimal]:
        patterns = [
            r"([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:m²|qm|m2|Quadratmeter)",
            r"(?:Größe|Zimmergröße)[\s:]*([0-9]+(?:[.,][0-9]{1,2})?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_val = match.group(1).replace(",", ".")
                try:
                    val = Decimal(raw_val)
                    if 5 <= val <= 500:  # Reasonable sqm range
                        return val
                except Exception:
                    continue
        return None

    def _extract_city(self, text: str, url: str) -> str:
        # Check text for major German cities
        for city in self.GERMAN_CITIES:
            if re.search(rf"\b{re.escape(city)}\b", text, re.IGNORECASE):
                return city

        # Check URL path
        for city in self.GERMAN_CITIES:
            if city.lower() in url.lower():
                return city

        return "Unknown"

    def _extract_anmeldung_status(self, text: str) -> str:
        if re.search(r"\b(keine|ohne|nicht möglich)\s+(?:anmeldung|wohnungsgeberbestätigung)\b", text, re.IGNORECASE):
            return RegistrationStatus.NO
        if re.search(r"\b(mit|inkl|möglich|erlaubt|vorhanden)\s+anmeldung\b", text, re.IGNORECASE) or \
           re.search(r"\banmeldung\s+(möglich|erlaubt|garantiert)\b", text, re.IGNORECASE):
            return RegistrationStatus.YES
        return RegistrationStatus.UNKNOWN

    def _extract_furnished(self, text: str) -> Optional[bool]:
        if re.search(r"\b(unmöbliert|nicht möbliert|ohne möbel)\b", text, re.IGNORECASE):
            return False
        if re.search(r"\b(möbliert|voll möbliert|teilmöbliert|ausgestattet mit möbeln)\b", text, re.IGNORECASE):
            return True
        return None

    def _extract_property_type(self, text: str) -> str:
        if re.search(r"\b(wg-zimmer|wg zimmer|in einer \d+-er wg|mitbewohner)\b", text, re.IGNORECASE):
            return PropertyType.WG_ROOM
        if re.search(r"\b(studio|1-zimmer-wohnung|1 zimmer wohnung)\b", text, re.IGNORECASE):
            return PropertyType.STUDIO
        if re.search(r"\b(wohnung|apartment|maisonette)\b", text, re.IGNORECASE):
            return PropertyType.APARTMENT
        if re.search(r"\b(haus|reihenhaus)\b", text, re.IGNORECASE):
            return PropertyType.HOUSE
        return PropertyType.WG_ROOM

    def _extract_contract_months(self, text: str) -> Optional[int]:
        match = re.search(r"(?:mindestmietdauer|mindestens|mindestdauer)[\s:]*([0-9]+)\s*(?:monat|monate)", text, re.IGNORECASE)
        if match:
            try:
                months = int(match.group(1))
                if 1 <= months <= 60:
                    return months
            except Exception:
                pass
        return None

    def _extract_amenities(self, text: str) -> Dict[str, bool]:
        amenity_keywords = {
            "balcony": r"\b(balkon|terrasse|loggia)\b",
            "washing_machine": r"\b(waschmaschine|waschraum)\b",
            "dishwasher": r"\b(spülmaschine|geschirrspüler)\b",
            "elevator": r"\b(aufzug|fahrstuhl)\b",
            "wifi": r"\b(wlan|wifi|internet)\b",
            "basement": r"\b(keller|kellerabteil)\b",
            "garden": r"\b(garten|gartenmitbenutzung)\b",
            "bike_storage": r"\b(fahrradkeller|fahrradabstellplatz)\b",
        }
        detected: Dict[str, bool] = {}
        for key, pattern in amenity_keywords.items():
            if re.search(pattern, text, re.IGNORECASE):
                detected[key] = True
        return detected


# Global parser instance
housing_ad_parser = HousingAdParser()
