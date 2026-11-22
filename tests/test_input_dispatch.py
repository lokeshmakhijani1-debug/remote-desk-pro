import sys
import types

import pytest
from fastapi.testclient import TestClient

from agent import host_agent
from backend.main import app, validate_control, validate_text_event


class FakePyAutoGUI(types.ModuleType):
    KEYBOARD_KEYS = {
        "enter", "esc", "tab", "backspace", "delete", "space", "up", "down",
        "left", "right", "shift", "ctrl", "alt", "win", "home", "end",
        "pageup", "pagedown",
    }

    def __init__(self):
        super().__init__("pyautogui")
        self.FAILSAFE = True
        self.calls = []

    def size(self):
        return types.SimpleNamespace(width=1920, height=1080)

    def moveTo(self, *args, **kwargs):
        self.calls.append(("moveTo", args, kwargs))

    def mouseDown(self, **kwargs):
        self.calls.append(("mouseDown", kwargs))

    def mouseUp(self, **kwargs):
        self.calls.append(("mouseUp", kwargs))

    def keyDown(self, *args, **kwargs):
        self.calls.append(("keyDown", args, kwargs))

    def keyUp(self, *args, **kwargs):
        self.calls.append(("keyUp", args, kwargs))

    def hotkey(self, *args, **kwargs):
        self.calls.append(("hotkey", args, kwargs))

    def scroll(self, *args, **kwargs):
        self.calls.append(("scroll", args, kwargs))

    def hscroll(self, *args, **kwargs):
        self.calls.append(("hscroll", args, kwargs))

    def write(self, *args, **kwargs):
        self.calls.append(("write", args, kwargs))

    def press(self, *args, **kwargs):
        self.calls.append(("press", args, kwargs))

    def hotkey(self, *args, **kwargs):
        self.calls.append(("hotkey", args, kwargs))


@pytest.fixture
def fake_pyautogui(monkeypatch):
    fake = FakePyAutoGUI()
    class FakeCapture:
        monitors = [{}, {"left": 0, "top": 0, "width": 3840, "height": 2160}]
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    fake_mss = types.ModuleType("mss")
    fake_mss.mss = lambda: FakeCapture()
    monkeypatch.setitem(sys.modules, "mss", fake_mss)
    class FakeCapture:
        monitors = [{}, {"left": 0, "top": 0, "width": 3840, "height": 2160}]
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    class FakeMSS(types.ModuleType):
        def __init__(self):
            super().__init__("mss")
        def mss(self):
            return FakeCapture()
    monkeypatch.setitem(sys.modules, "mss", FakeMSS())
    monkeypatch.setitem(sys.modules, "pyautogui", fake)
    host_agent._PRESSED_KEYS.clear()
    host_agent._PRESSED_MOUSE_BUTTONS.clear()
    host_agent._PRIMARY_CAPTURE_SIZE = None
    class FakeUser32:
        def __init__(self):
            self.calls = []
            self.mouse_event = lambda *args: self.calls.append(args)
    native = FakeUser32()
    monkeypatch.setattr(host_agent.ctypes, "WinDLL", lambda *_args, **_kwargs: native, raising=False)
    fake.native_user32 = native
    return fake


def test_mouse_move_maps_normalized_coordinates_to_primary_monitor(fake_pyautogui):
    assert host_agent.apply_control({"event": "mouse_move", "x": 0.5, "y": 0.25})
    assert fake_pyautogui.FAILSAFE is False
    assert fake_pyautogui.calls[-1] == ("moveTo", (960, 270), {"_pause": False})


def test_mouse_click_dispatches_real_button_down_and_up(fake_pyautogui):
    host_agent.apply_control({"event": "mouse_down", "button": 0})
    host_agent.apply_control({"event": "mouse_up", "button": 0})
    assert fake_pyautogui.calls == [
        ("mouseDown", {"button": "left"}),
        ("mouseUp", {"button": "left"}),
    ]


def test_keyboard_modifier_lifecycle_uses_down_and_up(fake_pyautogui):
    host_agent.apply_control({"event": "key_down", "key": "Control"})
    host_agent.apply_control({"event": "key_down", "key": "a"})
    host_agent.apply_control({"event": "key_up", "key": "a"})
    host_agent.apply_control({"event": "key_up", "key": "Control"})
    assert [call[0:2] for call in fake_pyautogui.calls] == [
        ("keyDown", ("ctrl",)), ("keyDown", ("a",)),
        ("keyUp", ("a",)), ("keyUp", ("ctrl",)),
    ]


def test_text_input_uses_clipboard_and_pastes_into_focused_host(fake_pyautogui, monkeypatch):
    clipboard = {"text": ""}
    fake_clipboard = types.ModuleType("pyperclip")
    fake_clipboard.copy = lambda value: clipboard.update(text=value)
    monkeypatch.setitem(sys.modules, "pyperclip", fake_clipboard)
    assert host_agent.apply_control({"event": "text_input", "text": "mobile typing"})
    assert clipboard["text"] == "mobile typing"
    assert fake_pyautogui.calls[-1] == ("hotkey", ("ctrl", "v"), {"_pause": False})


def test_mouse_wheel_dispatches_vertical_and_horizontal_scroll(fake_pyautogui):
    host_agent.apply_control({"event": "mouse_scroll", "deltaX": 120, "deltaY": -240})
    assert ("scroll", (2,), {"_pause": False}) in fake_pyautogui.calls
    assert fake_pyautogui.native_user32.calls
    assert fake_pyautogui.native_user32.calls[-1][0] == 0x01000
    assert fake_pyautogui.native_user32.calls[-1][3] == 120


def test_disconnect_releases_held_inputs(fake_pyautogui):
    host_agent.apply_control({"event": "key_down", "key": "shift"})
    host_agent.apply_control({"event": "mouse_down", "button": 2})
    host_agent.release_all_inputs()
    assert ("keyUp", ("shift",), {"_pause": False}) in fake_pyautogui.calls
    assert ("mouseUp", {"button": "right"}) in fake_pyautogui.calls
    assert not host_agent._PRESSED_KEYS
    assert not host_agent._PRESSED_MOUSE_BUTTONS


def test_invalid_input_is_rejected(fake_pyautogui):
    assert host_agent.apply_control({"event": "invalid"}) is False


@pytest.mark.parametrize("event", [
    {"event": "mouse_move", "x": 0.5, "y": 0.5},
    {"event": "mouse_down", "button": 0},
    {"event": "mouse_up", "button": 2},
    {"event": "key_down", "key": "Control"},
    {"event": "key_up", "key": "a"},
    {"event": "text_input", "text": "mobile text"},
    {"event": "mouse_scroll", "deltaX": 0, "deltaY": 120},
])
def test_backend_accepts_supported_control_events(event):
    assert validate_control(event)


@pytest.mark.parametrize("event", [
    {"event": "mouse_move", "x": 2, "y": 0},
    {"event": "mouse_move", "x": float("nan"), "y": 0},
    {"event": "mouse_down", "button": 8},
    {"event": "key_down", "key": ""},
    {"event": "text_input", "text": "x" * 4097},
    {"event": "mouse_scroll", "deltaY": float("inf")},
])
def test_backend_rejects_invalid_control_events(event):
    assert not validate_control(event)


def test_public_agent_download_serves_standalone_executable():
    with TestClient(app) as client:
        response = client.get("/download/agent")
    assert response.status_code == 200
    assert "attachment; filename=\"RemoteDeskPro-Agent.exe\"" in response.headers["content-disposition"]
    assert response.headers["content-type"] == "application/vnd.microsoft.portable-executable"
    assert len(response.content) > 10_000_000


@pytest.mark.parametrize("event", [
    {"type": "text", "text": "alpha123"},
    {"type": "text", "text": "हिन्दी"},
    {"type": "text", "text": " ", "key": None},
    {"type": "text", "text": "", "key": "Enter"},
    {"type": "text", "text": "", "key": "Backspace"},
    {"type": "text", "text": "", "key": "Tab"},
    {"type": "text", "text": "", "key": "Escape"},
])
def test_backend_accepts_mobile_text_schema(event):
    assert validate_text_event(event)


@pytest.mark.parametrize("event", [
    {"type": "text", "text": ""},
    {"type": "text", "text": "", "key": "Win"},
    {"type": "text", "text": "x" * 2049},
    {"type": "text", "text": "\x01"},
    {"type": "text", "text": 123},
])
def test_backend_rejects_invalid_mobile_text_schema(event):
    assert not validate_text_event(event)


def test_mobile_text_ascii_uses_pyautogui_write(fake_pyautogui, monkeypatch):
    monkeypatch.setattr(host_agent, "_focus_target_at_cursor", lambda: True)
    assert host_agent.apply_text({"type": "text", "text": "RDP123"})
    assert fake_pyautogui.calls == [("write", ("RDP123",), {"interval": 0.01})]


def test_mobile_text_unicode_uses_clipboard_paste(fake_pyautogui, monkeypatch):
    copied = []
    clipboard = types.ModuleType("pyperclip")
    clipboard.copy = copied.append
    monkeypatch.setitem(sys.modules, "pyperclip", clipboard)
    monkeypatch.setattr(host_agent, "_focus_target_at_cursor", lambda: True)
    assert host_agent.apply_text({"type": "text", "text": "नमस्ते"})
    assert copied == ["नमस्ते"]
    assert fake_pyautogui.FAILSAFE is False
    assert fake_pyautogui.calls == [("hotkey", ("ctrl", "v"), {})]


def test_clipboard_direct_paste_uses_ctrl_v(fake_pyautogui, monkeypatch):
    copied = []
    clipboard = types.ModuleType("pyperclip")
    clipboard.copy = copied.append
    monkeypatch.setitem(sys.modules, "pyperclip", clipboard)
    monkeypatch.setattr(host_agent, "_focus_target_at_cursor", lambda: True)
    assert host_agent.paste_clipboard("paste this")
    assert copied == ["paste this"]
    assert fake_pyautogui.FAILSAFE is False
    assert fake_pyautogui.calls == [("hotkey", ("ctrl", "v"), {"_pause": False})]


def test_file_transfer_destination_is_downloads_and_never_overwrites(tmp_path, monkeypatch):
    monkeypatch.setattr(host_agent.Path, "home", classmethod(lambda cls: tmp_path))
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    existing = downloads / "report.txt"
    existing.write_text("keep", encoding="utf-8")
    destination = host_agent.downloads_destination("report.txt", "12345678-abcd")
    assert destination.parent == downloads
    assert destination.name == "report-12345678.txt"
    assert existing.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("event", [
    {"event": "privacy_screen", "enabled": True, "mode": "banner"},
    {"event": "privacy_screen", "enabled": False, "mode": "banner"},
])
def test_backend_accepts_visible_privacy_banner_control(event):
    assert validate_control(event)


def test_backend_rejects_hidden_or_unsupported_privacy_modes():
    assert not validate_control({"event": "privacy_screen", "enabled": True, "mode": "blank"})
    assert not validate_control({"event": "privacy_screen", "enabled": "yes", "mode": "banner"})


def test_clipboard_paste_sets_host_clipboard_and_sends_ctrl_v(fake_pyautogui, monkeypatch):
    clipboard = {"text": ""}
    fake_clipboard = types.ModuleType("pyperclip")
    fake_clipboard.copy = lambda value: clipboard.update(text=value)
    monkeypatch.setitem(sys.modules, "pyperclip", fake_clipboard)
    monkeypatch.setattr(host_agent, "_focus_target_at_cursor", lambda: True)
    assert host_agent.paste_clipboard("delivered from viewer")
    assert clipboard["text"] == "delivered from viewer"
    assert fake_pyautogui.calls == [("hotkey", ("ctrl", "v"), {"_pause": False})]


def test_downloads_destination_uses_remote_desk_pro_received_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(host_agent.Path, "home", classmethod(lambda cls: tmp_path))
    destination = host_agent.downloads_destination("report.pdf", "12345678-1234-1234-1234-123456789abc")
    assert destination == tmp_path / "Downloads" / "RemoteDeskPro-Received" / "report.pdf"
    assert destination.parent.is_dir()


def test_backend_accepts_both_privacy_screen_modes():
    assert validate_control({"event": "privacy_screen", "enabled": True, "mode": "black"})
    assert validate_control({"event": "privacy_screen", "enabled": True, "mode": "banner"})
    assert not validate_control({"event": "privacy_screen", "enabled": True, "mode": "hidden"})
