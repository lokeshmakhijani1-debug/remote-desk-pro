from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_remote_dock_exposes_all_core_actions_and_workflow_panels():
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    for label in (
        "Mouse", "Right-click", "Scroll Up", "Scroll Down", "Virtual Keyboard",
        "Privacy", "Clipboard Sync", "File Transfer", "Fullscreen",
        "Start Recording", "V2 AI Replay", "Workflow Steps", "Community Library",
        "Recording Settings", "Disconnect", "Zoom In", "Zoom Out", "Reset Zoom",
    ):
        assert label in app
    assert 'function sendControl(data:Record<string,unknown>,force=false)' in app
    assert 'sendControl({event:"mouse_down",button:2,x:0.5,y:0.5},true)' in app
    assert 'sendControl({event:"mouse_scroll",deltaX:0,deltaY:-420},true)' in app


def test_remote_viewer_uses_safe_dynamic_viewport_and_rotation_observer():
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
    assert "new ResizeObserver(refit)" in app
    assert 'addEventListener("orientationchange",refit' in app
    assert "100dvh" in css and "100dvw" in css
    assert "z-index:9999" in css
    assert "env(safe-area-inset-bottom)" in css


def test_privacy_preview_and_native_overlay_are_pure_black():
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
    overlay = (ROOT / "agent" / "privacy_overlay.py").read_text(encoding="utf-8")
    assert '"privacy-enabled"' in app
    assert "background:#000" in css
    assert "SetLayeredWindowAttributes(hwnd, 0, 255" in overlay
    assert "0x00000004" in overlay  # SS_BLACKRECT
