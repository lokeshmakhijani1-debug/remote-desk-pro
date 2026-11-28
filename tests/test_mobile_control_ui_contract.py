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
    assert "Step preview (" in app
    assert 'function sendControl(data:Record<string,unknown>,force=false)' in app
    assert 'sendControl({event:"mouse_down",button:e.button,...p})' in app
    assert 'sendControl({event:"mouse_scroll",deltaX:e.deltaX,deltaY:e.deltaY})' in app


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
    assert '" privacy-enabled"' in app
    assert "background:#000" in css
    assert "SetLayeredWindowAttributes(hwnd, 0, 255" in overlay
    assert "0x00000004" in overlay  # SS_BLACKRECT


def test_mobile_viewer_toolbar_remains_visible_and_scrollable():
    css = (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
    assert ".viewer-head>div:last-child{display:none}" not in css
    assert ".viewer-head>div:last-child{display:flex;max-width:100%;overflow-x:auto;flex-wrap:nowrap" in css
    assert ".viewer-head>div:last-child>.tool{flex:0 0 auto;white-space:nowrap}" in css

 

def test_viewer_canvas_keeps_host_frame_aspect_ratio_without_fill_override():
    css = (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "object-fit:fill !important" not in css
    assert "max-width:100%!important;max-height:100%!important;object-fit:contain!important" in css
    assert "c.width=img.width;c.height=img.height" in app


def test_telemetry_hud_has_an_accessible_viewer_toggle():
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "telemetryHudVisible" in app
    assert 'aria-label="Toggle telemetry HUD"' in app
    assert "aria-pressed={telemetryHudVisible}" in app
    assert '{telemetryHudVisible&&<div className="telemetry-hud"' in app


def test_mobile_recording_download_waits_for_a_user_gesture_after_verification():
    app = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert 'setRecordingReady({filename:pending.filename,blob:new Blob([bytes],{type:"video/mp4"})})' in app
    assert "Save MP4 to this device" in app
    assert "function saveReadyRecording()" in app
    assert "anchor.click()" in app
