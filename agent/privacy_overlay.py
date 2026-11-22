"""Visible, reversible Windows privacy curtain for an approved remote session."""
from __future__ import annotations

import ctypes
import os
import threading
from ctypes import wintypes


class PrivacyBanner:
    """Topmost local privacy overlay excluded from supported Windows capture APIs."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._root = None
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._error: BaseException | None = None
        self._mode = "banner"
        self._hotkey_thread: threading.Thread | None = None
        self._hotkey_stop = threading.Event()

    def start(self, mode: str = "banner") -> bool:
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
                tk.Label(panel, text="Emergency local unlock: Ctrl + Alt + Shift + U",
                         fg="#8ee6c2", bg=background, font=("Segoe UI", 11)).pack(pady=(22, 0))
            root.bind_all("<Control-Alt-Shift-u>", lambda _event: self.stop())
            root.bind_all("<Control-Alt-Shift-U>", lambda _event: self.stop())
            root.update_idletasks()
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            hwnd = int(root.winfo_id())
            hwnd = int(user32.GetAncestor(hwnd, 2) or hwnd)
            get_style, set_style = user32.GetWindowLongW, user32.SetWindowLongW
            get_style.restype = ctypes.c_long
            set_style.restype = ctypes.c_long
            set_style(hwnd, -20, get_style(hwnd, -20) | 0x00000008 | 0x00000080)
            user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0020)
            if not user32.SetWindowDisplayAffinity(hwnd, 0x00000011):
                raise ctypes.WinError(ctypes.get_last_error())
            root.grab_set()
            root.focus_force()
            self._ready.set()
            self._start_emergency_hotkey()
            root.mainloop()
        except BaseException as exc:
            self._error = exc
            self._ready.set()
        finally:
            self._hotkey_stop.set()
            self._root = None
            self._stopped.set()

    def _start_emergency_hotkey(self) -> None:
        def listen() -> None:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            if not user32.RegisterHotKey(None, 0x5244, 0x0002 | 0x0001 | 0x0004, ord("U")):
                return
            try:
                message = wintypes.MSG()
                while not self._hotkey_stop.is_set():
                    while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
                        if message.message == 0x0312 and message.wParam == 0x5244:
                            self.stop()
                            return
                    threading.Event().wait(0.05)
            finally:
                user32.UnregisterHotKey(None, 0x5244)
        self._hotkey_thread = threading.Thread(target=listen, name="rdp-privacy-emergency-unlock", daemon=True)
        self._hotkey_thread.start()

    def stop(self) -> None:
        self._hotkey_stop.set()
        root = self._root
        if root is not None:
            try:
                if threading.current_thread() is self._thread:
                    root.destroy()
                else:
                    root.after(0, root.destroy)
            except Exception:
                pass
        if threading.current_thread() is not self._thread:
            self._stopped.wait(3)
