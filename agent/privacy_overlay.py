"""Visible privacy overlay with a best-effort global Windows emergency unlock."""

from __future__ import annotations

import ctypes
import os
import threading
import tkinter as tk
from ctypes import wintypes
from typing import Callable, Optional

WDA_EXCLUDEFROMCAPTURE = 0x00000011
SS_BLACKRECT = 0x00000004  # Win32 STATIC-control opaque-black fill style.
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
EMERGENCY_HOTKEY_ID = 0x5244
EMERGENCY_HOTKEY_MODIFIERS = 0x0002 | 0x0001 | 0x0004


class PrivacyBanner:
    """Manage a visible tkinter privacy overlay and emergency unlock shortcut."""

    def __init__(
        self,
        on_emergency_unlock: Optional[Callable[[], None]] = None,
        on_unlock: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        self._on_unlock = on_emergency_unlock or on_unlock
        self._active = False
        self._mode = "black"
        self._root = None
        self._hwnd = 0
        self._thread = None
        self._ready = threading.Event()
        self._stop_flag = threading.Event()
        self._stopped = self._stop_flag
        self._lock = threading.Lock()
        self._hotkey_thread = None
        self._hotkey_thread_id = None

    def start(self, mode: str = "black", **kwargs) -> bool:
        if os.name != "nt":
            return False
        with self._lock:
            self._mode = mode if mode in ("black", "banner") else "black"
            if self._active:
                return True
            self._active = True
            self._ready.clear()
            self._stop_flag.clear()
            self._thread = threading.Thread(target=self._run_tk, daemon=True)
            self._thread.start()
            if os.name == "nt":
                self._hotkey_thread = threading.Thread(
                    target=self._run_hotkey_listener,
                    name="privacy-emergency-hotkey",
                    daemon=True,
                )
                self._hotkey_thread.start()
        if not self._ready.wait(timeout=1.5):
            self.stop()
            return False
        return self._active

    def enable(self, mode: str = "black", **kwargs) -> bool:
        return self.start(mode=mode, **kwargs)

    def show(self, mode: str = "black", **kwargs) -> bool:
        return self.start(mode=mode, **kwargs)

    def _signal_hotkey_stop(self) -> None:
        thread_id = self._hotkey_thread_id
        if thread_id is None or os.name != "nt":
            return
        try:
            ctypes.windll.user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)
        except Exception:
            pass

    def stop(self) -> bool:
        with self._lock:
            if not self._active:
                self._stop_flag.set()
                self._signal_hotkey_stop()
                return False
            self._active = False
            self._stop_flag.set()
            root = self._root
            self._root = None
            self._hwnd = 0
        self._signal_hotkey_stop()
        if root is not None:
            try:
                root.after(0, root.destroy)
            except Exception:
                try:
                    root.destroy()
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
        return "break"

    def _run_hotkey_listener(self) -> None:
        """Register and process the global shortcut on its own Win32 message thread."""
        if os.name != "nt":
            return

        user32 = None
        registered = False
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            self._hotkey_thread_id = int(kernel32.GetCurrentThreadId())

            # Force creation of this thread's message queue before stop() can post WM_QUIT.
            msg = wintypes.MSG()
            user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
            if self._stop_flag.is_set():
                return

            registered = bool(user32.RegisterHotKey(None, 0x5244, 0x0002 | 0x0001 | 0x0004, ord("U")))
            if not registered:
                return

            while not self._stop_flag.is_set():
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result <= 0:
                    break
                if msg.message == 0x0312 and msg.wParam == 0x5244:
                    self._stop_flag.set()
                    self._trigger_unlock()
                    break
        except Exception:
            # The overlay remains usable if the OS, desktop, or shortcut API is unavailable.
            pass
        finally:
            if registered and user32 is not None:
                try:
                    user32.UnregisterHotKey(None, 0x5244)
                except Exception:
                    pass
            self._hotkey_thread_id = None

    def _run_tk(self) -> None:
        root = None
        try:
            root = tk.Tk()
            self._root = root
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.configure(bg="#000000")

            if os.name == "nt":
                try:
                    user32 = ctypes.windll.user32
                    vx = user32.GetSystemMetrics(76)
                    vy = user32.GetSystemMetrics(77)
                    vw = user32.GetSystemMetrics(78) or root.winfo_screenwidth()
                    vh = user32.GetSystemMetrics(79) or root.winfo_screenheight()
                    root.geometry(f"{vw}x{vh}+{vx}+{vy}")
                    root.update_idletasks()
                    try:
                        hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
                        self._hwnd = int(hwnd)
                        try:
                            user32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x0002)
                        except Exception:
                            pass
                        user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
                    except Exception:
                        pass
                except Exception:
                    root.geometry(
                        f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0"
                    )
            else:
                root.geometry(
                    f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0"
                )

            root.bind_all("<Control-Alt-Shift-U>", self._trigger_unlock)
            root.bind_all("<Control-Alt-Shift-u>", self._trigger_unlock)
            if os.name == "nt":
                try:
                    root.focus_force()
                except Exception:
                    pass
            self._ready.set()
            root.mainloop()
        except Exception:
            # Tk may be unavailable in headless sessions; never crash the host agent.
            self._stop_flag.set()
            self._signal_hotkey_stop()
        finally:
            self._ready.set()
            with self._lock:
                self._active = False
                self._root = None
                self._hwnd = 0
            self._stop_flag.set()
            self._signal_hotkey_stop()


PrivacyOverlayManager = PrivacyBanner
