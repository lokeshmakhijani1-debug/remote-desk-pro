from agent.telemetry import TelemetryTracker

def test_telemetry_exposes_fps_ping_and_transfer_rates():
    t=TelemetryTracker();t.frame_sent(1024);t.transfer_sent(4096);t.transfer_received(2048);t.set_ping(38)
    s=t.snapshot()
    assert s["fps"]>=0 and s["ping_ms"]==38
    assert s["upload_kbps"]>=0 and s["download_kbps"]>=0

def test_missing_ping_is_null():
    assert TelemetryTracker().snapshot()["ping_ms"] is None
