from pathlib import Path


def test_zap_baseline_keeps_security_findings_at_default_warn_and_info_classifies_only_observations():
    config = (Path(__file__).resolve().parents[1] / "zap-baseline.conf").read_text(encoding="utf-8")
    assert "10015\tINFO\t" in config
    assert "10049\tINFO\t" in config
    assert "10109\tINFO\t" in config
    assert "10020\tFAIL\t" not in config
    assert "10021\tFAIL\t" not in config
