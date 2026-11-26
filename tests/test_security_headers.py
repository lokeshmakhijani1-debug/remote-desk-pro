from fastapi.testclient import TestClient

from backend.main import app


EXPECTED_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(self), microphone=(self), display-capture=(self), geolocation=(), payment=(), usb=()",
    "content-security-policy": "frame-ancestors 'none'; object-src 'none'; base-uri 'self'",
}


def test_http_responses_include_security_headers_without_changing_payload():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    for name, value in EXPECTED_HEADERS.items():
        assert response.headers.get(name) == value


def test_hsts_is_only_added_for_https_requests():
    with TestClient(app, base_url="http://testserver") as client:
        plain = client.get("/")
    with TestClient(app, base_url="https://testserver") as client:
        secure = client.get("/")

    assert "strict-transport-security" not in plain.headers
    assert secure.headers.get("strict-transport-security") == "max-age=31536000"


def test_untrusted_forwarded_header_cannot_enable_hsts():
    with TestClient(app, base_url="http://testserver") as client:
        response = client.get("/", headers={"x-forwarded-proto": "https"})
    assert "strict-transport-security" not in response.headers
