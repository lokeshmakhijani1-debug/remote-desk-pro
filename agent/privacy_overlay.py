"""Native Win32 reversible privacy curtain for an approved remote session."""
from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes


class PrivacyBanner:
    """Topmost click-through Win32 black curtain excluded from screen capture."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._hwnd: int | None = None
        self._ready = threading.Event()
        self._stop_flag = threading.Event()
        self._stopped = threading.Event()
        self._error: BaseException | None = None
        self._mode = "black"

    def start(self, mode: str = "black") -> bool:
        if os.name != "nt":
            return False
        if mode not in {"black", "banner"}:
            mode = "black"
        if self._thread and self._thread.is_alive():
            if self._mode == mode:
                return True
            self.stop()
        self._mode = mode
        self._ready.clear()
        self._stop_flag.clear()
        self._stopped.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name="rdp-win32-privacy", daemon=True)
        self._thread.start()
        if not self._ready.wait(5):
            self.stop()
            raise RuntimeError("Privacy screen did not initialize")
        if self._error:
            raise RuntimeError(f"Privacy screen failed: {self._error}") from self._error
        return True

    def _run(self) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
        ]
        user32.CreateWindowExW.restype = wintypes.HWND
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD]
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        hwnd = None
        hinstance = kernel32.GetModuleHandleW(None)
        try:
            vx = user32.GetSystemMetrics(76)
            vy = user32.GetSystemMetrics(77)
            vw = user32.GetSystemMetrics(78) or user32.GetSystemMetrics(0)
            vh = user32.GetSystemMetrics(79) or user32.GetSystemMetrics(1)

            ex_style = 0x00000008 | 0x00000080 | 0x00080000 | 0x00000020
            style = 0x80000000 | 0x10000000 | 0x00000004  # WS_POPUP | WS_VISIBLE | SS_BLACKRECT: opaque pure-black surface

            hwnd = user32.CreateWindowExW(
                ex_style, "STATIC", "", style,
                vx, vy, vw, vh, None, None, hinstance, None
            )
            if not hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            self._hwnd = hwnd

            user32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x00000002)
            user32.ShowWindow(hwnd, 5)
            user32.SetWindowPos(hwnd, -1, vx, vy, vw, vh, 0x0040 | 0x0010)
            user32.UpdateWindow(hwnd)

            if not user32.SetWindowDisplayAffinity(hwnd, 0x00000011):
                user32.SetWindowDisplayAffinity(hwnd, 0x00000001)

            user32.RegisterHotKey(None, 0x5244, 0x0002 | 0x0001 | 0x0004, ord("U"))
            self._ready.set()

            msg = wintypes.MSG()
            while not self._stop_flag.is_set():
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    if msg.message == 0x0312 and msg.wParam == 0x5244:
                        self._stop_flag.set()
                        break
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                time.sleep(0.03)
        except BaseException as exc:
            self._error = exc
            self._ready.set()
        finally:
            try:
                user32.UnregisterHotKey(None, 0x5244)
            except Exception:
                pass
            if hwnd:
                try:
                    user32.DestroyWindow(hwnd)
                except Exception:
                    pass
            self._hwnd = None
            self._stopped.set()

    def stop(self) -> None:
        self._stop_flag.set()
        if threading.current_thread() is not self._thread:
            self._stopped.wait(2)
