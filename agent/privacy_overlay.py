"""Visible Windows privacy curtain with capture exclusion and safe display fallback."""
from __future__ import annotations
import ctypes
import logging
import os
import threading
from ctypes import wintypes

log = logging.getLogger("remote-desk-agent.privacy")
WDA_EXCLUDEFROMCAPTURE = 0x00000011
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
LWA_ALPHA = 0x00000002
EMERGENCY_HOTKEY_ID = 0x5244
EMERGENCY_HOTKEY_MODIFIERS = 0x0002 | 0x0001 | 0x0004
EMERGENCY_HOTKEY_VK = ord("B")


class PrivacyBanner:
    """Fullscreen curtain on a dedicated UI thread; restore display state on exit."""

    def __init__(self) -> None:
        self._thread = None
        self._root = None
        self._hwnd = None
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._error = None
        self._mode = "black"
        self._hotkey_thread = None
        self._hotkey_stop = threading.Event()
        self._gamma_dc = None
        self._gamma_original = None

    def start(self, mode: str = "black") -> bool:
        if os.name != "nt":
            return False
        if mode not in {"black", "banner"}:
            raise ValueError("Unsupported privacy overlay mode")
        if self._thread and self._thread.is_alive():
            if self._mode == mode:
                return True
            self.stop()
        self._mode = mode
        self._ready.clear()
        self._stopped.clear()
        self._error = None
        self._hotkey_stop.clear()
        self._thread = threading.Thread(target=self._run, name="rdp-privacy-overlay", daemon=True)
        self._thread.start()
        if not self._ready.wait(8):
            self.stop()
            raise RuntimeError("Privacy screen did not initialize")
        if self._error:
            raise RuntimeError("Privacy screen failed") from self._error
        return True

    def _apply_gamma_fallback(self) -> None:
        """Dim physical output while leaving the composed desktop available to capture."""
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        user32.GetDC.argtypes = [wintypes.HWND]
        user32.GetDC.restype = wintypes.HDC
        dc = user32.GetDC(None)
        if not dc:
            raise ctypes.WinError(ctypes.get_last_error())
        ramp_type = ctypes.c_ushort * (3 * 256)
        original = ramp_type()
        if not gdi32.GetDeviceGammaRamp(dc, ctypes.byref(original)):
            user32.ReleaseDC(None, dc)
            raise ctypes.WinError(ctypes.get_last_error())
        dimmed = ramp_type()
        for channel in range(3):
            for index in range(256):
                dimmed[channel * 256 + index] = index
        if not gdi32.SetDeviceGammaRamp(dc, ctypes.byref(dimmed)):
            user32.ReleaseDC(None, dc)
            raise ctypes.WinError(ctypes.get_last_error())
        self._gamma_dc = dc
        self._gamma_original = original
        log.warning("Capture affinity unavailable; using near-black hardware gamma fallback")

    def _restore_gamma_fallback(self) -> None:
        if not self._gamma_dc or self._gamma_original is None:
            return
        try:
            gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            gdi32.SetDeviceGammaRamp(self._gamma_dc, ctypes.byref(self._gamma_original))
            user32.ReleaseDC(None, self._gamma_dc)
        except Exception:
            log.exception("Could not restore the original display gamma ramp")
        finally:
            self._gamma_dc = None
            self._gamma_original = None

    def _run(self) -> None:
        try:
            import tkinter as tk
            root = tk.Tk()
            self._root = root
            root.title("Remote Desk Pro — Privacy Screen")
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            background = "#000000" if self._mode == "black" else "#101827"
            root.configure(bg=background)
            width, height = root.winfo_screenwidth(), root.winfo_screenheight()
            root.geometry(f"{width}x{height}+0+0")
            if self._mode == "banner":
                panel = tk.Frame(root, bg=background, padx=48, pady=40)
                panel.place(relx=0.5, rely=0.5, anchor="center")
                tk.Label(panel, text="REMOTE REPAIR IN PROGRESS", fg="#8ee6c2", bg=background,
                         font=("Segoe UI", 13, "bold")).pack(pady=(0, 18))
                tk.Label(panel, text="Remote Repair Technician is Currently Working",
                         fg="white", bg=background, font=("Segoe UI", 25, "bold"),
                         wraplength=max(500, width - 160)).pack(pady=8)
                tk.Label(panel, text="Please do not touch mouse or keyboard",
                         fg="#d4dbe7", bg=background, font=("Segoe UI", 16)).pack(pady=10)
            tk.Label(root, text="Emergency local unlock: Ctrl + Alt + Shift + B",
                     fg="#8ee6c2", bg=background, font=("Segoe UI", 10)).place(relx=0.5, rely=0.97, anchor="center")
            # The emergency hotkey is registered globally; never grab desktop focus.
            root.update_idletasks()
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            user32.GetAncestor.restype = wintypes.HWND
            hwnd = wintypes.HWND(root.winfo_id())
            hwnd = user32.GetAncestor(hwnd, 2) or hwnd
            self._hwnd = hwnd
            long_ptr = ctypes.c_ssize_t
            get_style = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
            set_style = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
            get_style.argtypes = [wintypes.HWND, ctypes.c_int]
            get_style.restype = long_ptr
            set_style.argtypes = [wintypes.HWND, ctypes.c_int, long_ptr]
            set_style.restype = long_ptr
            ex_style = get_style(hwnd, -20)
            ex_style |= WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            set_style(hwnd, -20, ex_style)
            user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_ubyte, wintypes.DWORD]
            user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
            if not user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA):
                raise ctypes.WinError(ctypes.get_last_error())
            user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
            user32.SetWindowPos.restype = wintypes.BOOL
            user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
            user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
            user32.SetWindowPos(hwnd, wintypes.HWND(-1), 0, 0, 0, 0,
                                0x0001 | 0x0002 | 0x0010 | 0x0020)
            if not user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
                log.warning("Display affinity unavailable; switching to gamma curtain fallback")
                self._apply_gamma_fallback()
                root.withdraw()
            else:
                log.info("Privacy curtain active; input remains click-through")
            self._ready.set()
            self._start_emergency_hotkey()
            root.mainloop()
        except BaseException as exc:
            self._error = exc
            self._ready.set()
            log.exception("Privacy curtain initialization failed")
        finally:
            self._hotkey_stop.set()
            self._restore_gamma_fallback()
            self._root = None
            self._hwnd = None
            self._stopped.set()

    def _start_emergency_hotkey(self) -> None:
        def listen() -> None:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            if not user32.RegisterHotKey(None, EMERGENCY_HOTKEY_ID,
                                         EMERGENCY_HOTKEY_MODIFIERS, EMERGENCY_HOTKEY_VK):
                log.warning("Emergency privacy hotkey could not be registered")
                return
            try:
                message = wintypes.MSG()
                while not self._hotkey_stop.is_set():
                    while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
                        if message.message == 0x0312 and message.wParam == EMERGENCY_HOTKEY_ID:
                            self.stop()
                            return
                    self._hotkey_stop.wait(0.05)
            finally:
                user32.UnregisterHotKey(None, EMERGENCY_HOTKEY_ID)
        self._hotkey_thread = threading.Thread(target=listen, name="rdp-privacy-emergency-unlock", daemon=True)
        self._hotkey_thread.start()

    def stop(self) -> None:
        """Hide only the local curtain; it never owns or closes a relay socket."""
        self._hotkey_stop.set()
        log.info("Privacy curtain stop requested; remote session remains connected")
        hwnd = self._hwnd
        if hwnd and os.name == "nt":
            try:
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
                user32.PostMessageW.restype = wintypes.BOOL
                if not user32.PostMessageW(hwnd, 0x0010, 0, 0):  # WM_CLOSE
                    log.debug("Could not post WM_CLOSE to privacy curtain: %s", ctypes.get_last_error())
            except Exception:
                log.exception("Could not close privacy curtain window")
        self._restore_gamma_fallback()
        if threading.current_thread() is not self._thread:
            self._stopped.wait(3)
