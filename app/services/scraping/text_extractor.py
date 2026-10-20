from typing import Optional
import trafilatura

from app.schemas.scraping import ExtractedPage


class TextExtractor:
    """
    Main-text fallback extractor using Trafilatura when standard HTML parsing
    returns noisy or insufficient content.
    """

    MIN_MEANINGFUL_TEXT_LENGTH = 120

    def should_use_fallback(self, page: ExtractedPage) -> bool:
        """Determines if the parsed page lacks sufficient descriptive content."""
        desc = page.description or ""
        main = page.main_text or ""
        return len(desc.strip()) < self.MIN_MEANINGFUL_TEXT_LENGTH and len(main.strip()) < self.MIN_MEANINGFUL_TEXT_LENGTH

    def extract_with_trafilatura(self, html: str, page: ExtractedPage) -> ExtractedPage:
        """
        Runs Trafilatura to extract readable main text and metadata from raw HTML,
        updating the ExtractedPage if higher quality text is recovered.
        """
        extracted_text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_precision=True,
        )

        if extracted_text and len(extracted_text.strip()) >= len(page.description or ""):
            page.main_text = extracted_text.strip()
            if not page.description or len(page.description.strip()) < self.MIN_MEANINGFUL_TEXT_LENGTH:
                page.description = extracted_text.strip()
            page.extraction_method = "trafilatura"

        # Trafilatura metadata extraction
        trafilatura_meta = trafilatura.extract_metadata(html)
        if trafilatura_meta:
            if not page.title and trafilatura_meta.title:
                page.title = trafilatura_meta.title.strip()
            if not page.site_name and trafilatura_meta.sitename:
                page.site_name = trafilatura_meta.sitename.strip()
            page.metadata["trafilatura_meta"] = {
                "author": trafilatura_meta.author,
                "date": trafilatura_meta.date,
                "sitename": trafilatura_meta.sitename,
                "categories": trafilatura_meta.categories,
            }

        return page
