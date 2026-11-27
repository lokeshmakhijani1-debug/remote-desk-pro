import ctypes
import threading
import tkinter as tk
from typing import Callable, Optional

WDA_EXCLUDEFROMCAPTURE = 0x00000011

class PrivacyBanner:
    def __init__(self, on_emergency_unlock: Optional[Callable[[], None]] = None, on_unlock: Optional[Callable[[], None]] = None, **kwargs):
        self._on_unlock = on_emergency_unlock or on_unlock
        self._active = False
        self._mode = 'black'
        self._root = None
        self._hwnd = 0
        self._thread = None
        self._ready = threading.Event()
        self._lock = threading.Lock()

    def start(self, mode: str = 'black', **kwargs) -> bool:
        with self._lock:
            self._mode = mode if mode in ('black', 'banner') else 'black'
            if self._active:
                return True
            self._active = True
            self._ready.clear()
            self._thread = threading.Thread(target=self._run_tk, daemon=True)
            self._thread.start()
        self._ready.wait(timeout=1.5)
        return True

    def enable(self, mode: str = 'black', **kwargs) -> bool:
        return self.start(mode=mode, **kwargs)

    def show(self, mode: str = 'black', **kwargs) -> bool:
        return self.start(mode=mode, **kwargs)

    def stop(self) -> bool:
        with self._lock:
            if not self._active:
                return False
            self._active = False
            r = self._root
            self._root = None
            self._hwnd = 0
        if r is not None:
            try:
                r.after(0, r.destroy)
            except Exception:
                pass
        return True

    def disable(self) -> bool:
        return self.stop()

    def hide(self) -> bool:
        return self.stop()

    def close(self) -> bool:
        return self.stop()

    def is_enabled(self) -> bool:
        return self._active

    @property
    def active(self) -> bool:
        return self._active

    @property
    def hwnd(self) -> int:
        return self._hwnd

    def _trigger_unlock(self, _event=None):
        self.stop()
        if self._on_unlock:
            try:
                self._on_unlock()
            except Exception:
                pass

    def _run_tk(self):
        try:
            root = tk.Tk()
            self._root = root
            root.overrideredirect(True)
            root.attributes('-topmost', True)
            root.configure(bg='#000000')
            user32 = ctypes.windll.user32
            vx = user32.GetSystemMetrics(76)
            vy = user32.GetSystemMetrics(77)
            vw = user32.GetSystemMetrics(78) or root.winfo_screenwidth()
            vh = user32.GetSystemMetrics(79) or root.winfo_screenheight()
            root.geometry(f'{vw}x{vh}+{vx}+{vy}')
            root.update_idletasks()
            try:
                hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
                self._hwnd = int(hwnd)
                user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
            except Exception:
                pass
            root.bind('<Control-Alt-Shift-U>', self._trigger_unlock)
            root.bind('<Control-Alt-Shift-u>', self._trigger_unlock)
            root.focus_force()
            self._ready.set()
            root.mainloop()
        except Exception:
            self._ready.set()

PrivacyOverlayManager = PrivacyBanner
