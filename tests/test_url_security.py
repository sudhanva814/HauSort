import pytest
from app.core.url_security import URLSecurityError, validate_url


def test_valid_allowed_urls():
    url = "https://www.wg-gesucht.de/wg-zimmer-in-Trier.12345.html"
    validated = validate_url(url, allowed_hosts=["wg-gesucht.de", "www.wg-gesucht.de"])
    assert validated == url


def test_reject_unsupported_scheme():
    with pytest.raises(URLSecurityError) as exc:
        validate_url("ftp://example.com/file")
    assert exc.value.code == "invalid_scheme"

    with pytest.raises(URLSecurityError) as exc:
        validate_url("file:///etc/passwd")
    assert exc.value.code == "invalid_scheme"


def test_reject_embedded_credentials():
    with pytest.raises(URLSecurityError) as exc:
        validate_url("https://user:password@example.com/listing")
    assert exc.value.code == "credentials_not_allowed"


def test_reject_unsupported_domain():
    with pytest.raises(URLSecurityError) as exc:
        validate_url("https://malicious-site.com/ad", allowed_hosts=["wg-gesucht.de"])
    assert exc.value.code == "unsupported_domain"


def test_reject_internal_and_loopback_hosts():
    for blocked_target in [
        "http://localhost:8000/internal",
        "http://127.0.0.1:5432",
        "http://169.254.169.254/latest/meta-data/",
    ]:
        with pytest.raises(URLSecurityError):
            validate_url(blocked_target, allowed_hosts=["localhost", "127.0.0.1", "169.254.169.254"])
