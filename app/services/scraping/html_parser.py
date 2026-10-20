import json
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from app.schemas.scraping import ExtractedPage


class HTMLParser:
    """
    Extracts structured metadata, JSON-LD, Open Graph properties, and clean text
    from raw HTML using BeautifulSoup and lxml.
    """

    def parse(self, html: str, url: str) -> ExtractedPage:
        warnings: List[str] = []
        soup = BeautifulSoup(html, "lxml")

        # 1. Extract JSON-LD structured data
        json_ld_data = self._extract_json_ld(soup, warnings)

        # 2. Extract Open Graph & Meta tags
        meta_tags = self._extract_meta_tags(soup)

        # 3. Extract Document Title
        title = self._extract_title(soup, meta_tags, json_ld_data)

        # 4. Extract Description / Main Text
        description, extraction_method = self._extract_description(
            soup, meta_tags, json_ld_data
        )

        site_name = (
            meta_tags.get("og:site_name")
            or json_ld_data.get("publisher_name")
            or meta_tags.get("application-name")
        )

        canonical_url = meta_tags.get("og:url") or meta_tags.get("canonical") or url

        # Aggregate metadata
        metadata: Dict[str, Any] = {
            "canonical_url": canonical_url,
            "meta_tags": meta_tags,
            "json_ld": json_ld_data.get("raw"),
        }

        # 5. Extract general visible body text (cleaned of nav/footer/scripts)
        main_text = self._extract_clean_body_text(soup)

        return ExtractedPage(
            submitted_url=url,
            final_url=canonical_url,
            site_name=site_name,
            title=title,
            description=description or main_text[:500] if main_text else None,
            main_text=main_text,
            metadata=metadata,
            extraction_method=extraction_method,
            warnings=warnings,
        )

    # TODO: UNDERSTAND AND REVIEW
    def _extract_json_ld(self, soup: BeautifulSoup, warnings: List[str]) -> Dict[str, Any]:
        """Parses <script type='application/ld+json'> tags looking for real estate or product schemas."""
        relevant_data: Dict[str, Any] = {}
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            if not script.string:
                continue
            try:
                data = json.loads(script.string.strip())
                # Normalize to list of items
                items = data if isinstance(data, list) else [data]
                if isinstance(data, dict) and "@graph" in data:
                    items = data["@graph"]

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    item_type = str(item.get("@type", "")).lower()
                    # Check for housing or real estate schemas
                    if any(kw in item_type for kw in ["apartment", "residence", "realestate", "accommodation", "product", "houselisting"]):
                        relevant_data["title"] = item.get("name") or item.get("headline")
                        relevant_data["description"] = item.get("description")
                        relevant_data["raw"] = item
                        if "publisher" in item and isinstance(item["publisher"], dict):
                            relevant_data["publisher_name"] = item["publisher"].get("name")
                        return relevant_data
                    # If general webpage, keep description if not yet found
                    if "description" in item and "description" not in relevant_data:
                        relevant_data["description"] = item["description"]
                        relevant_data["raw"] = item
            except Exception as exc:
                warnings.append(f"Failed to parse JSON-LD block: {exc}")

        return relevant_data

    def _extract_meta_tags(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extracts og:, twitter:, and standard metadata properties."""
        meta_dict: Dict[str, str] = {}
        for tag in soup.find_all("meta"):
            name = tag.get("name") or tag.get("property")
            content = tag.get("content")
            if name and content:
                meta_dict[name.strip().lower()] = content.strip()

        # Check canonical link
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            meta_dict["canonical"] = canonical["href"].strip()

        return meta_dict

    def _extract_title(
        self,
        soup: BeautifulSoup,
        meta_tags: Dict[str, str],
        json_ld: Dict[str, Any],
    ) -> Optional[str]:
        """Priority: JSON-LD title -> og:title -> h1 -> <title> tag."""
        if json_ld.get("title"):
            return self._clean_text(str(json_ld["title"]))

        if meta_tags.get("og:title"):
            return self._clean_text(meta_tags["og:title"])

        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            return self._clean_text(h1.get_text(strip=True))

        if soup.title and soup.title.string:
            return self._clean_text(soup.title.string)

        return None

    def _extract_description(
        self,
        soup: BeautifulSoup,
        meta_tags: Dict[str, str],
        json_ld: Dict[str, Any],
    ) -> tuple[Optional[str], str]:
        """Finds main description and records provenance."""
        if json_ld.get("description"):
            return self._clean_text(str(json_ld["description"])), "json_ld"

        if meta_tags.get("og:description"):
            return self._clean_text(meta_tags["og:description"]), "og_description"

        if meta_tags.get("description"):
            return self._clean_text(meta_tags["description"]), "meta_description"

        # Search for typical description class or id
        desc_el = soup.find(class_=re.compile(r"description|freitext|ad-details", re.I))
        if desc_el:
            return self._clean_text(desc_el.get_text(separator=" ", strip=True)), "html_selector"

        return None, "html_soup"

    def _extract_clean_body_text(self, soup: BeautifulSoup) -> str:
        """Strips scripts, styling, navigation, headers, and footers to produce clean content."""
        # Work on a clone so we don't alter original soup if reused
        clone = BeautifulSoup(str(soup), "lxml")
        for tag in clone(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "form"]):
            tag.decompose()

        body = clone.body or clone
        text = body.get_text(separator="\n", strip=True)
        return self._clean_text(text)

    @staticmethod
    def _clean_text(text: str) -> str:
        """Removes excessive newlines and whitespace."""
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()
