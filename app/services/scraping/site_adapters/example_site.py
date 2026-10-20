import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from app.schemas.scraping import ExtractedPage
from app.services.scraping.site_adapters.base import BaseSiteAdapter


class WgGesuchtAdapter(BaseSiteAdapter):
    """
    Adapter tailored for WG-Gesucht public listing pages (wg-gesucht.de).
    Extracts key facts, multi-part descriptions (Zimmer, Lage, WG-Leben, Sonstiges),
    and price details.
    """

    def supports(self, url: str) -> bool:
        hostname = (urlparse(url).hostname or "").lower()
        return "wg-gesucht.de" in hostname

    def extract(self, html: str, url: str) -> Optional[ExtractedPage]:
        soup = BeautifulSoup(html, "lxml")
        warnings: List[str] = []

        # 1. Title
        title_el = (
            soup.find("h1", id="slider-headline")
            or soup.find("h1", class_=re.compile(r"headline", re.I))
            or soup.find("meta", property="og:title")
            or soup.find("title")
        )
        if title_el:
            title = title_el.get("content", "").strip() if title_el.name == "meta" else title_el.get_text(strip=True)
        else:
            title = None

        # 2. Key facts (Rent, Size, City, Dates)
        key_facts: Dict[str, Any] = {}
        facts_container = soup.find(class_=re.compile(r"key_facts|headline_values|row", re.I))
        if facts_container:
            for item in facts_container.find_all(class_=re.compile(r"col-", re.I)):
                text = item.get_text(separator=" ", strip=True)
                if text:
                    key_facts[f"fact_{len(key_facts)}"] = text

        # 3. Multi-section descriptions: Zimmer, Lage, WG-Leben, Sonstiges
        description_parts: List[str] = []
        for i in range(5):
            section = soup.find(id=f"freitext_{i}") or soup.find(id=f"freitext_content_{i}")
            if section:
                header = section.find_previous(["h3", "h4"])
                header_text = header.get_text(strip=True) if header else ""
                body_text = section.get_text(separator="\n", strip=True)
                if header_text:
                    description_parts.append(f"### {header_text}\n{body_text}")
                else:
                    description_parts.append(body_text)

        # Fallback if freitext IDs are not present
        if not description_parts:
            general_desc = soup.find(id="ad_description_text") or soup.find(class_="section_panel")
            if general_desc:
                description_parts.append(general_desc.get_text(separator="\n", strip=True))
            else:
                meta_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
                if meta_desc and meta_desc.get("content"):
                    description_parts.append(meta_desc["content"].strip())

        full_description = "\n\n".join(description_parts) if description_parts else None

        # 4. Amenities / Details list
        amenities: List[str] = []
        tags_container = soup.find(class_=re.compile(r"tag_container|angaben", re.I))
        if tags_container:
            for tag in tags_container.find_all(["span", "li"]):
                tag_text = tag.get_text(strip=True)
                if tag_text:
                    amenities.append(tag_text)

        return ExtractedPage(
            submitted_url=url,
            final_url=url,
            site_name="WG-Gesucht",
            title=title,
            description=full_description or (title if title else None),
            main_text=full_description,
            metadata={
                "key_facts": key_facts,
                "amenities": amenities,
                "adapter": "WgGesuchtAdapter",
            },
            extraction_method="site_adapter",
            warnings=warnings,
        )
