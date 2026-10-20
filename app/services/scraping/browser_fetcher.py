import logging
from typing import Optional

from app.core.config import settings
from app.core.url_security import URLSecurityError, validate_url
from app.services.scraping.fetcher import FetchResult

logger = logging.getLogger(__name__)


class BrowserFetcher:
    """
    Optional headless browser fetcher using Playwright for JavaScript-heavy listings.
    Only invoked when SCRAPER_BROWSER_FALLBACK_ENABLED is True and static HTML is insufficient.
    """

    def __init__(self, timeout_seconds: Optional[int] = None):
        self.timeout_seconds = timeout_seconds or settings.SCRAPER_BROWSER_TIMEOUT_SECONDS

    async def fetch(self, url: str) -> FetchResult:
        if not settings.SCRAPER_BROWSER_FALLBACK_ENABLED:
            return FetchResult(
                html="",
                final_url=url,
                status_code=0,
                duration_ms=0,
                response_size=0,
                success=False,
                error_code="browser_disabled",
                error_message="Browser-based rendering fallback is currently disabled.",
            )

        try:
            validated_url = validate_url(url)
        except URLSecurityError as exc:
            return FetchResult(
                html="",
                final_url=url,
                status_code=0,
                duration_ms=0,
                response_size=0,
                success=False,
                error_code=exc.code,
                error_message=str(exc),
            )

        try:
            # pyrefly: ignore [missing-import]
            from playwright.async_api import async_playwright
        except ImportError:
            return FetchResult(
                html="",
                final_url=url,
                status_code=0,
                duration_ms=0,
                response_size=0,
                success=False,
                error_code="playwright_not_installed",
                error_message="Playwright is not installed in the current environment.",
            )

        import time
        start_time = time.perf_counter()
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
                )
                context = await browser.new_context(
                    user_agent=settings.SCRAPER_USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                )
                page = await context.new_page()

                # Block subresources like media, fonts, images to minimize bandwidth and SSRF surface
                await page.route(
                    "**/*",
                    lambda route: route.abort()
                    if route.request.resource_type in ["image", "media", "font", "stylesheet"]
                    else route.continue_(),
                )

                response = await page.goto(
                    validated_url,
                    timeout=self.timeout_seconds * 1000,
                    wait_until="domcontentloaded",
                )
                content = await page.content()
                final_url = page.url
                status_code = response.status if response else 200

                await browser.close()
                duration_ms = (time.perf_counter() - start_time) * 1000

                return FetchResult(
                    html=content,
                    final_url=final_url,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    response_size=len(content.encode("utf-8")),
                    success=True,
                )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return FetchResult(
                html="",
                final_url=url,
                status_code=0,
                duration_ms=duration_ms,
                response_size=0,
                success=False,
                error_code="browser_fetch_failed",
                error_message=f"Browser execution failed: {exc}",
            )
