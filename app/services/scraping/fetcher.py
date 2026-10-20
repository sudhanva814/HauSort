import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin
import httpx

from app.core.config import settings
from app.core.url_security import URLSecurityError, validate_url


@dataclass
class FetchResult:
    """Encapsulates the raw HTTP fetch outcome."""
    html: str
    final_url: str
    status_code: int
    duration_ms: float
    response_size: int
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class HTTPXFetcher:
    """
    Secure HTTP fetcher for housing advertisements using HTTPX.
    Enforces SSRF validation on initial requests and redirects, bounds memory
    and response size, and respects configured timeouts.
    """

    def __init__(
        self,
        user_agent: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        max_response_bytes: Optional[int] = None,
        max_redirects: Optional[int] = None,
    ):
        self.user_agent = user_agent or settings.SCRAPER_USER_AGENT
        self.timeout_seconds = timeout_seconds or settings.SCRAPER_REQUEST_TIMEOUT_SECONDS
        self.max_response_bytes = max_response_bytes or settings.SCRAPER_MAX_RESPONSE_BYTES
        self.max_redirects = max_redirects or settings.SCRAPER_MAX_REDIRECTS

    async def fetch(self, url: str) -> FetchResult:
        start_time = time.perf_counter()
        current_url = url
        redirect_count = 0

        # Validate initial URL
        try:
            current_url = validate_url(current_url)
        except URLSecurityError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return FetchResult(
                html="",
                final_url=url,
                status_code=0,
                duration_ms=duration_ms,
                response_size=0,
                success=False,
                error_code=exc.code,
                error_message=str(exc),
            )

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        # Follow redirects manually to validate destination IPs and hosts at each step
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(self.timeout_seconds),
        ) as client:
            while True:
                try:
                    response = await client.get(current_url, headers=headers)
                except httpx.TimeoutException:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    return FetchResult(
                        html="",
                        final_url=current_url,
                        status_code=0,
                        duration_ms=duration_ms,
                        response_size=0,
                        success=False,
                        error_code="fetch_timeout",
                        error_message=f"Request to '{current_url}' timed out after {self.timeout_seconds}s.",
                    )
                except httpx.RequestError as exc:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    return FetchResult(
                        html="",
                        final_url=current_url,
                        status_code=0,
                        duration_ms=duration_ms,
                        response_size=0,
                        success=False,
                        error_code="http_error",
                        error_message=f"Network request error: {exc}",
                    )

                # Check for redirect status codes (301, 302, 303, 307, 308)
                if response.is_redirect:
                    redirect_count += 1
                    if redirect_count > self.max_redirects:
                        duration_ms = (time.perf_counter() - start_time) * 1000
                        return FetchResult(
                            html="",
                            final_url=current_url,
                            status_code=response.status_code,
                            duration_ms=duration_ms,
                            response_size=0,
                            success=False,
                            error_code="too_many_redirects",
                            error_message=f"Exceeded maximum allowed redirects ({self.max_redirects}).",
                        )

                    location = response.headers.get("Location")
                    if not location:
                        break

                    next_url = urljoin(current_url, location)
                    try:
                        current_url = validate_url(next_url)
                    except URLSecurityError as sec_exc:
                        duration_ms = (time.perf_counter() - start_time) * 1000
                        return FetchResult(
                            html="",
                            final_url=next_url,
                            status_code=response.status_code,
                            duration_ms=duration_ms,
                            response_size=0,
                            success=False,
                            error_code=sec_exc.code,
                            error_message=f"Redirect to '{next_url}' blocked: {sec_exc}",
                        )
                    continue
                else:
                    break

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Handle HTTP status errors
        if response.status_code in {401, 403}:
            return FetchResult(
                html="",
                final_url=current_url,
                status_code=response.status_code,
                duration_ms=duration_ms,
                response_size=len(response.content),
                success=False,
                error_code="access_restricted",
                error_message=f"Access denied (HTTP {response.status_code}). Please submit pasted listing text instead.",
            )
        elif response.status_code == 429:
            return FetchResult(
                html="",
                final_url=current_url,
                status_code=response.status_code,
                duration_ms=duration_ms,
                response_size=len(response.content),
                success=False,
                error_code="rate_limited",
                error_message="Rate limit reached on target site. Try again later or use pasted text.",
            )
        elif response.status_code >= 400:
            return FetchResult(
                html="",
                final_url=current_url,
                status_code=response.status_code,
                duration_ms=duration_ms,
                response_size=len(response.content),
                success=False,
                error_code="http_error",
                error_message=f"Server returned HTTP {response.status_code}.",
            )

        # Validate MIME type
        content_type = response.headers.get("content-type", "").lower()
        if not ("text/html" in content_type or "application/xhtml+xml" in content_type or content_type.startswith("text/")):
            return FetchResult(
                html="",
                final_url=current_url,
                status_code=response.status_code,
                duration_ms=duration_ms,
                response_size=len(response.content),
                success=False,
                error_code="non_html_response",
                error_message=f"Expected HTML response, but received '{content_type}'.",
            )

        # Enforce maximum response bytes
        content_bytes = response.content
        if len(content_bytes) > self.max_response_bytes:
            return FetchResult(
                html="",
                final_url=current_url,
                status_code=response.status_code,
                duration_ms=duration_ms,
                response_size=len(content_bytes),
                success=False,
                error_code="oversized_response",
                error_message=f"Response size ({len(content_bytes)} bytes) exceeds limit ({self.max_response_bytes} bytes).",
            )

        html_text = response.text
        return FetchResult(
            html=html_text,
            final_url=current_url,
            status_code=response.status_code,
            duration_ms=duration_ms,
            response_size=len(content_bytes),
            success=True,
        )
