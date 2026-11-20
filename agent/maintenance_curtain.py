"""Consent-based Windows maintenance curtain with capture-exclusion verification.

The curtain is deliberately fail-closed: it is never reported active unless every
selected monitor window has WDA_EXCLUDEFROMCAPTURE affinity and the MSS/GDI
probe confirms that the sentinel overlay pixels are absent from captured frames.
"""
from __future__ import annotations

import ctypes
import platform
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable

WDA_NONE = 0x0
WDA_EXCLUDEFROMCAPTURE = 0x11
MIN_SUPPORTED_BUILD = 19041
CURTAIN_TIMEOUT_SECONDS = 15 * 60


@dataclass(frozen=True)
class CurtainCapability:
    supported: bool
    reason: str
    os_build: int | None = None


def capability_for(build: int | None, dwm_enabled: bool, is_windows: bool = True) -> CurtainCapability:
    if not is_windows:
        return CurtainCapability(False, "Windows is required.", build)
    if build is None or build < MIN_SUPPORTED_BUILD:
        return CurtainCapability(False, "Windows 10 build 19041 or newer is required.", build)
    if not dwm_enabled:
        return CurtainCapability(False, "Desktop Window Manager composition is unavailable.", build)
    return CurtainCapability(True, "Capture exclusion is available.", build)


def sentinel_rgb(baseline_rgb: tuple[int, int, int],
                 avoid: set[tuple[int, int, int]] | None = None) -> tuple[int, int, int]:
    """Choose a probe colour absent from the pre-overlay sample patch."""
    red, green, blue = (max(0, min(255, int(value))) for value in baseline_rgb)
    candidates = (
        (255 - red, 255 - green, 255 - blue),
        (red ^ 0xFF, green ^ 0x7F, blue ^ 0x3F),
        (red ^ 0x7F, green ^ 0xFF, blue ^ 0x5A),
        (red ^ 0x5A, green ^ 0x3F, blue ^ 0xFF),
        (0, 255, 255), (255, 0, 255), (255, 255, 0),
    )
    blocked = avoid or set()
    return next((candidate for candidate in candidates if candidate not in blocked), (255, 0, 0))


def sentinel_is_visible(frame_rgb: bytes, width: int, height: int, sentinel: tuple[int, int, int]) -> bool:
    """Return true when the top-left 4x4 probe patch appears in the captured frame."""
    if width < 4 or height < 4 or len(frame_rgb) < width * height * 3:
        return True
    for y in range(4):
        for x in range(4):
            offset = (y * width + x) * 3
            if tuple(frame_rgb[offset:offset + 3]) == sentinel:
                return True
    return False


def selected_monitor_indexes(requested: Iterable[int] | None, monitor_count: int) -> list[int]:
    """Validate MSS monitor indexes; index 0 is the virtual desktop, not a display."""
    available = list(range(1, max(1, monitor_count)))
    if requested is None:
        return available
    selected = sorted({int(value) for value in requested if str(value).isdigit()})
    if not selected or any(value not in available for value in selected):
        raise ValueError("The requested monitor selection is invalid.")
    return selected


def windows_capability() -> CurtainCapability:
    if platform.system() != "Windows":
        return capability_for(None, False, False)
    build = int(getattr(sys.getwindowsversion(), "build", 0))
    enabled = ctypes.c_int(0)
    try:
        result = ctypes.windll.dwmapi.DwmIsCompositionEnabled(ctypes.byref(enabled))
        dwm_enabled = result == 0 and enabled.value == 1
    except (AttributeError, OSError):
        dwm_enabled = False
    return capability_for(build, dwm_enabled)


def monitor_inventory() -> list[dict[str, int]]:
    if platform.system() != "Windows":
        return []
    import mss
    with mss.mss() as capture:
        return [
            {"index": index, "left": int(monitor["left"]), "top": int(monitor["top"]),
             "width": int(monitor["width"]), "height": int(monitor["height"])}
            for index, monitor in enumerate(capture.monitors[1:], start=1)
        ]


class MaintenanceCurtain:
    """Owns one fullscreen overlay per selected monitor on a dedicated UI thread."""

    def __init__(self, monitor_indexes: Iterable[int] | None, emit: Callable[[str, dict], None]):
        self.monitor_indexes = list(monitor_indexes) if monitor_indexes is not None else None
        self.emit = emit
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self._reason = "local_exit"

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, name="rdp-maintenance-curtain", daemon=True)
        self.thread.start()

    def stop(self, reason: str = "requested") -> None:
        self._reason = reason[:80]
        self.stop_event.set()

    def join(self, timeout: float = 3.0) -> None:
        if self.thread:
            self.thread.join(timeout)

    def _run(self) -> None:
        windows: list[tuple[object, int]] = []
        hook = None
        root = None
        activated = False
        failed = False
        try:
            capability = windows_capability()
            if not capability.supported:
                self.emit("curtain.status", {"status": "unsupported", "reason": capability.reason,
                                             "os_build": capability.os_build})
                return

            import mss
            import tkinter as tk
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            try:
                # PER_MONITOR_AWARE_V2; fall back to per-monitor awareness on older builds.
                user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            except (AttributeError, OSError):
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(2)
                except (AttributeError, OSError):
                    pass

            with mss.mss() as capture:
                indexes = selected_monitor_indexes(self.monitor_indexes, len(capture.monitors))
                monitors = [(index, capture.monitors[index]) for index in indexes]
                if not monitors:
                    raise RuntimeError("No active display was found.")
                probes = {}
                for index, monitor in monitors:
                    before = capture.grab(monitor)
                    baseline = tuple(before.rgb[:3])
                    baseline_patch = {
                        tuple(before.rgb[(y * before.width + x) * 3:(y * before.width + x) * 3 + 3])
                        for y in range(min(4, before.height)) for x in range(min(4, before.width))
                    }
                    probes[index] = sentinel_rgb(baseline, baseline_patch)

                root = tk.Tk()
                root.withdraw()
                root.title("Remote Desk Pro Maintenance Curtain")
                root.attributes("-topmost", True)

                def stop_local(_event=None):
                    self._reason = "local_exit"
                    self.stop_event.set()
                    try:
                        root.after(0, root.quit)
                    except tk.TclError:
                        pass

                for index, monitor in monitors:
                    window = tk.Toplevel(root)
                    window.overrideredirect(True)
                    window.attributes("-topmost", True)
                    window.configure(background="#111b2b")
                    left, top = int(monitor["left"]), int(monitor["top"])
                    x_offset = f"+{left}" if left >= 0 else str(left)
                    y_offset = f"+{top}" if top >= 0 else str(top)
                    window.geometry(f'{int(monitor["width"])}x{int(monitor["height"])}{x_offset}{y_offset}')
                    canvas = tk.Canvas(window, background="#111b2b", highlightthickness=0)
                    canvas.pack(fill="both", expand=True)
                    sentinel = "#%02x%02x%02x" % probes[index]
                    canvas.create_rectangle(0, 0, 4, 4, fill=sentinel, outline=sentinel)
                    panel = tk.Frame(canvas, background="#17263a", padx=34, pady=26)
                    canvas.create_window(int(monitor["width"]) // 2, int(monitor["height"]) // 2,
                                         window=panel, anchor="center")
                    tk.Label(panel, text="SYSTEM MAINTENANCE IN PROGRESS",
                             font=("Segoe UI", 22, "bold"), foreground="#ffffff",
                             background="#17263a").pack(pady=(0, 12))
                    tk.Label(panel, text="Technician Active",
                             font=("Segoe UI", 15), foreground="#b8c8da",
                             background="#17263a").pack(pady=(0, 18))
                    tk.Label(panel, text="Press Esc or click Stop Assistance to end assistance",
                             font=("Segoe UI", 11), foreground="#d9e4ef",
                             background="#17263a").pack(pady=(0, 20))
                    tk.Button(panel, text="Stop Assistance", command=stop_local,
                              font=("Segoe UI", 12, "bold"), foreground="#ffffff",
                              background="#b42332", activebackground="#8f1d29",
                              relief="flat", padx=22, pady=10).pack()
                    window.protocol("WM_DELETE_WINDOW", stop_local)
                    root.update_idletasks()
                    hwnd = int(window.winfo_id())
                    user32.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
                    user32.SetWindowDisplayAffinity.restype = ctypes.c_int
                    user32.GetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
                    user32.GetWindowDisplayAffinity.restype = ctypes.c_int
                    windows.append((window, hwnd))
                    if not user32.SetWindowDisplayAffinity(ctypes.c_void_p(hwnd), WDA_EXCLUDEFROMCAPTURE):
                        raise RuntimeError(f"Display affinity could not be enabled for Screen {index}.")
                    affinity = ctypes.c_uint(0)
                    if not user32.GetWindowDisplayAffinity(ctypes.c_void_p(hwnd), ctypes.byref(affinity)):
                        raise RuntimeError(f"Display affinity could not be verified for Screen {index}.")
                    if affinity.value != WDA_EXCLUDEFROMCAPTURE:
                        raise RuntimeError(f"Screen {index} does not support capture exclusion.")
                    self.emit("curtain.affinity_enabled", {"monitor": index, "affinity": affinity.value})

                root.update()
                time.sleep(0.2)
                # Verify the actual MSS/GDI path on each selected display before success.
                for index, monitor in monitors:
                    frame = capture.grab(monitor)
                    if sentinel_is_visible(frame.rgb, frame.width, frame.height, probes[index]):
                        raise RuntimeError(f"MSS capture still contains the Screen {index} curtain.")
                    self.emit("curtain.capture_verified", {"monitor": index, "capture_backend": "mss-gdi"})

                activated = True
                self.emit("curtain.shown", {"monitors": indexes, "capture_backend": "mss-gdi"})
                self.emit("curtain.status", {"status": "active_verified", "monitors": indexes,
                                             "capture_backend": "mss-gdi"})
                deadline = time.monotonic() + CURTAIN_TIMEOUT_SECONDS

                # A low-level hook distinguishes physical Esc from injected remote key events.
                WH_KEYBOARD_LL, WM_KEYDOWN, WM_SYSKEYDOWN, VK_ESCAPE, LLKHF_INJECTED = 13, 0x0100, 0x0104, 0x1B, 0x10
                class KBDLLHOOKSTRUCT(ctypes.Structure):
                    _fields_ = [("vkCode", ctypes.c_uint), ("scanCode", ctypes.c_uint),
                                ("flags", ctypes.c_uint), ("time", ctypes.c_uint),
                                ("dwExtraInfo", ctypes.c_void_p)]
                callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t)
                def hook_proc(code, message, data):
                    if code >= 0 and message in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        key = ctypes.cast(data, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                        if key.vkCode == VK_ESCAPE and not (key.flags & LLKHF_INJECTED):
                            stop_local()
                            return 1
                    return user32.CallNextHookEx(hook, code, message, data)
                callback = callback_type(hook_proc)
                user32.SetWindowsHookExW.argtypes = [ctypes.c_int, callback_type, ctypes.c_void_p, ctypes.c_uint]
                user32.SetWindowsHookExW.restype = ctypes.c_void_p
                user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t]
                user32.CallNextHookEx.restype = ctypes.c_ssize_t
                user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
                user32.UnhookWindowsHookEx.restype = ctypes.c_int
                kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
                kernel32.GetModuleHandleW.restype = ctypes.c_void_p
                hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, callback, kernel32.GetModuleHandleW(None), 0)
                if not hook:
                    raise RuntimeError("The local Escape safety hook could not be installed.")

                def input_desktop_is_default() -> bool:
                    try:
                        user32.OpenInputDesktop.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
                        user32.OpenInputDesktop.restype = ctypes.c_void_p
                        user32.GetUserObjectInformationW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                                                                    ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)]
                        user32.GetUserObjectInformationW.restype = ctypes.c_int
                        user32.CloseDesktop.argtypes = [ctypes.c_void_p]
                        user32.CloseDesktop.restype = ctypes.c_int
                        handle = user32.OpenInputDesktop(0, False, 0x0001)
                        if not handle:
                            return False
                        try:
                            name = ctypes.create_unicode_buffer(128)
                            needed = ctypes.c_ulong(0)
                            if not user32.GetUserObjectInformationW(handle, 2, name,
                                                                    ctypes.sizeof(name), ctypes.byref(needed)):
                                return False
                            return name.value.lower() == "default"
                        finally:
                            user32.CloseDesktop(handle)
                    except (AttributeError, OSError):
                        return False

                def poll():
                    if self.stop_event.is_set() or time.monotonic() >= deadline:
                        if not self.stop_event.is_set():
                            self._reason = "timeout"
                        root.quit()
                        return
                    if not input_desktop_is_default():
                        self._reason = "lock_screen_or_secure_desktop"
                        self.stop_event.set()
                        root.quit()
                        return
                    root.after(250, poll)
                root.after(100, poll)
                root.mainloop()
        except Exception as exc:
            failed = True
            reason = str(exc)[:160]
            self.emit("curtain.affinity_failed", {"reason": reason})
            self.emit("curtain.status", {"status": "failed", "reason": reason})
        finally:
            if hook:
                try:
                    ctypes.windll.user32.UnhookWindowsHookEx(hook)
                except (AttributeError, OSError):
                    pass
            for window, hwnd in reversed(windows):
                try:
                    ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_NONE)
                except (AttributeError, OSError):
                    pass
                try:
                    window.destroy()
                except Exception:
                    pass
            if root is not None:
                try:
                    root.destroy()
                except Exception:
                    pass
            if activated:
                if self._reason in ("local_exit", "timeout", "lock_screen_or_secure_desktop"):
                    self.emit("curtain.exit_requested", {"reason": self._reason})
                self.emit("curtain.revoked", {"reason": self._reason})
                self.emit("curtain.closed", {"reason": self._reason})
            if activated and not failed:
                self.emit("curtain.status", {"status": "inactive", "reason": self._reason})
