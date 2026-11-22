import hashlib
import json
import sys
import time
import types
from pathlib import Path

from agent import privacy_overlay
from agent.privacy_overlay import PrivacyBanner
from agent.session_recorder import SessionRecorder


def test_privacy_banner_is_disabled_off_windows():
    banner = PrivacyBanner()
    assert banner.start() is False
    banner.stop()


def test_session_recorder_writes_mp4_and_audit_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    class FakeWriter:
        def __init__(self, path):
            self.path = Path(path)
        def send(self, frame):
            if frame is not None:
                with self.path.open("ab") as stream:
                    stream.write(frame)
        def close(self):
            self.path.touch(exist_ok=True)

    class FakeCapture:
        monitors = [{}, {"left": 0, "top": 0, "width": 2, "height": 2}]
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def grab(self, _monitor):
            return types.SimpleNamespace(rgb=b"\x01" * 12)

    fake_mss = types.ModuleType("mss")
    fake_mss.mss = FakeCapture
    fake_ffmpeg = types.ModuleType("imageio_ffmpeg")
    fake_ffmpeg.write_frames = lambda path, *_args, **_kwargs: FakeWriter(path)
    monkeypatch.setitem(sys.modules, "mss", fake_mss)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", fake_ffmpeg)

    recorder = SessionRecorder("123456789", "42", fps=10)
    recorder.start()
    time.sleep(0.05)
    recorder.stop()

    assert recorder.path.exists()
    expected = hashlib.sha256(recorder.path.read_bytes()).hexdigest()
    assert recorder.sha256 == expected
    events = [json.loads(line) for line in recorder.audit_path.read_text(encoding="utf-8").splitlines()]
    assert [event["event"] for event in events] == ["session_started", "session_ended"]
    assert events[-1]["viewer_id"] == "42"
    assert events[-1]["sha256"] == expected


def test_privacy_banner_starts_and_stops_with_emergency_unlock_binding(monkeypatch):
    import threading

    stopped = threading.Event()
    class FakeRoot:
        def title(self, *_args): pass
        def overrideredirect(self, *_args): pass
        def attributes(self, *_args): pass
        def configure(self, **_kwargs): pass
        def winfo_screenwidth(self): return 1280
        def winfo_screenheight(self): return 720
        def geometry(self, *_args): pass
        def bind_all(self, *_args): pass
        def update_idletasks(self): pass
        def winfo_id(self): return 1234
        def grab_set(self): pass
        def focus_force(self): pass
        def mainloop(self): stopped.wait(2)
        def after(self, _delay, callback): callback()
        def destroy(self): stopped.set()

    class FakeWidget:
        def __init__(self, *_args, **_kwargs): pass
        def place(self, **_kwargs): pass
        def pack(self, **_kwargs): pass

    fake_tk = types.ModuleType("tkinter")
    fake_tk.Tk = FakeRoot
    fake_tk.Frame = FakeWidget
    fake_tk.Label = FakeWidget
    monkeypatch.setattr(privacy_overlay.os, "name", "nt")
    class FakeFunction:
        def __init__(self, callback):
            self.callback = callback
            self.restype = None
        def __call__(self, *args):
            return self.callback(*args)
    class FakeUser32:
        def __init__(self):
            self.GetAncestor = FakeFunction(lambda hwnd, _flags: hwnd)
            self.GetWindowLongW = FakeFunction(lambda *_args: 0)
            self.SetWindowLongW = FakeFunction(lambda *_args: 0)
            self.SetWindowPos = FakeFunction(lambda *_args: 1)
            self.SetWindowDisplayAffinity = FakeFunction(lambda *_args: 1)
            self.RegisterHotKey = FakeFunction(lambda *_args: 0)
    monkeypatch.setattr(privacy_overlay.ctypes, "WinDLL", lambda *_args, **_kwargs: FakeUser32(), raising=False)
    monkeypatch.setitem(sys.modules, "tkinter", fake_tk)

    banner = PrivacyBanner()
    assert banner.start() is True
    assert banner._thread is not None and banner._thread.is_alive()
    banner.stop()
    assert stopped.is_set()
    assert banner._stopped.is_set()
