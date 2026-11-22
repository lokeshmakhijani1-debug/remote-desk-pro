"""Visible, reversible maintenance banner for an approved remote session."""
from __future__ import annotations

import os
import threading


class PrivacyBanner:
    """Show an always-on-top, input-blocking banner; never conceal remote activity."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._root = None
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._error: BaseException | None = None

    def start(self) -> bool:
        if os.name != "nt":
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._ready.clear()
        self._stopped.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name="rdp-privacy-banner", daemon=True)
        self._thread.start()
        if not self._ready.wait(8):
            raise RuntimeError("Maintenance banner did not initialize")
        if self._error:
            raise RuntimeError("Maintenance banner failed") from self._error
        return True

    def _run(self) -> None:
        try:
            import tkinter as tk
            root = tk.Tk()
            self._root = root
            root.title("Remote Desk Pro — Technician working")
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.configure(bg="#101827")
            width = root.winfo_screenwidth()
            height = root.winfo_screenheight()
            root.geometry(f"{width}x{height}+0+0")
            panel = tk.Frame(root, bg="#101827", padx=48, pady=40)
            panel.place(relx=0.5, rely=0.5, anchor="center")
            tk.Label(panel, text="REMOTE REPAIR IN PROGRESS", fg="#8ee6c2", bg="#101827",
                     font=("Segoe UI", 13, "bold")).pack(pady=(0, 18))
            tk.Label(panel, text="Remote Repair Technician is Currently Working",
                     fg="white", bg="#101827", font=("Segoe UI", 25, "bold"),
                     wraplength=max(500, width - 160)).pack(pady=8)
            tk.Label(panel, text="Please do not touch mouse or keyboard",
                     fg="#d4dbe7", bg="#101827", font=("Segoe UI", 16)).pack(pady=10)
            tk.Label(panel, text="Emergency local unlock: Ctrl + Alt + Shift + U",
                     fg="#8ee6c2", bg="#101827", font=("Segoe UI", 11)).pack(pady=(22, 0))
            root.bind_all("<Control-Alt-Shift-u>", lambda _event: self.stop())
            root.bind_all("<Control-Alt-Shift-U>", lambda _event: self.stop())
            root.focus_force()
            self._ready.set()
            root.mainloop()
        except BaseException as exc:
            self._error = exc
            self._ready.set()
        finally:
            self._root = None
            self._stopped.set()

    def stop(self) -> None:
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
