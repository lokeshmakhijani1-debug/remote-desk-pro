import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import desktop_app

def test_windows_config_encrypts_and_roundtrips_credentials(tmp_path, monkeypatch):
    config_path = tmp_path / "RemoteDeskPro" / "config.json"
    monkeypatch.setattr(desktop_app, "CONFIG_FILE", config_path)
    monkeypatch.setattr(desktop_app, "APP_DIR", config_path.parent)
    values = {
        "server": "https://example.invalid",
        "device_id": "123456789",
        "device_secret": "agent-secret-test",
        "access_token": "jwt-test-token",
        "dynamic_password": "654321",
    }
    desktop_app.save_config(values)
    raw = config_path.read_text(encoding="utf-8")
    assert "agent-secret-test" not in raw
    assert "jwt-test-token" not in raw
    assert "654321" not in raw
    assert desktop_app.load_config() == values
