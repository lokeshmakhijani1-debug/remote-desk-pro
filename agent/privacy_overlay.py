"""Native Win32 reversible privacy curtain for an approved remote session."""
from __future__ import annotations

import ctypes
import os
import threading
from ctypes import wintypes


class PrivacyBanner:
    """Topmost click-through Win32 black curtain excluded from screen capture."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._hwnd: int | None = None
        self._ready = threading.Event()
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
        self._stopped.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name="rdp-win32-privacy", daemon=True)
        self._thread.start()
        if not self._ready.wait(5):
            self.stop()
            raise RuntimeError("Privacy screen did not initialize")
        if self._error:
            raise RuntimeError("Privacy screen failed") from self._error
        return True

    def _run(self) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        hwnd = None
        brush = None
        class_name = f"RDPPrivacyCurtain_{threading.get_ident()}"
        hinstance = kernel32.GetModuleHandleW(None)
        try:
            WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

            def wnd_proc(h, msg, wp, lp):
                if msg == 0x0312 and wp == 0x5244:  # WM_HOTKEY emergency unlock
                    user32.PostQuitMessage(0)
                    return 0
                if msg == 0x0010:  # WM_CLOSE
                    user32.DestroyWindow(h)
                    return 0
                if msg == 0x0002:  # WM_DESTROY
                    user32.PostQuitMessage(0)
                    return 0
                return user32.DefWindowProcW(h, msg, wp, lp)

            proc_cb = WNDPROC(wnd_proc)
            color = 0x00000000 if self._mode == "black" else 0x00271810
            brush = gdi32.CreateSolidBrush(color)

            class WNDCLASSEXW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.UINT), ("style", wintypes.UINT),
                    ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                    ("hIcon", wintypes.HICON), ("hCursor", wintypes.HICON),
                    ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR),
                    ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON),
                ]

            wc = WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wc.lpfnWndProc = proc_cb
            wc.hInstance = hinstance
            wc.hbrBackground = brush
            wc.lpszClassName = class_name
            user32.RegisterClassExW(ctypes.byref(wc))

            vx = user32.GetSystemMetrics(76)
            vy = user32.GetSystemMetrics(77)
            vw = user32.GetSystemMetrics(78) or user32.GetSystemMetrics(0)
            vh = user32.GetSystemMetrics(79) or user32.GetSystemMetrics(1)

            # WS_EX_TOPMOST (0x8) | WS_EX_TOOLWINDOW (0x80) | WS_EX_LAYERED (0x80000) | WS_EX_TRANSPARENT (0x20)
            ex_style = 0x00000008 | 0x00000080 | 0x00080000 | 0x00000020
            # WS_POPUP (0x80000000) | WS_VISIBLE (0x10000000)
            style = 0x80000000 | 0x10000000

            hwnd = user32.CreateWindowExW(
                ex_style, class_name, "Remote Desk Pro Privacy", style,
                vx, vy, vw, vh, None, None, hinstance, None
            )
            if not hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            self._hwnd = hwnd
            user32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x00000002)
            user32.SetWindowPos(hwnd, -1, vx, vy, vw, vh, 0x0040 | 0x0010)
            # Exclude from capture so phone viewer sees live desktop
            if not user32.SetWindowDisplayAffinity(hwnd, 0x00000011):
                user32.SetWindowDisplayAffinity(hwnd, 0x00000001)
            # Emergency local unlock: Ctrl + Alt + Shift + U
            user32.RegisterHotKey(hwnd, 0x5244, 0x0002 | 0x0001 | 0x0004, ord("U"))
            self._ready.set()

            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except BaseException as exc:
            self._error = exc
            self._ready.set()
        finally:
            if hwnd:
                try:
                    user32.UnregisterHotKey(hwnd, 0x5244)
                    user32.DestroyWindow(hwnd)
                except Exception:
                    pass
            try:
                user32.UnregisterClassW(class_name, hinstance)
            except Exception:
                pass
            if brush:
                gdi32.DeleteObject(brush)
            self._hwnd = None
            self._stopped.set()

    def stop(self) -> None:
        hwnd = self._hwnd
        if hwnd:
            try:
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.PostMessageW(hwnd, 0x0010, 0, 0)
            except Exception:
                pass
        if threading.current_thread() is not self._thread:
            self._stopped.wait(3)
