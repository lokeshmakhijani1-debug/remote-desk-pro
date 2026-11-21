import sys
import types

import pytest
from fastapi.testclient import TestClient

from agent import host_agent
from backend.main import app, validate_control


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

    def scroll(self, *args, **kwargs):
        self.calls.append(("scroll", args, kwargs))

    def hscroll(self, *args, **kwargs):
        self.calls.append(("hscroll", args, kwargs))


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


def test_mouse_wheel_dispatches_vertical_and_horizontal_scroll(fake_pyautogui):
    host_agent.apply_control({"event": "mouse_scroll", "deltaX": 120, "deltaY": -240})
    assert ("scroll", (2,), {"_pause": False}) in fake_pyautogui.calls
    assert ("hscroll", (1,), {"_pause": False}) in fake_pyautogui.calls


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
    {"event": "mouse_scroll", "deltaX": 0, "deltaY": 120},
])
def test_backend_accepts_supported_control_events(event):
    assert validate_control(event)


@pytest.mark.parametrize("event", [
    {"event": "mouse_move", "x": 2, "y": 0},
    {"event": "mouse_move", "x": float("nan"), "y": 0},
    {"event": "mouse_down", "button": 8},
    {"event": "key_down", "key": ""},
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
