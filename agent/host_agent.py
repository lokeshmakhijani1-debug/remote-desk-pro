"""Consent-gated host bridge with optional owner-authorized unattended sessions."""
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
import queue
import hashlib
import uuid
from pathlib import Path
try:
    from resumable_transfer import EndpointFileReceiver, EndpointTransferError
except ModuleNotFoundError:
    from agent.resumable_transfer import EndpointFileReceiver, EndpointTransferError
try:
    from privacy_overlay import PrivacyBanner
    from session_recorder import SessionRecorder, list_recordings, delete_recording, read_recording_chunk
except ModuleNotFoundError:
    from agent.privacy_overlay import PrivacyBanner
    from agent.session_recorder import SessionRecorder, list_recordings, delete_recording, read_recording_chunk
from logging.handlers import RotatingFileHandler
from io import BytesIO
try:
    from workflow_engine import WorkflowRecorder, WorkflowReplayEngine
    from telemetry import TelemetryTracker
except ModuleNotFoundError:
    from agent.workflow_engine import WorkflowRecorder, WorkflowReplayEngine
    from agent.telemetry import TelemetryTracker

APP_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "RemoteDeskPro")
os.makedirs(APP_DIR, exist_ok=True)
log = logging.getLogger("remote-desk-agent")
log.setLevel(logging.INFO)
if not log.handlers:
    _handler = RotatingFileHandler(os.path.join(APP_DIR, "agent.log"), maxBytes=2_000_000, backupCount=4, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(_handler)
_STATUS_CALLBACK = None
_CONSENT_CALLBACK = None
_FILE_CONSENT_CALLBACK = None
_DIAGNOSTICS_CALLBACK = None
_TELEMETRY_CALLBACK = None
_WORKFLOW_RECORDER = None
_WORKFLOW_RECORD_REQUESTED = False
_PRIVACY_SCREEN_ACTIVE = False
_LAST_ERROR = "None"
_INSTANCE_MUTEX = None
_PRESSED_KEYS = set()
_PRESSED_MOUSE_BUTTONS = set()
_PRIMARY_CAPTURE_SIZE = None
_FILE_SEND_QUEUE = queue.Queue()
_RECORDING_COMMAND_QUEUE = queue.Queue()
_OUTGOING_TRANSFER_STATE = Path(APP_DIR) / "outgoing-transfer.json"

def enqueue_file_send(path: str) -> None:
    candidate = Path(path).expanduser().resolve()
    if not candidate.is_file():
        raise FileNotFoundError("Selected file does not exist.")
    if candidate.stat().st_size <= 0 or candidate.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("Choose a file between 1 byte and 50 MB.")
    _FILE_SEND_QUEUE.put(str(candidate))

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def _save_outgoing_transfer(state: dict) -> None:
    temporary = _OUTGOING_TRANSFER_STATE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    os.replace(temporary, _OUTGOING_TRANSFER_STATE)
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

def set_telemetry_callback(callback):
    global _TELEMETRY_CALLBACK
    _TELEMETRY_CALLBACK = callback

def set_session_recording_requested(enabled: bool, settings: dict | None = None):
    """Queue an explicit local-video recording command from the desktop UI."""
    _RECORDING_COMMAND_QUEUE.put({"action": "start" if enabled else "stop", "settings": settings or {}})


def set_workflow_recorder(recorder):
    global _WORKFLOW_RECORDER
    _WORKFLOW_RECORDER = recorder
    _sync_workflow_recording_state()

def set_workflow_recording_requested(enabled: bool):
    global _WORKFLOW_RECORD_REQUESTED
    _WORKFLOW_RECORD_REQUESTED = bool(enabled)
    _sync_workflow_recording_state()

def _sync_workflow_recording_state():
    if _WORKFLOW_RECORDER is not None:
        try:
            _WORKFLOW_RECORDER.set_enabled(bool(_WORKFLOW_RECORD_REQUESTED and _PRIVACY_SCREEN_ACTIVE))
        except Exception:
            log.exception("Semantic workflow recorder state update failed")

def _set_privacy_screen_active(enabled: bool):
    global _PRIVACY_SCREEN_ACTIVE
    _PRIVACY_SCREEN_ACTIVE = bool(enabled)
    _sync_workflow_recording_state()

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
    tk.Label(root, text="A remote viewer is requesting access. Video recording is OFF by default and starts only after an explicit Start Recording action.", wraplength=360).pack(pady=12)
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


def is_unattended_auto_approve_enabled():
    env_pin = os.environ.get("RDP_UNATTENDED_PIN", "").strip()
    if len(env_pin) >= 4 and env_pin.isdigit():
        return True
    try:
        cfg_path = Path(os.environ.get("APPDATA", Path.home())) / "RemoteDeskPro" / "config.json"
        if cfg_path.exists():
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            pin = str(data.get("unattended_pin", "")).strip()
            if data.get("unattended_auto_approve") and len(pin) >= 4 and pin.isdigit():
                return True
    except Exception:
        pass
    return False

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
    tk.Label(root, text="AUTO_ACCEPTED_FILE_TRANSFER", font=("Segoe UI", 14, "bold")).pack(pady=(22, 10))
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
    folder = Path.home() / "Downloads"
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

async def stream_screen(ws, running: asyncio.Event, telemetry=None):
    while running.is_set():
        frame = encode_screen()
        await ws.send(frame)
        if telemetry is not None:
            telemetry.frame_sent(len(frame))
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
    if _WORKFLOW_RECORDER is not None:
        try:
            _WORKFLOW_RECORDER.record_control(message)
        except Exception:
            log.exception("Semantic action recording failed")
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
        endpoint, ssl=tls_context, max_size=8 * 1024 * 1024, ping_interval=5,
        ping_timeout=5, close_timeout=10, open_timeout=25, max_queue=16,
    ) as ws:
        await ws.send(json.dumps({"type":"auth","secret":args.secret}))
        response = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        if response.get("type") != "connected":
            set_status("Invalid device credential — sign in and re-link this computer")
            raise RuntimeError("Server rejected the device credential.")
        set_status("Connected to relay. Waiting for a viewer...")
        stream_task = None
        clipboard_task = None
        incoming_file = None
        incoming_transfers: dict[str, EndpointFileReceiver] = {}
        outgoing_transfers: dict[str, dict] = {}
        try:
            saved = json.loads(_OUTGOING_TRANSFER_STATE.read_text(encoding="utf-8"))
            saved_path = Path(saved["path"])
            if saved_path.is_file() and saved_path.stat().st_size == int(saved["total_size"]) and _sha256_file(saved_path) == saved["sha256"]:
                outgoing_transfers[str(saved["transfer_id"])] = saved
            else:
                _OUTGOING_TRANSFER_STATE.unlink(missing_ok=True)
        except FileNotFoundError:
            pass
        except Exception:
            _OUTGOING_TRANSFER_STATE.unlink(missing_ok=True)
            log.warning("Discarded invalid outgoing transfer checkpoint", exc_info=True)
        streaming = asyncio.Event()
        viewer_id = "unknown"
        recorder = None
        privacy_banner = None
        telemetry = TelemetryTracker()
        stop_task = None
        latency_task = None
        file_sender_task = None
        async def report_latency():
            while True:
                await asyncio.sleep(5)
                latency_seconds = getattr(ws, "latency", None)
                ping_ms = round(latency_seconds * 1000) if latency_seconds is not None else None
                telemetry.set_ping(ping_ms)
                if _DIAGNOSTICS_CALLBACK:
                    _DIAGNOSTICS_CALLBACK(_LAST_ERROR, ping_ms)
                metrics = telemetry.snapshot()
                if _TELEMETRY_CALLBACK:
                    _TELEMETRY_CALLBACK(metrics)
                await ws.send(json.dumps({"type":"telemetry", **metrics}))
        latency_task = asyncio.create_task(report_latency())
        async def send_outgoing_chunk(transfer_id: str, offset: int):
            state = outgoing_transfers.get(transfer_id)
            if not state:
                return
            size = int(state["total_size"]); chunk_size = int(state["chunk_size"])
            if offset < 0 or offset > size:
                await ws.send(json.dumps({"type":"transfer_error","transfer_id":transfer_id,"detail":"Invalid resume offset"}))
                return
            state["offset"] = offset
            _save_outgoing_transfer(state)
            if offset >= size:
                await ws.send(json.dumps({"type":"transfer_complete","transfer_id":transfer_id,"sha256":state["sha256"]}))
                return
            def read_chunk():
                with Path(state["path"]).open("rb") as stream:
                    stream.seek(offset)
                    return stream.read(min(chunk_size, size-offset))
            chunk = await asyncio.to_thread(read_chunk)
            if not chunk:
                await ws.send(json.dumps({"type":"transfer_error","transfer_id":transfer_id,"detail":"Source file became unreadable"}))
                return
            await ws.send(json.dumps({"type":"transfer_chunk","transfer_id":transfer_id,"offset":offset,"data":base64.b64encode(chunk).decode("ascii")}))
            telemetry.transfer_sent(len(chunk))
        async def send_queued_files():
            while True:
                if not streaming.is_set() or outgoing_transfers:
                    await asyncio.sleep(0.4)
                    continue
                try:
                    path = Path(await asyncio.to_thread(_FILE_SEND_QUEUE.get, True, 1))
                except queue.Empty:
                    continue
                try:
                    size = path.stat().st_size
                    if not 0 < size <= 50 * 1024 * 1024:
                        set_status("Outgoing file rejected: maximum size is 50 MB")
                        continue
                    digest = await asyncio.to_thread(_sha256_file, path)
                    transfer_id = uuid.uuid4().hex
                    state = {"transfer_id":transfer_id,"path":str(path),"name":path.name[:180],"total_size":size,"sha256":digest,"chunk_size":256*1024,"compression":"none","offset":0}
                    outgoing_transfers[transfer_id] = state
                    _save_outgoing_transfer(state)
                    await ws.send(json.dumps({"type":"transfer_init","transfer_id":transfer_id,"name":state["name"],"total_size":size,"sha256":digest,"chunk_size":state["chunk_size"],"compression":"none"}))
                    set_status("Waiting for viewer to accept outgoing file…")
                except Exception as exc:
                    log.warning("Could not initialize outgoing file transfer: %s", exc)
                    set_status("Outgoing file transfer could not start")
        file_sender_task = asyncio.create_task(send_queued_files())
        recording_timer_task = None
        recording_reason = None

        async def apply_recording_action(action: str, settings: dict | None = None):
            nonlocal recorder, recording_timer_task, recording_reason
            if action in ("stop", "privacy_stop"):
                if recorder is not None and recording_reason == "privacy" and action == "stop" and _PRIVACY_SCREEN_ACTIVE:
                    await ws.send(json.dumps({"type": "recording_status", "active": True, "reason": "privacy", "detail": "Privacy-triggered recording cannot be stopped while the host screen remains blanked."}))
                    return
                should_stop = recorder is not None and (action == "stop" or recording_reason == "privacy")
                if should_stop:
                    current, recorder = recorder, None
                    previous_reason, recording_reason = recording_reason, None
                    if recording_timer_task and recording_timer_task is not asyncio.current_task():
                        recording_timer_task.cancel()
                    await asyncio.to_thread(current.stop)
                    await ws.send(json.dumps({"type": "recording_status", "active": False, "reason": None,
                                              "detail": "Privacy security recording finalized locally." if previous_reason == "privacy" else "Recording saved locally."}))
                elif recorder is not None and recorder.is_alive:
                    await ws.send(json.dumps({"type": "recording_status", "active": True, "reason": recording_reason, "detail": "Manual recording continues after the privacy screen is removed."}))
                else:
                    await ws.send(json.dumps({"type": "recording_status", "active": False, "reason": None, "detail": "No active recording."}))
                return
            if action not in ("start", "privacy_start") or not streaming.is_set():
                await ws.send(json.dumps({"type": "recording_status", "active": False, "reason": None, "detail": "Recording requires an approved live session."}))
                return
            if recorder is not None and recorder.is_alive:
                await ws.send(json.dumps({"type": "recording_status", "active": True, "reason": recording_reason, "detail": "Recording is already active."}))
                return
            options = settings if isinstance(settings, dict) else {}
            if options.get("save_mode", "local") != "local":
                await ws.send(json.dumps({"type": "recording_status", "active": False, "reason": None, "detail": "Video publishing is not enabled; choose Save Locally."}))
                return
            max_duration = max(1, min(int(options.get("max_duration_seconds", 1800)), 14400))
            keep_last = max(1, min(int(options.get("retention_count", 5)), 100))
            storage_mb = max(100, min(int(options.get("max_storage_mb", 1024)), 20480))
            candidate = SessionRecorder(args.device_id, viewer_id, max_duration_seconds=max_duration,
                                        retention_count=keep_last, max_storage_mb=storage_mb)
            await asyncio.to_thread(candidate.start)
            recorder = candidate
            recording_reason = "privacy" if action == "privacy_start" else "manual"
            await ws.send(json.dumps({"type": "recording_status", "active": True, "reason": recording_reason,
                                      "detail": "Auto-recording active while screen is blanked" if recording_reason == "privacy" else "Local recording started."}))

            async def auto_stop(expected):
                await asyncio.sleep(max_duration)
                if recorder is expected:
                    await apply_recording_action("privacy_stop" if recording_reason == "privacy" else "stop")
                    await ws.send(json.dumps({"type": "recording_status", "active": False, "reason": None,
                                              "detail": "Maximum recording duration reached; recording auto-stopped."}))

            recording_timer_task = asyncio.create_task(auto_stop(candidate))

        async def consume_recording_commands():
            while True:
                try:
                    command = await asyncio.to_thread(_RECORDING_COMMAND_QUEUE.get, True, 1)
                except queue.Empty:
                    continue
                await apply_recording_action(command.get("action", "stop"), command.get("settings"))

        recording_command_task = asyncio.create_task(consume_recording_commands())
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
                        await ws.send(json.dumps({"type":"host_approved","recording":bool(recorder and recorder.is_alive)}))
                        for state in outgoing_transfers.values():
                            await ws.send(json.dumps({"type":"transfer_init","transfer_id":state["transfer_id"],"name":state["name"],"total_size":state["total_size"],"sha256":state["sha256"],"chunk_size":state["chunk_size"],"compression":"none"}))
                        continue
                    if is_unattended_auto_approve_enabled() or await ask_host_consent(args.device_id, args.dynamic_password):
                        streaming.set()
                        await ws.send(json.dumps({"type":"host_approved","recording":False}))
                        stream_task = asyncio.create_task(stream_screen(ws, streaming, telemetry))
                        clipboard_task = asyncio.create_task(clipboard_watch(ws, streaming))
                        for state in outgoing_transfers.values():
                            await ws.send(json.dumps({"type":"transfer_init","transfer_id":state["transfer_id"],"name":state["name"],"total_size":state["total_size"],"sha256":state["sha256"],"chunk_size":state["chunk_size"],"compression":"none"}))
                        set_status("Connected (Live) · Recording off")
                    else:
                        await ws.send(json.dumps({"type":"host_denied"}))
                        set_status("Connection denied by host")
                elif message.get("type") == "recording_list" and streaming.is_set():
                    try:
                        recordings = await asyncio.to_thread(list_recordings)
                        await ws.send(json.dumps({"type": "recording_list_result", "recordings": recordings}))
                    except Exception:
                        log.exception("Recording list request failed")
                        await ws.send(json.dumps({"type": "recording_error", "detail": "Could not list host recordings"}))
                elif message.get("type") == "recording_delete" and streaming.is_set():
                    try:
                        filename = str(message.get("filename", ""))
                        await asyncio.to_thread(delete_recording, filename)
                        recordings = await asyncio.to_thread(list_recordings)
                        await ws.send(json.dumps({"type": "recording_deleted", "filename": filename, "recordings": recordings}))
                    except (ValueError, OSError, FileNotFoundError):
                        await ws.send(json.dumps({"type": "recording_error", "detail": "Recording could not be deleted"}))
                    except Exception:
                        log.exception("Recording delete request failed")
                        await ws.send(json.dumps({"type": "recording_error", "detail": "Recording delete failed"}))
                elif message.get("type") == "recording_download_chunk" and streaming.is_set():
                    try:
                        payload = await asyncio.to_thread(read_recording_chunk, str(message.get("filename", "")), message.get("offset", 0), message.get("length", 131072))
                        await ws.send(json.dumps({"type": "recording_chunk_result", **payload}))
                    except (ValueError, OSError, FileNotFoundError):
                        await ws.send(json.dumps({"type": "recording_error", "detail": "Recording chunk request rejected"}))
                    except Exception:
                        log.exception("Recording chunk request failed")
                        await ws.send(json.dumps({"type": "recording_error", "detail": "Recording download failed"}))
                elif message.get("type") == "recording_control" and streaming.is_set():
                    try:
                        await apply_recording_action(str(message.get("action", "stop")), message.get("settings"))
                    except Exception as exc:
                        log.exception("Explicit recording command failed")
                        await ws.send(json.dumps({"type": "recording_status", "active": False,
                                                  "detail": "Recording command failed: " + str(exc)[:180]}))
                elif message.get("type") == "viewer_left":
                    _set_privacy_screen_active(False)
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
                elif message.get("type") == "transfer_resume_req" and streaming.is_set():
                    transfer_id = str(message.get("transfer_id", ""))
                    if transfer_id in outgoing_transfers:
                        await send_outgoing_chunk(transfer_id, int(message.get("next_offset", 0)))
                elif message.get("type") == "transfer_ack" and streaming.is_set():
                    transfer_id = str(message.get("transfer_id", ""))
                    if transfer_id in outgoing_transfers:
                        await send_outgoing_chunk(transfer_id, int(message.get("next_offset", 0)))
                elif message.get("type") == "transfer_init" and streaming.is_set():
                    try:
                        transfer_id = str(message.get("transfer_id", ""))
                        name = Path(str(message.get("name", "received-file")).replace("\\", "/")).name[:180]
                        size = int(message["total_size"])
                        if not transfer_id or not 0 < size <= 50 * 1024 * 1024:
                            raise ValueError("Invalid transfer ID or file size")
                        if not await ask_file_consent(name, size):
                            await ws.send(json.dumps({"type":"transfer_error","transfer_id":transfer_id,
                                                      "detail":"Host declined the file transfer"}))
                            continue
                        destination = downloads_destination(name, transfer_id)
                        receiver = EndpointFileReceiver(
                            destination, transfer_id, size, str(message["sha256"]),
                            int(message["chunk_size"]), str(message.get("compression", "none")),
                        )
                        incoming_transfers[transfer_id] = receiver
                        await ws.send(json.dumps({"type":"transfer_resume_req","transfer_id":transfer_id,
                                                  "next_offset":receiver.next_offset}))
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
                            telemetry.transfer_received(len(encoded))
                            offset = receiver.append(int(message.get("offset", -1)), encoded)
                            await ws.send(json.dumps({"type":"transfer_ack","transfer_id":transfer_id,
                                                      "next_offset":offset}))
                        except (ValueError, TypeError, OSError) as exc:
                            await ws.send(json.dumps({"type":"transfer_error","transfer_id":transfer_id,
                                                      "detail":str(exc)[:200]}))
                elif message.get("type") == "transfer_complete" and streaming.is_set():
                    transfer_id = str(message.get("transfer_id", ""))
                    outgoing = outgoing_transfers.get(transfer_id)
                    if outgoing:
                        verified = bool(message.get("verified")) and str(message.get("sha256", "")).lower() == outgoing["sha256"]
                        outgoing_transfers.pop(transfer_id, None)
                        _OUTGOING_TRANSFER_STATE.unlink(missing_ok=True)
                        set_status("Outgoing file delivered and SHA-256 verified" if verified else "Viewer did not verify the outgoing file")
                        continue
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
                elif message.get("type") == "transfer_error" and streaming.is_set():
                    transfer_id = str(message.get("transfer_id", ""))
                    if transfer_id in outgoing_transfers:
                        outgoing_transfers.pop(transfer_id, None)
                        _OUTGOING_TRANSFER_STATE.unlink(missing_ok=True)
                        set_status("Viewer rejected or could not receive the outgoing file")
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
                        if message.get("event") == "workflow_replay":
                            try:
                                replay_engine = WorkflowReplayEngine()
                                target = replay_engine.latest()
                                if target is None:
                                    raise FileNotFoundError("No saved host-local workflow is available.")
                                result = await asyncio.to_thread(replay_engine.replay, target)
                                detail = f"Workflow replayed: {int(result.get('executed', 0))} steps."
                            except Exception as exc:
                                detail = "Workflow replay failed: " + str(exc)[:180]
                            await ws.send(json.dumps({"type":"workflow_replay_status","detail":detail}))
                        elif message.get("event") == "privacy_screen":
                            mode = message.get("mode") if message.get("mode") in ("black", "banner") else "black"
                            if message.get("enabled") is True:
                                if privacy_banner is None:
                                    privacy_banner = PrivacyBanner()
                                applied = privacy_banner.start(mode=mode)
                            else:
                                if privacy_banner:
                                    privacy_banner.stop()
                                    privacy_banner = None
                                applied = True
                            privacy_enabled = bool(message.get("enabled")) and bool(applied)
                            if privacy_enabled:
                                _set_privacy_screen_active(True)
                                try:
                                    await apply_recording_action("privacy_start")
                                except Exception:
                                    if privacy_banner:
                                        privacy_banner.stop()
                                        privacy_banner = None
                                    _set_privacy_screen_active(False)
                                    raise
                            else:
                                _set_privacy_screen_active(False)
                                await apply_recording_action("privacy_stop")
                            await ws.send(json.dumps({"type":"privacy_screen_ack","enabled":privacy_enabled,"mode":mode}))
                        else:
                            await asyncio.to_thread(apply_control, message)
                    except Exception as exc:
                        log.warning("Input event rejected: %s", exc)
                        if message.get("event") == "privacy_screen":
                            await ws.send(json.dumps({"type":"privacy_screen_ack","enabled":False,"mode":"banner","detail":"Maintenance banner could not be applied"}))
        finally:
            try:
                release_all_inputs()
            except Exception:
                log.exception("Unable to release remote input state")
            if stop_task:
                stop_task.cancel()
            if latency_task:
                latency_task.cancel()
            if recording_command_task:
                recording_command_task.cancel()
            if recording_timer_task:
                recording_timer_task.cancel()
            if file_sender_task:
                file_sender_task.cancel()
            streaming.clear()
            _set_privacy_screen_active(False)
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

def calculate_backoff(attempt: int, base: int = 2, cap: int = 30) -> int:
    """Bounded exponential reconnect delay; first retry waits two seconds."""
    exponent = max(0, min(10, int(attempt) - 1))
    return min(max(1, int(cap)), max(1, int(base)) * (2 ** exponent))

async def run(args, stop_event=None):
    """Keep the host agent alive across transient relay/network interruptions."""
    retry_delay = 2
    attempt = 0
    while stop_event is None or not stop_event.is_set():
        attempt += 1
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
        retry_delay = calculate_backoff(attempt)
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
    parser.add_argument("--server", default=os.getenv("RDP_SERVER", "http://127.0.0.1:8000"))
    parser.add_argument("--viewer", action="store_true", help="Open the embedded viewer for this relay server.")
    parser.add_argument("--device-id", default=os.getenv("RDP_DEVICE_ID"))
    parser.add_argument("--secret", default=os.getenv("RDP_AGENT_SECRET"))
    parser.add_argument("--dynamic-password", default=os.getenv("RDP_DYNAMIC_PASSWORD", ""))
    args = parser.parse_args()
    if args.viewer:
        try:
            import webview
        except ImportError:
            parser.error("Embedded viewer support is unavailable; rebuild with pywebview installed.")
        webview.create_window("Remote Desk Pro — Viewer", args.server.rstrip("/") + "/", width=1360, height=900, min_size=(900, 600))
        webview.start(gui="edgechromium")
        return
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
