from agent.host_agent import is_unattended_auto_approve_enabled

def test_unattended_pin_default_and_enabled(monkeypatch, tmp_path):
    monkeypatch.delenv("RDP_UNATTENDED_PIN", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert is_unattended_auto_approve_enabled() is False
    monkeypatch.setenv("RDP_UNATTENDED_PIN", "123")
    assert is_unattended_auto_approve_enabled() is False
    monkeypatch.setenv("RDP_UNATTENDED_PIN", "2580")
    assert is_unattended_auto_approve_enabled() is True
