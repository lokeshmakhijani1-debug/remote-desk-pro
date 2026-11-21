from backend.config import settings
from backend.security import issue_token, read_token

def test_dynamic_password_default_is_24_hours():
    assert settings.device_password_ttl_seconds >= 24 * 60 * 60

def test_account_token_lifetime_is_persistent_but_bounded():
    payload = read_token(issue_token("42", "technician"))
    assert payload["exp"] - payload["iat"] >= 29 * 24 * 60 * 60

def test_viewer_session_token_is_device_scoped_and_long_lived_for_reconnect():
    account_token = issue_token("42", "technician")
    viewer_token = issue_token("viewer:42:123456789", "technician", settings.session_ttl_seconds)
    assert read_token(account_token)["sub"] == "42"
    payload = read_token(viewer_token)
    assert payload["sub"] == "viewer:42:123456789"
    assert payload["exp"] - payload["iat"] >= 29 * 24 * 60 * 60
