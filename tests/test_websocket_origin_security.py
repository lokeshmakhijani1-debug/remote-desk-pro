from backend.config import settings
from backend.main import websocket_origin_allowed


def test_websocket_origin_accepts_configured_frontend_origin():
    assert websocket_origin_allowed("http://localhost:5173")


def test_websocket_origin_rejects_untrusted_or_non_web_origins():
    assert not websocket_origin_allowed("https://attacker.invalid")
    assert not websocket_origin_allowed("file:///etc/passwd")
    assert not websocket_origin_allowed("http://localhost:5173/evil")
    assert not websocket_origin_allowed("http://user:pass@localhost:5173")


def test_websocket_origin_allows_native_clients_without_origin_header():
    assert websocket_origin_allowed(None)
    assert websocket_origin_allowed("")


def test_websocket_origin_accepts_configured_public_api_origin():
    assert websocket_origin_allowed(settings.public_base_url)
