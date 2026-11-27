from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_workspace_and_auth_screens_expose_semantic_landmarks():
    app = (ROOT / "frontend/src/App.tsx").read_text(encoding="utf-8")
    assert '<main className="auth-shell">' in app
    assert '<main className="main">' in app
    assert '<header>' in app
    assert '<nav className="workspace-nav" aria-label="Workspace navigation">' in app


def test_auth_and_remote_control_fields_have_explicit_names():
    app = (ROOT / "frontend/src/App.tsx").read_text(encoding="utf-8")
    for input_id in (
        "auth-email",
        "auth-password",
        "device-display-name",
        "partner-id",
        "partner-password",
    ):
        assert f'id="{input_id}"' in app
    assert 'aria-label="Email address"' in app
    assert 'aria-label="Password"' in app


def test_login_supporting_text_uses_wcag_aa_contrast_colors():
    css = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
    assert ".eyebrow { color: #53657a; }" in css
    assert ".auth-card p { color: #586a80; }" in css
    assert ".hint { color: #5f7086; }" in css
    assert ":focus-visible" in css
