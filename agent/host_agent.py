"""Visible-consent host bridge. Streaming starts only after explicit local approval."""
import argparse
import asyncio
import ctypes
import math
import time
import base64
import json
import logging
import os
import sys
import threading
from pathlib import Path
from resumable_transfer import EndpointFileReceiver, EndpointTransferError
try:
    from privacy_overlay import PrivacyBanner
    from session_recorder import SessionRecorder
except ModuleNotFoundError:
    from agent.privacy_overlay import PrivacyBanner
    from agent.session_recorder import SessionRecorder
from logging.handlers import RotatingFileHandler
from io import BytesIO

APP_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "RemoteDeskPro")
os.makedirs(APP_DIR, exist_ok=True)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = Path(os.getenv("RDP_LOG_DIR", str(Path(APP_DIR) / "logs" if getattr(sys, "frozen", False) else PROJECT_ROOT / "logs")))
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    LOG_DIR = Path(APP_DIR) / "logs"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
log = logging.getLogger("remote-desk-agent")
log.setLevel(logging.INFO)
if not any(isinstance(handler, RotatingFileHandler) and
           Path(getattr(handler, "baseFilename", "")).resolve() == (LOG_DIR / "agent.log").resolve()
           for handler in log.handlers):
    _handler = RotatingFileHandler(LOG_DIR / "agent.log", maxBytes=2_000_000, backupCount=4, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    log.addHandler(_handler)
_STATUS_CALLBACK = None
_CONSENT_CALLBACK = None
_FILE_CONSENT_CALLBACK = None
_DIAGNOSTICS_CALLBACK = None
_LAST_ERROR = "None"
_INSTANCE_MUTEX = None
_PRESSED_KEYS = set()
_PRESSED_MOUSE_BUTTONS = set()
_PRIMARY_CAPTURE_SIZE = None
_INPUT_LOCK = threading.RLock()


def _focus_existing_window():
    if os.name != "nt":
        return
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, "Remote Desk Pro")
        if hwnd:
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
    except Exception:
        log.debug("Could not focus existing agent window", exc_info=True)

def acquire_single_instance():
    """Hold the machine-wide Windows mutex for the lifetime of this agent."""
    global _INSTANCE_MUTEX
    if os.name != "nt":
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, True, r"Global\RemoteDeskProAgentMutex")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(handle)
        _focus_existing_window()
        return False
    _INSTANCE_MUTEX = handle
    return True

def release_single_instance():
    global _INSTANCE_MUTEX
    if _INSTANCE_MUTEX and os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.ReleaseMutex(_INSTANCE_MUTEX)
        kernel32.CloseHandle(_INSTANCE_MUTEX)
        _INSTANCE_MUTEX = None

def set_windows_dpi_awareness():
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            log.warning("Could not enable per-monitor DPI awareness")

def _normalize_key(value):
    aliases = {
        " ": "space", "ArrowUp": "up", "ArrowDown": "down",
        "ArrowLeft": "left", "ArrowRight": "right", "Escape": "esc",
        "Control": "ctrl", "Shift": "shift", "Alt": "alt", "Meta": "win",
        "Backspace": "backspace", "Delete": "delete", "Enter": "enter",
        "Tab": "tab", "PageUp": "pageup", "PageDown": "pagedown",
    }
    key = str(value or "")
    return aliases.get(key, aliases.get(key.lower(), key.lower()))

def set_status_callback(callback):
    global _STATUS_CALLBACK
    _STATUS_CALLBACK = callback

def set_consent_callback(callback):
    global _CONSENT_CALLBACK
    _CONSENT_CALLBACK = callback

def set_file_consent_callback(callback):
    global _FILE_CONSENT_CALLBACK
    _FILE_CONSENT_CALLBACK = callback

def set_diagnostics_callback(callback):
    global _DIAGNOSTICS_CALLBACK
    _DIAGNOSTICS_CALLBACK = callback

def set_status(message: str):
    global _LAST_ERROR
    if "connected to relay" in message.lower() or message == "Connected (Live)":
        _LAST_ERROR = "None"
        if _DIAGNOSTICS_CALLBACK:
            _DIAGNOSTICS_CALLBACK(_LAST_ERROR, None)
    if any(term in message.lower() for term in ("error", "unreachable", "denied", "rejected", "invalid")):
        _LAST_ERROR = message
        if _DIAGNOSTICS_CALLBACK:
            _DIAGNOSTICS_CALLBACK(_LAST_ERROR, None)
    log.info(message)
    if _STATUS_CALLBACK:
        try:
            _STATUS_CALLBACK(message)
        except Exception:
            log.exception("Status callback failed")

def _consent_dialog(device_id: str, dynamic_password: str) -> bool:
    import tkinter as tk
    root = tk.Tk()
    root.title("Remote Desk Pro — Session approval")
    root.geometry("420x300")
    root.resizable(False, False)
    tk.Label(root, text="REMOTE ACCESS REQUEST", font=("Segoe UI", 14, "bold")).pack(pady=(20, 8))
    tk.Label(root, text="Device ID: " + device_id, font=("Segoe UI", 11)).pack(pady=3)
    tk.Label(root, text="Dynamic password: " + (dynamic_password or "Check the dashboard"), font=("Segoe UI", 11)).pack(pady=3)
    tk.Label(root, text="A remote viewer is requesting access. Approved sessions are recorded locally for security and audit.", wraplength=360).pack(pady=12)
    tk.Checkbutton(root, text="Unattended access (not available)", state="disabled").pack()
    decision = {"approved": False}
    buttons = tk.Frame(root)
    buttons.pack(pady=18)
    def finish(value: bool):
        decision["approved"] = value
        root.destroy()
    tk.Button(buttons, text="Approve this session", command=lambda: finish(True), width=20).pack(side="left", padx=6)
    tk.Button(buttons, text="Deny", command=lambda: finish(False), width=10).pack(side="left", padx=6)
    root.protocol("WM_DELETE_WINDOW", lambda: finish(False))
    root.mainloop()
    return decision["approved"]

async def ask_host_consent(device_id: str, dynamic_password: str) -> bool:
    if _CONSENT_CALLBACK:
        return await _CONSENT_CALLBACK(device_id, dynamic_password)
    return await asyncio.to_thread(_consent_dialog, device_id, dynamic_password)

def _file_consent_dialog(name: str, size: int) -> bool:
    import tkinter as tk
    root = tk.Tk()
    root.title("Remote Desk Pro — Incoming file")
    root.geometry("440x230")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    decision = {"accepted": False}
    tk.Label(root, text="INCOMING FILE TRANSFER", font=("Segoe UI", 14, "bold")).pack(pady=(22, 10))
    tk.Label(root, text=f"File: {name}\nSize: {size:,} bytes", font=("Segoe UI", 10), justify="left").pack(pady=8)
    tk.Label(root, text="Accept to save this file in your Downloads folder.", wraplength=380).pack(pady=6)
    buttons = tk.Frame(root); buttons.pack(pady=14)
    def finish(value):
        decision["accepted"] = value
        root.destroy()
    tk.Button(buttons, text="Accept", command=lambda: finish(True), width=14, bg="#087d65", fg="white").pack(side="left", padx=8)
    tk.Button(buttons, text="Decline", command=lambda: finish(False), width=14).pack(side="left", padx=8)
    root.protocol("WM_DELETE_WINDOW", lambda: finish(False))
    root.mainloop()
    return decision["accepted"]


async def ask_file_consent(name: str, size: int) -> bool:
    if _FILE_CONSENT_CALLBACK:
        result = _FILE_CONSENT_CALLBACK(name, size)
        if asyncio.iscoroutine(result) or hasattr(result, "__await__"):
            result = await result
        return bool(result)
    return await asyncio.to_thread(_file_consent_dialog, name, size)


def downloads_destination(name: str, transfer_id: str) -> Path:
    safe_name = Path(str(name).replace("\\", "/")).name[:180] or "received-file"
    folder = Path.home() / "Downloads" / "RemoteDeskPro-Received"
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / safe_name
    if destination.exists():
        destination = folder / f"{destination.stem}-{transfer_id[:8]}{destination.suffix}"
    return destination


def apply_text(message: dict):
    import pyautogui
    pyautogui.FAILSAFE = False
    _focus_target_at_cursor()
    key = message.get("key")
    if key:
        normalized = _normalize_key(key)
        if normalized not in set(getattr(pyautogui, "KEYBOARD_KEYS", ())):
            return False
        pyautogui.press(normalized, _pause=False)
        return True
    value = message.get("text", "")
    if not isinstance(value, str) or not value or len(value) > 2048:
        return False
    if value.isascii() and value.isalnum():
        pyautogui.write(value, interval=0.01)
    else:
        import pyperclip
        pyperclip.copy(value)
        pyautogui.hotkey("ctrl", "v")
    return True


def paste_clipboard(text: str):
    if not isinstance(text, str) or len(text) > 65536:
        return False
    import pyautogui
    import pyperclip
    pyautogui.FAILSAFE = False
    _focus_target_at_cursor()
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v", _pause=False)
    return True


async def clipboard_watch(ws, running: asyncio.Event):
    import pyperclip
    previous = None
    while running.is_set():
        try:
            value = await asyncio.to_thread(pyperclip.paste)
            if isinstance(value, str) and value != previous and len(value) <= 65536:
                previous = value
                await ws.send(json.dumps({"type":"clipboard_update","text":value}))
        except Exception as exc:
            log.debug("Clipboard read unavailable: %s", exc)
        await asyncio.sleep(0.8)

def choose_save_path(name: str) -> str:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    path = filedialog.asksaveasfilename(title="Save file received from remote viewer", initialfile=name)
    root.destroy()
    return path

def encode_screen() -> bytes:
    import mss
    from PIL import Image
    with mss.mss() as capture:
        frame = capture.grab(capture.monitors[1])
        image = Image.frombytes("RGB", frame.size, frame.rgb)
        image.thumbnail((1600, 900))
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=65, optimize=True)
        return buffer.getvalue()

async def stream_screen(ws, running: asyncio.Event):
    while running.is_set():
        await ws.send(encode_screen())
        await asyncio.sleep(0.25)

def _wheel_delta_units(delta: float) -> int:
    """Convert normalized browser wheel deltas into Windows 120-unit notches."""
    notches = int(round(delta / 100.0))
    if delta != 0 and notches == 0:
        notches = 1 if delta > 0 else -1
    return int(notches * 120)


def _focus_target_at_cursor() -> bool:
    """Bring the window under the physical cursor forward before input dispatch."""
    if os.name != "nt":
        return True
    attached = False
    current_thread = 0
    target_thread = 0
    try:
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        class POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
        position = __import__("pyautogui").position()
        point = POINT(int(position.x), int(position.y))
        child = user32.WindowFromPoint(point)
        if not child:
            return False
        root = user32.GetAncestor(child, 2) or child
        process_id = wintypes.DWORD()
        target_thread = user32.GetWindowThreadProcessId(root, ctypes.byref(process_id))
        current_thread = kernel32.GetCurrentThreadId()
        if target_thread and target_thread != current_thread:
            attached = bool(user32.AttachThreadInput(current_thread, target_thread, True))
        user32.ShowWindow(root, 9)
        focused = bool(user32.SetForegroundWindow(root))
        return focused
    except Exception:
        log.debug("Could not foreground target window before input", exc_info=True)
        return False
    finally:
        if attached:
            try:
                user32.AttachThreadInput(current_thread, target_thread, False)
            except Exception:
                log.debug("Could not detach foreground input threads", exc_info=True)


def _apply_control_unlocked(message: dict):
    """Dispatch viewer events in the primary monitor's physical pixel coordinate space."""
    import pyautogui
    pyautogui.FAILSAFE = False
    event = message.get("event")
    if event == "mouse_move":
        size = pyautogui.size()
        global _PRIMARY_CAPTURE_SIZE
        if _PRIMARY_CAPTURE_SIZE is None or _PRIMARY_CAPTURE_SIZE[:2] != (size.width, size.height):
            try:
                import mss
                with mss.mss() as capture:
                    primary = capture.monitors[1]
                    capture_width = int(primary["width"])
                    capture_height = int(primary["height"])
            except Exception:
                capture_width, capture_height = size.width, size.height
            _PRIMARY_CAPTURE_SIZE = (size.width, size.height, capture_width, capture_height)
        _, _, capture_width, capture_height = _PRIMARY_CAPTURE_SIZE
        x = float(message.get("x", 0))
        y = float(message.get("y", 0))
        if not math.isfinite(x) or not math.isfinite(y):
            return False
        x = min(1.0, max(0.0, x))
        y = min(1.0, max(0.0, y))
        capture_x = x * max(1, capture_width - 1)
        capture_y = y * max(1, capture_height - 1)
        px = min(size.width - 1, max(0, round(capture_x * size.width / max(1, capture_width))))
        py = min(size.height - 1, max(0, round(capture_y * size.height / max(1, capture_height))))
        pyautogui.moveTo(px, py, _pause=False)
    elif event in ("mouse_down", "mouse_up"):
        _focus_target_at_cursor()
        button = {0: "left", 1: "middle", 2: "right"}.get(message.get("button"), "left")
        action = pyautogui.mouseDown if event == "mouse_down" else pyautogui.mouseUp
        action(button=button)
        if event == "mouse_down":
            _PRESSED_MOUSE_BUTTONS.add(button)
        else:
            _PRESSED_MOUSE_BUTTONS.discard(button)
    elif event == "text_input":
        text = message.get("text")
        if not isinstance(text, str) or not text or len(text) > 4096:
            return False
        _focus_target_at_cursor()
        try:
            if text.isascii() and text.isalnum():
                pyautogui.write(text, interval=0.01)
            else:
                raise UnicodeEncodeError("ascii", text, 0, len(text), "Spaces and Unicode require clipboard paste")
        except Exception:
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v", _pause=False)
    elif event in ("key_down", "key_up"):
        _focus_target_at_cursor()
        key = _normalize_key(message.get("key"))
        allowed = set(getattr(pyautogui, "KEYBOARD_KEYS", ()))
        if not key or (len(key) != 1 and key not in allowed):
            return False
        action = pyautogui.keyDown if event == "key_down" else pyautogui.keyUp
        action(key, _pause=False)
        if event == "key_down":
            _PRESSED_KEYS.add(key)
        else:
            _PRESSED_KEYS.discard(key)
    elif event == "mouse_scroll":
        _focus_target_at_cursor()
        dx = float(message.get("deltaX", 0))
        dy = float(message.get("deltaY", 0))
        if not math.isfinite(dx) or not math.isfinite(dy) or abs(dx) > 2400 or abs(dy) > 2400:
            return False
        vertical = _wheel_delta_units(dy)
        horizontal = _wheel_delta_units(dx)
        if vertical:
            pyautogui.scroll(int(-vertical / 120), _pause=False)
        if horizontal:
            # PyAutoGUI's Windows hscroll path is unreliable; inject the native
            # horizontal wheel event (signed 120-unit notches) instead.
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.mouse_event.argtypes = [
                ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
                ctypes.c_size_t,
            ]
            user32.mouse_event.restype = None
            user32.mouse_event(
                0x01000, 0, 0, ctypes.c_ulong(horizontal).value, 0
            )
    else:
        return False
    return True

def apply_control(message: dict):
    """Serialize host input dispatch across async WebSocket events."""
    with _INPUT_LOCK:
        return _apply_control_unlocked(message)

def release_all_inputs():
    """Release held keys and buttons whenever the viewer/relay session ends."""
    import pyautogui
    pyautogui.FAILSAFE = False
    for key in tuple(_PRESSED_KEYS):
        try:
            pyautogui.keyUp(key, _pause=False)
        except Exception:
            log.warning("Unable to release remote key %s", key)
        finally:
            _PRESSED_KEYS.discard(key)
    for button in tuple(_PRESSED_MOUSE_BUTTONS):
        try:
            pyautogui.mouseUp(button=button)
        except Exception:
            log.warning("Unable to release remote mouse button %s", button)
        finally:
            _PRESSED_MOUSE_BUTTONS.discard(button)

async def run_once(args, stop_event=None):
    import ssl
    import certifi
    import websockets
    endpoint = args.server.rstrip("/") + f"/ws/host/{args.device_id}"
    endpoint = endpoint.replace("https://", "wss://").replace("http://", "ws://")
    tls_context = ssl.create_default_context(cafile=certifi.where()) if endpoint.startswith("wss://") else None
    async with websockets.connect(
        endpoint, ssl=tls_context, max_size=8 * 1024 * 1024, ping_interval=15,
        ping_timeout=45, close_timeout=10, open_timeout=25, max_queue=32,
    ) as ws:
        await ws.send(json.dumps({"type":"auth","secret":args.secret}))
        response = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        if response.get("type") != "connected":
            set_status("Invalid device credential — sign in and re-link this computer")
            raise RuntimeError("Server rejected the device credential.")
        set_status("Connected to relay. Waiting for a viewer...")
        log.info("WebSocket connected device_id=%s ping_interval=15 ping_timeout=45", args.device_id)
        stream_task = None
        clipboard_task = None
        incoming_file = None
        incoming_transfers: dict[str, EndpointFileReceiver] = {}
        streaming = asyncio.Event()
        viewer_id = "unknown"
        recorder = None
        privacy_banner = None
        stop_task = None
        latency_task = None
        async def report_latency():
            while True:
                await asyncio.sleep(5)
                latency_seconds = getattr(ws, "latency", None)
                if _DIAGNOSTICS_CALLBACK:
                    _DIAGNOSTICS_CALLBACK(_LAST_ERROR, round(latency_seconds * 1000) if latency_seconds is not None else None)
        latency_task = asyncio.create_task(report_latency())
        if stop_event is not None:
            async def close_on_stop():
                await asyncio.to_thread(stop_event.wait)
                try:
                    await ws.send(json.dumps({"type":"host_disconnected"}))
                except Exception:
                    pass
                await ws.close(code=1000, reason="Host disconnected")
            stop_task = asyncio.create_task(close_on_stop())
        try:
            async for packet in ws:
                if isinstance(packet, bytes):
                    continue
                message = json.loads(packet)
                if message.get("type") == "viewer_joined":
                    viewer_id = str(message.get("viewer_id") or "unknown")
                    set_status("Waiting for host approval...")
                    if stream_task and not stream_task.done():
                        await ws.send(json.dumps({"type":"host_approved","recording":bool(recorder)}))
                        continue
                    if await ask_host_consent(args.device_id, args.dynamic_password):
                        try:
                            recorder = SessionRecorder(args.device_id, viewer_id)
                            recorder.start()
                        except Exception:
                            log.exception("Session recording could not start; refusing remote session")
                            recorder = None
                            await ws.send(json.dumps({"type":"host_denied","detail":"Local security recording could not start; session was not approved"}))
                            set_status("Session denied — security recording unavailable")
                            continue
                        streaming.set()
                        await ws.send(json.dumps({"type":"host_approved","recording":True}))
                        stream_task = asyncio.create_task(stream_screen(ws, streaming))
                        clipboard_task = asyncio.create_task(clipboard_watch(ws, streaming))
                        set_status("Connected (Live) · REC")
                    else:
                        await ws.send(json.dumps({"type":"host_denied"}))
                        set_status("Connection denied by host")
                elif message.get("type") == "viewer_left":
                    release_all_inputs()
                    streaming.clear()
                    if privacy_banner:
                        privacy_banner.stop()
                        privacy_banner = None
                    if recorder:
                        try:
                            recorder.stop()
                        except Exception:
                            log.exception("Session recording finalization failed")
                        recorder = None
                    if stream_task:
                        stream_task.cancel()
                        stream_task = None
                    if clipboard_task:
                        clipboard_task.cancel()
                        clipboard_task = None
                    if incoming_file:
                        incoming_file["handle"].close()
                        incoming_file = None
                    set_status("Viewer disconnected; waiting for a new request")
                elif message.get("type") == "text" and streaming.is_set():
                    try:
                        await asyncio.to_thread(apply_text, message)
                    except Exception as exc:
                        log.warning("Remote text injection failed: %s", exc)
                elif message.get("type") == "clipboard_paste" and streaming.is_set():
                    request_id = str(message.get("request_id") or "")
                    try:
                        pasted = await asyncio.to_thread(paste_clipboard, message.get("text", ""))
                        await ws.send(json.dumps({"type":"clipboard_ack","request_id":request_id,"success":bool(pasted)}))
                    except Exception as exc:
                        log.warning("Clipboard paste failed: %s", exc)
                        await ws.send(json.dumps({"type":"clipboard_ack","request_id":request_id,"success":False,"detail":"Host clipboard paste failed"}))
                elif message.get("type") == "clipboard_update" and streaming.is_set():
                    value = message.get("text", "")
                    if isinstance(value, str) and len(value) <= 65536:
                        try:
                            current = await asyncio.to_thread(pyperclip.paste)
                            if current != value:
                                await asyncio.to_thread(pyperclip.copy, value)
                        except Exception as exc:
                            log.warning("Clipboard update failed: %s", exc)
                elif message.get("type") == "clipboard_update" and streaming.is_set():
                    value = message.get("text", "")
                    if isinstance(value, str) and len(value) <= 65536:
                        try:
                            await asyncio.to_thread(__import__("pyperclip").copy, value)
                            if message.get("paste") is True:
                                await asyncio.to_thread(_focus_target_at_cursor)
                                import pyautogui
                                await asyncio.to_thread(pyautogui.hotkey, "ctrl", "v", _pause=False)
                        except Exception:
                            log.warning("Incoming clipboard update failed", exc_info=True)
                elif message.get("type") == "transfer_init" and streaming.is_set():
                    try:
                        transfer_id = str(message.get("transfer_id", ""))
                        name = Path(str(message.get("name", "received-file")).replace("\\", "/")).name[:180]
                        size = int(message["total_size"])
                        if not transfer_id or not 0 < size <= 50 * 1024 * 1024 or int(message["chunk_size"]) != 512 * 1024:
                            raise ValueError("Invalid transfer ID or file size")
                        destination = downloads_destination(name, transfer_id)
                        receiver = EndpointFileReceiver(
                            destination, transfer_id, size, str(message["sha256"]),
                            int(message["chunk_size"]), str(message.get("compression", "none")),
                        )
                        incoming_transfers[transfer_id] = receiver
                        await ws.send(json.dumps({"type":"transfer_resume_req","transfer_id":transfer_id,
                                                  "next_offset":receiver.next_offset,
                                                  "next_index":receiver.next_offset // receiver.chunk_size}))
                        log.info("Host accepted %s (%s bytes); saving to %s", name, size, destination)
                    except (KeyError, TypeError, ValueError, OSError) as exc:
                        await ws.send(json.dumps({"type":"transfer_error","transfer_id":str(message.get("transfer_id","")),
                                                  "detail":str(exc)[:200]}))
                elif message.get("type") == "transfer_chunk" and streaming.is_set():
                    transfer_id = str(message.get("transfer_id", ""))
                    receiver = incoming_transfers.get(transfer_id)
                    if receiver:
                        try:
                            encoded = base64.b64decode(message.get("data", ""), validate=True)
                            offset = receiver.append(int(message.get("offset", -1)), encoded, int(message.get("index", -1)))
                            await ws.send(json.dumps({"type":"transfer_ack","transfer_id":transfer_id,
                                                      "next_offset":offset,
                                                      "next_index":offset // receiver.chunk_size}))
                        except (ValueError, TypeError, OSError) as exc:
                            await ws.send(json.dumps({"type":"transfer_error","transfer_id":transfer_id,
                                                      "detail":str(exc)[:200]}))
                elif message.get("type") == "transfer_complete" and streaming.is_set():
                    transfer_id = str(message.get("transfer_id", ""))
                    receiver = incoming_transfers.get(transfer_id)
                    if receiver:
                        try:
                            destination = receiver.finalize()
                            incoming_transfers.pop(transfer_id, None)
                            await ws.send(json.dumps({"type":"transfer_complete","transfer_id":transfer_id,
                                                      "sha256":receiver.expected_sha256,"verified":True}))
                            log.info("Verified file transfer complete: %s", destination.name)
                        except (ValueError, OSError) as exc:
                            await ws.send(json.dumps({"type":"transfer_error","transfer_id":transfer_id,
                                                      "detail":str(exc)[:200]}))
                elif message.get("type") == "file_offer" and streaming.is_set():
                    name = str(message.get("name", "received-file"))[:180]
                    size = int(message.get("size", 0))
                    transfer_id = str(message.get("transfer_id", ""))
                    if 0 < size <= 50 * 1024 * 1024 and transfer_id:
                        destination = await asyncio.to_thread(choose_save_path, name)
                        if destination:
                            incoming_file = {"id":transfer_id,"size":size,"received":0,"handle":open(destination,"wb")}
                            await ws.send(json.dumps({"type":"file_accept","transfer_id":transfer_id}))
                            log.info("Receiving %s", name)
                        else:
                            await ws.send(json.dumps({"type":"file_reject","transfer_id":transfer_id}))
                elif message.get("type") == "file_chunk" and streaming.is_set():
                    if incoming_file and message.get("transfer_id") == incoming_file["id"]:
                        chunk = base64.b64decode(message.get("data", ""), validate=True)
                        if len(chunk) <= 192 * 1024 and incoming_file["received"] + len(chunk) <= incoming_file["size"]:
                            incoming_file["handle"].write(chunk)
                            incoming_file["received"] += len(chunk)
                elif message.get("type") == "file_complete" and streaming.is_set():
                    if incoming_file and message.get("transfer_id") == incoming_file["id"]:
                        complete = incoming_file["received"] == incoming_file["size"]
                        incoming_file["handle"].close()
                        transfer_id = incoming_file["id"]
                        incoming_file = None
                        if complete:
                            await ws.send(json.dumps({"type":"file_complete","transfer_id":transfer_id}))
                            log.info("File transfer completed.")
                        else:
                            log.warning("File transfer size mismatch; incomplete file retained.")
                elif message.get("type") == "control" and streaming.is_set():
                    try:
                        if message.get("event") == "privacy_screen":
                            mode = str(message.get("mode") or "banner")
                            if mode not in {"black", "banner"}:
                                raise ValueError("Unsupported privacy screen mode")
                            if message.get("enabled") is True:
                                if privacy_banner is None:
                                    privacy_banner = PrivacyBanner()
                                applied = privacy_banner.start(mode)
                                log.info("Privacy curtain enabled mode=%s; relay socket retained", mode)
                            else:
                                if privacy_banner:
                                    privacy_banner.stop()
                                    privacy_banner = None
                                applied = True
                                log.info("Privacy curtain disabled; relay socket retained")
                            await ws.send(json.dumps({"type":"privacy_screen_ack","enabled":bool(message.get("enabled")) and bool(applied),"mode":mode}))
                        else:
                            await asyncio.to_thread(apply_control, message)
                    except Exception as exc:
                        log.warning("Input event rejected: %s", exc)
                        if message.get("event") == "privacy_screen":
                            await ws.send(json.dumps({"type":"privacy_screen_ack","enabled":False,"mode":str(message.get("mode") or "banner"),"detail":"Privacy screen could not be applied"}))
        finally:
            try:
                release_all_inputs()
            except Exception:
                log.exception("Unable to release remote input state")
            if stop_task:
                stop_task.cancel()
            if latency_task:
                latency_task.cancel()
            streaming.clear()
            if privacy_banner:
                privacy_banner.stop()
            if recorder:
                try:
                    recorder.stop()
                except Exception:
                    log.exception("Session recording finalization failed during disconnect")
            if stream_task:
                stream_task.cancel()
            if clipboard_task:
                clipboard_task.cancel()
            if incoming_file:
                incoming_file["handle"].close()

async def run(args, stop_event=None):
    """Keep the host agent alive across transient relay/network interruptions."""
    attempt = 0
    while stop_event is None or not stop_event.is_set():
        attempt += 1
        retry_delay = min(2 ** min(attempt, 5), 30)
        try:
            if attempt > 1:
                set_status(f"Reconnecting (Attempt {attempt - 1})...")
            await run_once(args, stop_event)
            if stop_event is not None and stop_event.is_set():
                break
            set_status("Relay disconnected. Reconnecting...")
        except RuntimeError:
            raise
        except Exception as exc:
            log.warning("Relay/network interruption (%s); reconnecting in %ss.", exc, retry_delay)
            set_status("Server waking up / unreachable — retrying...")
        if stop_event is None:
            # The relay session and its async tasks have fully unwound here. A
            # synchronous wait is deliberate: the frozen Windows one-file build
            # can stall asyncio timer callbacks after a socket reset.
            log.info("Reconnect loop sleeping for %ss.", retry_delay)
            time.sleep(retry_delay)
            log.info("Reconnect delay elapsed; retrying relay.")
        elif stop_event.wait(retry_delay):
            break
    set_status("Disconnected by host")

def main():
    parser = argparse.ArgumentParser(description="Remote Desk Pro visible-consent host agent")
    parser.add_argument("--server", default=os.getenv("RDP_SERVER", "https://remote-desk-pro-pj29.onrender.com"))
    parser.add_argument("--device-id", default=os.getenv("RDP_DEVICE_ID"))
    parser.add_argument("--secret", default=os.getenv("RDP_AGENT_SECRET"))
    parser.add_argument("--dynamic-password", default=os.getenv("RDP_DYNAMIC_PASSWORD", ""))
    args = parser.parse_args()
    log.info("Startup mode: device_id_set=%s secret_set=%s", bool(args.device_id), bool(args.secret))
    set_windows_dpi_awareness()
    if not args.device_id and not args.secret:
        log.info("Launching native desktop GUI")
        try:
            from desktop_app import launch
            launch(args.server)
        except Exception:
            log.exception("Native desktop GUI startup failed")
            raise
        return
    if not args.device_id or not args.secret:
        parser.error("Provide both --device-id and --secret for headless mode.")
    if not acquire_single_instance():
        return
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        asyncio.run(run(args))
    finally:
        release_all_inputs()
        release_single_instance()

if __name__ == "__main__":
    main()
