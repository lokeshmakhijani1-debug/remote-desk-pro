"""Native Remote Desk Pro enrollment and host console."""
from __future__ import annotations
import asyncio
import base64
import ctypes
import concurrent.futures
import json
import logging
import os
import sys
import subprocess
import threading
import time
import urllib.error
import urllib.request
from ctypes import wintypes
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

DEFAULT_SERVER = os.getenv("RDP_SERVER", "http://127.0.0.1:8000").rstrip("/")
APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "RemoteDeskPro"
CONFIG_FILE = APP_DIR / "config.json"
LOG_FILE = APP_DIR / "agent.log"
logger = logging.getLogger("remote-desk-agent")
_INSTANCE_MUTEX = None

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
        logger.debug("Could not focus existing GUI window", exc_info=True)

def _acquire_single_instance():
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

def _release_single_instance():
    global _INSTANCE_MUTEX
    if _INSTANCE_MUTEX and os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.ReleaseMutex(_INSTANCE_MUTEX)
        kernel32.CloseHandle(_INSTANCE_MUTEX)
        _INSTANCE_MUTEX = None
logger.setLevel(logging.INFO)
APP_DIR.mkdir(parents=True, exist_ok=True)
from logging.handlers import RotatingFileHandler
if not logger.handlers:
    handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=4, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

def _dpapi(value: bytes, protect: bool) -> bytes:
    if os.name != "nt":
        return value
    crypt = ctypes.windll.crypt32
    kernel = ctypes.windll.kernel32
    crypt.CryptProtectData.argtypes = [ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(DATA_BLOB), wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
    crypt.CryptProtectData.restype = wintypes.BOOL
    crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(DATA_BLOB), wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
    crypt.CryptUnprotectData.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    source = ctypes.create_string_buffer(value)
    blob = DATA_BLOB(len(value), ctypes.cast(source, ctypes.POINTER(ctypes.c_byte)))
    output = DATA_BLOB()
    if protect:
        ok = crypt.CryptProtectData(ctypes.byref(blob), "RemoteDeskPro", None, None, None, 0x1, ctypes.byref(output))
    else:
        ok = crypt.CryptUnprotectData(ctypes.byref(blob), None, None, None, None, 0x1, ctypes.byref(output))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel.LocalFree(output.pbData)

def _seal(value: str) -> str:
    return base64.b64encode(_dpapi(value.encode("utf-8"), True)).decode("ascii")

def _unseal(value: str) -> str:
    return _dpapi(base64.b64decode(value), False).decode("utf-8")

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if data.get("device_secret_enc"):
            data["device_secret"] = _unseal(data.pop("device_secret_enc"))
        if data.get("access_token_enc"):
            data["access_token"] = _unseal(data.pop("access_token_enc"))
        if data.get("dynamic_password_enc"):
            data["dynamic_password"] = _unseal(data.pop("dynamic_password_enc"))
        if data.get("unattended_pin_enc"):
            data["unattended_pin"] = _unseal(data.pop("unattended_pin_enc"))
        return data
    except Exception:
        logger.exception("Unable to read protected local configuration")
        return {}

def save_config(data: dict) -> None:
    safe = {k: v for k, v in data.items() if k not in ("device_secret", "access_token", "dynamic_password", "unattended_pin")}
    if data.get("device_secret"):
        safe["device_secret_enc"] = _seal(data["device_secret"])
    if data.get("access_token"):
        safe["access_token_enc"] = _seal(data["access_token"])
    if data.get("dynamic_password"):
        safe["dynamic_password_enc"] = _seal(data["dynamic_password"])
    if data.get("unattended_pin"):
        safe["unattended_pin_enc"] = _seal(str(data["unattended_pin"]))
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temp = CONFIG_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(safe, indent=2), encoding="utf-8")
    os.replace(temp, CONFIG_FILE)

def api(server: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(server.rstrip("/") + path, data=payload, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("detail", f"HTTP {exc.code}")
        except Exception:
            detail = f"HTTP {exc.code}"
        raise RuntimeError(str(detail)) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("Server waking up / unreachable — retrying...") from exc

class DesktopApp:
    def __init__(self, server=None):
        self.root = tk.Tk()
        self.root.title("Remote Desk Pro")
        self.root.geometry("500x740")
        self.root.minsize(460, 680)
        self.root.configure(bg="#f3f6fa")
        self._set_system_awake(True)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.config = load_config()
        saved_pin = str(self.config.get("unattended_pin", "")).strip()
        if self.config.get("unattended_auto_approve") and 4 <= len(saved_pin) <= 8 and saved_pin.isdigit():
            os.environ["RDP_UNATTENDED_PIN"] = saved_pin
        else:
            os.environ.pop("RDP_UNATTENDED_PIN", None)
        self.server = self.config.get("server") or server or DEFAULT_SERVER
        self.running = False
        self.session_live = False
        self.agent_thread = None
        self.agent_args = None
        self.stop_event = threading.Event()
        self.attempt = 0
        self.last_error = "None"
        self.latency_ms = None
        try:
            from workflow_engine import WorkflowRecorder, WorkflowReplayEngine
        except ModuleNotFoundError:
            from agent.workflow_engine import WorkflowRecorder, WorkflowReplayEngine
        self.workflow_recorder = WorkflowRecorder()
        self.workflow_engine = WorkflowReplayEngine()
        self._workflow_prompted_path = None
        self.telemetry_snapshot = {"fps": 0.0, "ping_ms": None, "upload_kbps": 0.0, "download_kbps": 0.0}
        self.status_var = tk.StringVar(value="Not connected")
        self.id_var = tk.StringVar(value=self.config.get("device_id", "Not paired"))
        self.password_var = tk.StringVar(value=self.config.get("dynamic_password", "••••••"))
        self._build()
        self.root.deiconify()
        self.root.lift()
        self.root.after(750, self._poll_workflow_save)
        if self.config.get("device_id") and self.config.get("device_secret"):
            self.root.after(250, self._start_existing)
        else:
            self.root.after(250, self._show_login)

    def _build(self):
        tk.Label(self.root, text="REMOTE DESK PRO", bg="#f3f6fa", fg="#087d65", font=("Segoe UI", 10, "bold")).pack(pady=(22, 2))
        tk.Label(self.root, text="Your computer, ready for secure remote support", bg="#f3f6fa", fg="#25364d", font=("Segoe UI", 16, "bold")).pack(pady=(0, 8))
        tk.Button(self.root, text="Open Viewer / Take Control", command=self._open_viewer, bg="#087d65", fg="white", relief="flat", padx=12, pady=7).pack(pady=(0, 4))
        tk.Button(self.root, text="Send File to Connected Viewer", command=self._send_file_to_viewer, bg="#ffffff", fg="#087d65", relief="solid", bd=1, padx=10, pady=5).pack(pady=(0, 8))
        card = tk.Frame(self.root, bg="white", highlightbackground="#e0e7ef", highlightthickness=1)
        card.pack(fill="x", padx=24, pady=8)
        tk.Label(card, text="YOUR ID", bg="white", fg="#7b8ba1", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(18, 4))
        row = tk.Frame(card, bg="white"); row.pack(fill="x", padx=18)
        tk.Label(row, textvariable=self.id_var, bg="white", fg="#17243a", font=("Segoe UI", 23, "bold")).pack(side="left")
        tk.Button(row, text="Copy", command=lambda: self._copy(self.id_var.get()), relief="flat", bg="#e8f6f1", fg="#087d65").pack(side="right")
        tk.Label(card, text="DYNAMIC PASSWORD", bg="white", fg="#7b8ba1", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(18, 4))
        row2 = tk.Frame(card, bg="white"); row2.pack(fill="x", padx=18, pady=(0, 18))
        tk.Label(row2, textvariable=self.password_var, bg="white", fg="#17243a", font=("Segoe UI", 23, "bold")).pack(side="left")
        tk.Button(row2, text="Copy", command=lambda: self._copy(self.password_var.get()), relief="flat", bg="#e8f6f1", fg="#087d65").pack(side="right")
        self.rotate_btn = tk.Button(card, text="↻  Rotate Password", command=self.rotate_password, bg="#ffffff", fg="#52637a", relief="solid", bd=1)
        self.rotate_btn.pack(fill="x", padx=18, pady=(0, 8))
        tk.Button(card, text="Disconnect host agent", command=self.disconnect, bg="#fff5f5", fg="#b42318", relief="flat").pack(fill="x", padx=18, pady=(0, 18))
        status = tk.Frame(self.root, bg="white", highlightbackground="#e0e7ef", highlightthickness=1)
        status.pack(fill="x", padx=24, pady=8)
        tk.Label(status, text="CONNECTION STATUS", bg="white", fg="#7b8ba1", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(12, 3))
        tk.Label(status, textvariable=self.status_var, bg="white", fg="#087d65", font=("Segoe UI", 11, "bold"), wraplength=420).pack(anchor="w", padx=14, pady=(0, 12))
        unattended_card = tk.Frame(self.root, bg="white", highlightbackground="#e0e7ef", highlightthickness=1)
        unattended_card.pack(fill="x", padx=24, pady=6)
        self.unattended_var = tk.BooleanVar(value=bool(self.config.get("unattended_auto_approve", False)))
        self.unattended_pin_var = tk.StringVar(value=str(self.config.get("unattended_pin", "")))
        tk.Checkbutton(unattended_card, text="Unattended Trusted Auto-Approve (No Popup)", variable=self.unattended_var, command=self._save_unattended, bg="white", fg="#17243a", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(8, 4))
        pin_row = tk.Frame(unattended_card, bg="white"); pin_row.pack(fill="x", padx=14, pady=(0, 8))
        tk.Label(pin_row, text="Trusted PIN (4-8 digits):", bg="white", fg="#52637a", font=("Segoe UI", 8)).pack(side="left")
        tk.Entry(pin_row, textvariable=self.unattended_pin_var, show="*", width=12).pack(side="left", padx=8)
        tk.Button(pin_row, text="Save PIN", command=self._save_unattended, bg="#087d65", fg="white", relief="flat", padx=10).pack(side="right")
        workflow_card = tk.Frame(self.root, bg="white", highlightbackground="#e0e7ef", highlightthickness=1)
        workflow_card.pack(fill="x", padx=24, pady=6)
        self.workflow_record_var = tk.BooleanVar(value=False)
        self.session_recording_var = tk.BooleanVar(value=False)
        self.recording_duration_var = tk.IntVar(value=int(self.config.get("recording_max_minutes", 30)))
        self.recording_retention_var = tk.IntVar(value=int(self.config.get("recording_retention_count", 5)))
        self.recording_storage_var = tk.IntVar(value=int(self.config.get("recording_max_storage_mb", 1024)))
        tk.Checkbutton(workflow_card, text="Record semantic actions only while privacy blank-screen is active", variable=self.workflow_record_var, command=self._set_workflow_recording, bg="white", fg="#17243a", font=("Segoe UI", 8, "bold"), wraplength=390).pack(anchor="w", padx=12, pady=(8, 3))
        tk.Button(workflow_card, text="Workflow History", command=self._open_workflow_history, bg="#ffffff", fg="#52637a", relief="solid", bd=1).pack(fill="x", padx=12, pady=(2, 8))
        tk.Checkbutton(workflow_card, text="Start / Stop MP4 session recording (off by default)", variable=self.session_recording_var, command=self._set_session_recording, bg="white", fg="#17243a", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(2, 4))
        tk.Button(workflow_card, text="Recording & Storage Settings", command=self._recording_settings_dialog, bg="#ffffff", fg="#52637a", relief="solid", bd=1).pack(fill="x", padx=12, pady=(0, 8))
        tk.Button(workflow_card, text="Replay latest saved workflow", command=self._replay_latest_workflow, bg="#ffffff", fg="#52637a", relief="solid", bd=1).pack(fill="x", padx=12, pady=(0, 8))
        self.diag = tk.Frame(self.root, bg="#f3f6fa")
        self.diag.pack(fill="x", padx=24, pady=6)
        self.diag_visible = False
        tk.Button(self.diag, text="Connection Diagnostics  ▾", command=self._toggle_diag, relief="flat", bg="#f3f6fa", fg="#53637a").pack(anchor="w")
        self.diag_text = tk.Label(self.diag, text=self._diagnostics_text(), bg="#f3f6fa", fg="#718096", justify="left", font=("Consolas", 8))
        tk.Button(self.root, text="Sign out / Re-link account", command=self._show_login, bg="#ffffff", fg="#53637a", relief="solid", bd=1).pack(fill="x", padx=24, pady=(10, 5))
        tk.Label(self.root, text="Manual approval is the default. Trusted unattended mode requires the owner's saved PIN.", bg="#f3f6fa", fg="#718096", wraplength=430, font=("Segoe UI", 8)).pack(pady=12)

    def _sync_unattended_pin_to_server(self, pin_value: str):
        did = self.config.get("device_id")
        sec = self.config.get("device_secret")
        if not did or not sec:
            return
        def worker():
            try:
                api(self.server, f"/api/devices/{did}/agent-unattended-pin", {"agent_secret": sec, "pin": pin_value})
            except Exception:
                logger.warning("Could not sync unattended PIN to server", exc_info=True)
        threading.Thread(target=worker, daemon=True).start()

    def _save_unattended(self):
        pin = self.unattended_pin_var.get().strip()
        enabled = bool(self.unattended_var.get())
        if enabled and (len(pin) < 4 or len(pin) > 8 or not pin.isdigit()):
            self.unattended_var.set(False)
            self.status_var.set("Set a 4-8 digit numeric PIN before enabling Unattended Auto-Approve")
            return
        self.config["unattended_auto_approve"] = enabled
        self.config["unattended_pin"] = pin
        save_config(self.config)
        if enabled:
            os.environ["RDP_UNATTENDED_PIN"] = pin
            self._sync_unattended_pin_to_server(pin)
            self.status_var.set("Unattended Trusted PIN active and synced (Auto-Approve ON)")
        else:
            os.environ.pop("RDP_UNATTENDED_PIN", None)
            self._sync_unattended_pin_to_server("")
            self.status_var.set("Unattended Auto-Approve disabled (Manual approval required)")

    def _open_viewer(self):
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--viewer", "--server", self.server]
        else:
            command = [sys.executable, str(Path(__file__).with_name("host_agent.py")), "--viewer", "--server", self.server]
        try:
            subprocess.Popen(command, close_fds=True)
        except Exception as exc:
            messagebox.showerror("Viewer could not start", str(exc))

    def _send_file_to_viewer(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.root, title="Choose a file to send to the viewer")
        if not path:
            return
        try:
            try:
                import host_agent
            except ModuleNotFoundError:
                from agent import host_agent
            host_agent.enqueue_file_send(path)
            self.status_var.set("File queued; it will be offered to the next approved viewer session.")
        except Exception as exc:
            messagebox.showerror("File could not be queued", str(exc))

    def _set_session_recording(self):
        enabled = bool(self.session_recording_var.get())
        if enabled and not self.session_live:
            self.session_recording_var.set(False)
            self.status_var.set("Connect and approve a live viewer session before starting recording.")
            return
        try:
            import host_agent
        except ModuleNotFoundError:
            from agent import host_agent
        settings = {
            "max_duration_seconds": max(1, min(240, self.recording_duration_var.get())) * 60,
            "retention_count": max(1, min(100, self.recording_retention_var.get())),
            "max_storage_mb": max(100, min(20480, self.recording_storage_var.get())),
            "save_mode": "local",
        }
        host_agent.set_session_recording_requested(enabled, settings)
        self.status_var.set("Recording start requested — saved locally only." if enabled else "Recording stop requested.")

    def _recording_settings_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Recording & Storage Settings")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()
        fields = [
            ("Maximum duration (minutes)", self.recording_duration_var, 1, 240),
            ("Keep last N recordings", self.recording_retention_var, 1, 100),
            ("Storage cap (MB)", self.recording_storage_var, 100, 20480),
        ]
        tk.Label(dialog, text="Recording & Storage Settings", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 8))
        for label, variable, minimum, maximum in fields:
            tk.Label(dialog, text=label).pack(anchor="w", padx=16, pady=(8, 2))
            tk.Spinbox(dialog, from_=minimum, to=maximum, textvariable=variable, width=12).pack(anchor="w", padx=16)
        tk.Label(dialog, text="Destination: Save Locally. Community video publishing is disabled.", fg="#087d65").pack(anchor="w", padx=16, pady=12)
        def save():
            self.config.update({
                "recording_max_minutes": max(1, min(240, self.recording_duration_var.get())),
                "recording_retention_count": max(1, min(100, self.recording_retention_var.get())),
                "recording_max_storage_mb": max(100, min(20480, self.recording_storage_var.get())),
            })
            save_config(self.config)
            dialog.destroy()
            self.status_var.set("Recording settings saved.")
        tk.Button(dialog, text="Save Settings", command=save, bg="#087d65", fg="white", relief="flat").pack(fill="x", padx=16, pady=(0, 16))

    def _set_workflow_recording(self):
        enabled = bool(self.workflow_record_var.get())
        try:
            import host_agent
        except ModuleNotFoundError:
            from agent import host_agent
        host_agent.set_workflow_recording_requested(enabled)
        self.status_var.set("Action recording is armed; it records only while the privacy screen is active." if enabled else "Semantic action recording disabled.")

    def _poll_workflow_save(self):
        try:
            target = self.workflow_recorder.last_saved
            if target and target.is_file() and str(target) != self._workflow_prompted_path:
                self._workflow_prompted_path = str(target)
                self._prompt_workflow_metadata(target)
        except Exception:
            logger.exception("Workflow save prompt failed")
        finally:
            if self.root.winfo_exists():
                self.root.after(750, self._poll_workflow_save)

    def _prompt_workflow_metadata(self, target):
        dialog = tk.Toplevel(self.root)
        dialog.title("Save recorded workflow")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()
        tk.Label(dialog, text="Name this workflow", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
        name_var = tk.StringVar(value="Workflow " + time.strftime("%Y-%m-%d %H:%M"))
        name_entry = tk.Entry(dialog, textvariable=name_var, width=48)
        name_entry.pack(fill="x", padx=16)
        tk.Label(dialog, text="Tags (comma-separated)", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(10, 3))
        tags_var = tk.StringVar()
        tk.Entry(dialog, textvariable=tags_var, width=48).pack(fill="x", padx=16)
        tk.Label(dialog, text="Notes", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(10, 3))
        notes = tk.Text(dialog, width=48, height=4, wrap="word")
        notes.pack(fill="x", padx=16)
        tk.Label(dialog, text="Saved locally on this device. Nothing is uploaded or shared.", fg="#087d65").pack(anchor="w", padx=16, pady=8)
        def save():
            try:
                try:
                    from workflow_engine import annotate_workflow
                except ModuleNotFoundError:
                    from agent.workflow_engine import annotate_workflow
                saved = annotate_workflow(target, name_var.get(), tags_var.get().split(","), notes.get("1.0", "end").strip())
                self._workflow_prompted_path = str(saved)
                self.status_var.set("Workflow saved locally: " + saved.stem)
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Workflow could not be saved", str(exc), parent=dialog)
        buttons = tk.Frame(dialog); buttons.pack(fill="x", padx=16, pady=(0, 14))
        tk.Button(buttons, text="Save locally", command=save, bg="#087d65", fg="white", relief="flat").pack(side="right")
        tk.Button(buttons, text="Keep unnamed", command=dialog.destroy, relief="flat").pack(side="right", padx=8)
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        name_entry.focus_set()

    def _open_workflow_history(self):
        try:
            try:
                from workflow_engine import list_workflows
            except ModuleNotFoundError:
                from agent.workflow_engine import list_workflows
            paths = list_workflows()
            if not paths:
                messagebox.showinfo("Workflow History", "No locally saved workflows yet.", parent=self.root)
                return
            dialog = tk.Toplevel(self.root); dialog.title("Local Workflow History"); dialog.geometry("520x360")
            listing = tk.Listbox(dialog, height=12, activestyle="dotbox")
            listing.pack(fill="both", expand=True, padx=12, pady=12)
            for path in paths:
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    title = str(data.get("name") or path.stem)
                    tags = ", ".join(data.get("tags", []))
                    listing.insert("end", title + (("  |  " + tags) if tags else ""))
                except Exception:
                    listing.insert("end", path.stem + "  |  unreadable")
            def replay_selected():
                selected = listing.curselection()
                if not selected:
                    return
                dialog.destroy()
                self._replay_workflow_path(paths[selected[0]])
            listing.bind("<Double-Button-1>", lambda _event: replay_selected())
            tk.Button(dialog, text="Replay selected workflow", command=replay_selected).pack(pady=(0, 12))
        except Exception as exc:
            messagebox.showerror("Workflow History", str(exc), parent=self.root)

    def _replay_workflow_path(self, target):
        def replay():
            try:
                result = self.workflow_engine.replay(target)
                message = f"Workflow replayed: {result['executed']} steps."
                if result.get("warnings"):
                    message += " Adaptation warnings: " + "; ".join(result["warnings"][:3])
            except Exception as exc:
                message = "Workflow replay failed: " + str(exc)
            self.root.after(0, lambda: self.status_var.set(message))
        threading.Thread(target=replay, daemon=True, name="RDPWorkflowReplay").start()

    def _replay_latest_workflow(self):
        target = self.workflow_engine.latest()
        if target is None:
            self.status_var.set("No saved workflow exists yet.")
            return
        def replay():
            try:
                result = self.workflow_engine.replay(target)
                message = f"Workflow replayed: {result['executed']} steps."
                if result.get("warnings"):
                    message += " Some target applications were not found."
            except Exception as exc:
                message = "Workflow replay failed: " + str(exc)
            self.root.after(0, lambda: self.status_var.set(message))
        threading.Thread(target=replay, daemon=True, name="RDPWorkflowReplay").start()

    def _toggle_diag(self):
        self.diag_visible = not self.diag_visible
        if self.diag_visible:
            self.diag_text.pack(anchor="w", padx=8, pady=5)
        else:
            self.diag_text.pack_forget()

    def _set_system_awake(self, enabled: bool):
        if os.name != "nt":
            return
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(
                0x80000001 if enabled else 0x80000000
            )
        except Exception:
            logger.warning("Unable to update Windows execution state", exc_info=True)

    def close(self):
        if self.running:
            self.stop_event.set()
            self.running = False
        self._set_system_awake(False)
        self.root.destroy()

    def _copy(self, value):
        self.root.clipboard_clear(); self.root.clipboard_append(value); self.root.update()

    def _show_login(self):
        if self.running:
            self.stop_event.set()
            self.running = False
        dialog = tk.Toplevel(self.root)
        dialog.title("Link this computer")
        dialog.geometry("420x390")
        dialog.transient(self.root); dialog.grab_set()
        dialog.configure(bg="white")
        tk.Label(dialog, text="Link your account", bg="white", fg="#17243a", font=("Segoe UI", 17, "bold")).pack(pady=(22, 6))
        tk.Label(dialog, text="Sign in or create an account to register this computer.", bg="white", fg="#718096", wraplength=350).pack(pady=(0, 14))
        fields = {}
        for label, key, show in (("Email address","email",None),("Password (minimum 12 characters)","password","•"),("Computer name","name",None)):
            tk.Label(dialog, text=label, bg="white", fg="#52637a").pack(anchor="w", padx=30, pady=(8, 3))
            entry = tk.Entry(dialog, show=show, width=42); entry.pack(padx=30, fill="x")
            fields[key] = entry
        fields["name"].insert(0, self.config.get("name", os.environ.get("COMPUTERNAME","This computer")))
        create = tk.BooleanVar(value=False)
        tk.Checkbutton(dialog, text="Create a new account", variable=create, bg="white").pack(anchor="w", padx=30, pady=8)
        error = tk.StringVar()
        tk.Label(dialog, textvariable=error, fg="#b42318", bg="white", wraplength=350).pack()
        def submit():
            email, password, name = fields["email"].get().strip(), fields["password"].get(), fields["name"].get().strip()
            if not email or len(password) < 12 or not name:
                error.set("Enter an email, a password of at least 12 characters, and a computer name."); return
            button.configure(state="disabled")
            is_create = create.get()
            def work():
                try:
                    auth_path = "/api/auth/register" if is_create else "/api/auth/login"
                    auth = api(self.server, auth_path, {"email":email,"password":password})
                    token = auth["access_token"]
                    paired = None
                    if self.config.get("device_id") and self.config.get("device_secret"):
                        try:
                            paired = api(self.server, f"/api/devices/{self.config['device_id']}/rotate-password", {}, token)
                            config = {**self.config,"server":self.server,"name":name,"email":email,"access_token":token,"dynamic_password":paired["dynamic_password"]}
                        except Exception:
                            paired = None
                    if paired is None:
                        paired = api(self.server, "/api/devices/pair", {"name":name}, token)
                        config = {"server":self.server,"name":name,"email":email,"device_id":paired["device_id"],"device_secret":paired["agent_secret"],"access_token":token,"dynamic_password":paired["dynamic_password"]}
                    save_config(config)
                    self.root.after(0, lambda: finish(config, paired))
                except Exception as exc:
                    logger.exception("Enrollment failed")
                    error_message = str(exc)
                    self.root.after(0, lambda message=error_message: (error.set(message), button.configure(state="normal")))
            threading.Thread(target=work, daemon=True).start()
        def finish(config, paired):
            self.config = config
            self.id_var.set(config["device_id"]); self.password_var.set(paired["dynamic_password"])
            dialog.grab_release(); dialog.destroy()
            self._start_agent()
        button = tk.Button(dialog, text="Sign in and register this computer", command=submit, bg="#087d65", fg="white", relief="flat", pady=10)
        button.pack(fill="x", padx=30, pady=14)
        dialog.protocol("WM_DELETE_WINDOW", lambda: (dialog.grab_release(), dialog.destroy()))

    def _start_existing(self):
        try:
            # Rotate at every agent launch; this invalidates any previously shared password.
            token = self.config.get("access_token")
            if token:
                result = api(self.server, f"/api/devices/{self.config['device_id']}/rotate-password", {}, token)
                self.config["dynamic_password"] = result["dynamic_password"]
                save_config(self.config)
                self.password_var.set(result["dynamic_password"])
            self._start_agent()
        except Exception as exc:
            logger.exception("Stored pairing could not be resumed")
            self.status_var.set(str(exc))
            if "token" in str(exc).lower() or "authentication" in str(exc).lower() or "expired" in str(exc).lower():
                self.root.after(500, self._show_login)

    def rotate_password(self):
        token = self.config.get("access_token")
        if not token:
            self._show_login(); return
        self.rotate_btn.configure(state="disabled")
        def work():
            try:
                result = api(self.server, f"/api/devices/{self.config['device_id']}/rotate-password", {}, token)
                self.config["dynamic_password"] = result["dynamic_password"]
                if self.agent_args is not None:
                    self.agent_args.dynamic_password = result["dynamic_password"]
                save_config(self.config)
                self.root.after(0, lambda: self.password_var.set(result["dynamic_password"]))
                self.root.after(0, lambda: self.status_var.set("Password rotated. Previous password is invalid."))
            except Exception as exc:
                logger.exception("Password rotation failed")
                error_message = str(exc)
                self.root.after(0, lambda message=error_message: self.status_var.set(message))
            finally:
                self.root.after(0, lambda: self.rotate_btn.configure(state="normal"))
        threading.Thread(target=work, daemon=True).start()

    def disconnect(self):
        if self.running:
            self.stop_event.set()
            self.status_var.set("Disconnected by host")
            self.running = False

    async def _ask_file_consent(self, name: str, size: int):
        (Path.home() / "Downloads").mkdir(parents=True, exist_ok=True)
        return True

    async def _ask_consent(self, device_id: str, dynamic_password: str):
        future = concurrent.futures.Future()
        def show():
            dialog = tk.Toplevel(self.root)
            dialog.title("Remote access request")
            dialog.geometry("420x230")
            dialog.transient(self.root); dialog.grab_set()
            tk.Label(dialog, text="REMOTE ACCESS REQUEST", font=("Segoe UI", 14, "bold")).pack(pady=(22, 10))
            tk.Label(dialog, text=f"Device ID: {device_id}\nDynamic password: {dynamic_password}", font=("Segoe UI", 10)).pack(pady=6)
            tk.Label(dialog, text="A viewer is requesting access. Approve only if you trust them.", wraplength=350).pack(pady=10)
            def finish(value):
                if not future.done(): future.set_result(value)
                dialog.grab_release(); dialog.destroy()
            buttons = tk.Frame(dialog); buttons.pack(pady=12)
            tk.Button(buttons, text="Approve this session", command=lambda: finish(True), bg="#087d65", fg="white", width=20).pack(side="left", padx=6)
            tk.Button(buttons, text="Deny", command=lambda: finish(False), width=10).pack(side="left", padx=6)
            dialog.protocol("WM_DELETE_WINDOW", lambda: finish(False))
        self.root.after(0, show)
        return await asyncio.wrap_future(future)

    def _start_agent(self):
        if self.running:
            return
        self.stop_event.clear()
        self.running = True
        self.status_var.set("Connecting to relay...")
        self.attempt = 0
        def run():
            try:
                try:
                    import host_agent
                except ModuleNotFoundError:
                    from agent import host_agent
                host_agent.set_status_callback(self._agent_status)
                host_agent.set_consent_callback(self._ask_consent)
                host_agent.set_file_consent_callback(self._ask_file_consent)
                host_agent.set_diagnostics_callback(self._agent_diagnostics)
                host_agent.set_telemetry_callback(self._agent_telemetry)
                host_agent.set_workflow_recorder(self.workflow_recorder)
                host_agent.set_workflow_recording_requested(bool(self.workflow_record_var.get()))
                args = type("Args", (), {"server":self.server,"device_id":self.config["device_id"],"secret":self.config["device_secret"],"dynamic_password":self.config.get("dynamic_password","")})()
                self.agent_args = args
                asyncio.run(host_agent.run(args, self.stop_event))
            except Exception:
                logger.exception("Host agent stopped unexpectedly")
                self.root.after(0, lambda: self.status_var.set("Agent stopped — open Connection Diagnostics"))
            finally:
                self.running = False
        self.agent_thread = threading.Thread(target=run, daemon=True, name="RemoteDeskProRelay")
        self.agent_thread.start()

    def _diagnostics_text(self):
        latency = str(self.latency_ms) + " ms" if self.latency_ms is not None else "Measuring / unavailable"
        t = self.telemetry_snapshot
        ping = str(t["ping_ms"]) + " ms" if t["ping_ms"] is not None else latency
        return f"Server: {self.server}\nLast error: {self.last_error}\nFPS: {t['fps']} | Ping: {ping}\nUpload: {t['upload_kbps']} KB/s | Download: {t['download_kbps']} KB/s\nLog: {LOG_FILE}"

    def _agent_telemetry(self, snapshot):
        def update():
            self.telemetry_snapshot = dict(snapshot)
            self.diag_text.configure(text=self._diagnostics_text())
        self.root.after(0, update)

    def _agent_diagnostics(self, last_error, latency_ms):
        def update():
            self.last_error = last_error or "None"
            self.latency_ms = latency_ms
            self.diag_text.configure(text=self._diagnostics_text())
        self.root.after(0, update)

    def _agent_status(self, value: str):
        normalized = value.lower()
        if "connected (live)" in normalized:
            self.session_live = True
        disconnected = any(marker in normalized for marker in ("waiting for a viewer", "viewer disconnected", "host offline", "disconnected", "connection denied", "agent stopped"))
        if disconnected:
            self.session_live = False
        def update():
            self.status_var.set(value)
            if disconnected:
                self.session_recording_var.set(False)
        self.root.after(0, update)
        logger.info("Status: %s", value)

    def run(self):
        self.root.mainloop()

def launch(server=None):
    if not _acquire_single_instance():
        return
    try:
        DesktopApp(server).run()
    finally:
        _release_single_instance()
