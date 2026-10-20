import ipaddress
import socket
from typing import List, Optional
from urllib.parse import urlparse

from app.core.config import settings


class URLSecurityError(Exception):
    """Base exception for URL security and SSRF validation errors."""
    def __init__(self, message: str, code: str = "invalid_url"):
        super().__init__(message)
        self.code = code


def is_ip_disallowed(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Checks if an IP is private, loopback, link-local, multicast, or reserved."""
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        # Cloud metadata service protection (AWS, GCP, Azure, DigitalOcean)
        or str(ip) in {"169.254.169.254", "169.254.170.2"}
    )


def validate_url(url: str, allowed_hosts: Optional[List[str]] = None) -> str:
    """
    Validates a URL against SSRF threats, malicious schemes, embedded credentials,
    and host allowlists.

    Returns the normalized URL string if valid, or raises URLSecurityError.
    """
    if not url or not isinstance(url, str):
        raise URLSecurityError("URL cannot be empty.", code="invalid_url")

    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise URLSecurityError(f"Malformed URL: {exc}", code="invalid_url") from exc

    # 1. Scheme validation
    if parsed.scheme.lower() not in {"http", "https"}:
        raise URLSecurityError(
            f"Unsupported scheme '{parsed.scheme}'. Only http and https are allowed.",
            code="invalid_scheme",
        )

    # 2. Reject embedded credentials (user:pass@host)
    if parsed.username or parsed.password:
        raise URLSecurityError(
            "URLs with embedded credentials are not allowed.",
            code="credentials_not_allowed",
        )

    hostname = parsed.hostname
    if not hostname:
        raise URLSecurityError("URL must include a valid hostname.", code="missing_host")

    hostname_lower = hostname.lower()

    # Block well-known internal hostnames
    if hostname_lower in {"localhost", "127.0.0.1", "::1", "db", "api", "postgres", "redis"}:
        raise URLSecurityError(
            f"Access to internal host '{hostname}' is blocked.",
            code="blocked_destination",
        )

    # 3. Host allowlist check
    active_allowed_hosts = allowed_hosts if allowed_hosts is not None else settings.SCRAPER_ALLOWED_HOSTS
    if active_allowed_hosts:
        is_allowed = False
        for allowed in active_allowed_hosts:
            allowed_clean = allowed.lower().lstrip(".")
            if hostname_lower == allowed_clean or hostname_lower.endswith(f".{allowed_clean}"):
                is_allowed = True
                break
        if not is_allowed:
            raise URLSecurityError(
                f"Domain '{hostname}' is not in the allowed list of scraping sources.",
                code="unsupported_domain",
            )

    # 4. Resolve DNS and inspect resolved IP addresses (SSRF protection)
    # Check if the hostname itself is a raw IP literal
    try:
        ip_obj = ipaddress.ip_address(hostname_lower)
        if is_ip_disallowed(ip_obj):
            raise URLSecurityError(
                f"Direct IP target '{hostname}' is restricted.",
                code="blocked_destination",
            )
    except ValueError:
        # Hostname is a domain name, resolve via DNS
        try:
            addr_info = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            raise URLSecurityError(
                f"Could not resolve host '{hostname}'.",
                code="dns_resolution_failed",
            ) from exc

        for entry in addr_info:
            sockaddr = entry[4]
            ip_str = sockaddr[0]
            try:
                ip_addr = ipaddress.ip_address(ip_str)
                if is_ip_disallowed(ip_addr):
                    raise URLSecurityError(
                        f"Resolved IP '{ip_str}' for host '{hostname}' is in a private or restricted network.",
                        code="blocked_destination",
                    )
            except ValueError:
                continue

    return url
