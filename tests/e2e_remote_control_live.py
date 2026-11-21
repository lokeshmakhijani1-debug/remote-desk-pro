"""Live Render -> headless Chromium -> Windows OS input E2E.

Uses the existing DPAPI-protected Desktop Agent config; never prints credentials.
Run: py tests/e2e_remote_control_live.py
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pyautogui
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agent"
SERVER = "https://remote-desk-pro-pj29.onrender.com"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
STATE = Path(tempfile.gettempdir()) / "rdp-live-input-e2e-state.json"


def load_agent_config() -> dict:
    sys.path.insert(0, str(AGENT_DIR))
    import desktop_app  # DPAPI unseals only inside this process
    config = desktop_app.load_config()
    required = ("server", "device_id", "dynamic_password", "access_token")
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise RuntimeError("Agent enrollment config is incomplete: " + ", ".join(missing))
    if config["server"].rstrip("/") != SERVER:
        raise RuntimeError("Stored agent server does not match the production relay")
    return config


def target_window() -> None:
    import tkinter as tk
    from tkinter import ttk

    state = {"clicks": 0, "scrolls": 0, "hscrolls": 0, "typed": "", "ready": False}
    root = tk.Tk()
    root.title("RDP E2E Input Target")
    root.geometry("760x520+80+80")
    root.attributes("-topmost", False)
    root.configure(bg="#f4f7fb")
    ttk.Label(root, text="Remote Desk Pro â€” OS Input Test", font=("Segoe UI", 16, "bold")).pack(pady=18)
    ttk.Label(root, text="Tap the target, scroll the text area, then type RDP_OK.").pack(pady=6)
    clicked = ttk.Label(root, text="CLICK TARGET â€” WAITING", width=42, anchor="center")
    clicked.pack(pady=12, ipady=18)
    def on_click(_event=None):
        state["clicks"] += 1
        clicked.configure(text=f"CLICK REGISTERED: {state['clicks']}")
        save()
    clicked.bind("<Button-1>", on_click)
    entry = ttk.Entry(root, width=48, font=("Consolas", 16))
    entry.pack(pady=12, ipady=8)
    scroll = tk.Text(root, width=72, height=10, font=("Consolas", 10), wrap="word")
    scroll.pack(padx=24, pady=10, fill="both", expand=True)
    scroll.insert("1.0", ("Scroll target line â€” verify Windows wheel delivery.\n" * 35))
    def on_scroll(_event=None):
        state["scrolls"] += 1
        save()
    scroll.bind("<MouseWheel>", on_scroll)
    root.bind_all("<MouseWheel>", on_scroll, add="+")
    def on_hscroll(_event=None):
        state["hscrolls"] += 1
        save()
    scroll.bind("<Shift-MouseWheel>", on_hscroll)
    root.bind_all("<Shift-MouseWheel>", on_hscroll, add="+")
    def on_key(_event=None):
        state["typed"] = entry.get()
        save()
    entry.bind("<KeyRelease>", on_key)
    def save():
        payload = {**state, "entry": entry.get(), "window": root.winfo_geometry(),
                   "window_xy": [root.winfo_rootx(), root.winfo_rooty()],
                   "click_xy": [clicked.winfo_rootx()+clicked.winfo_width()//2,
                                clicked.winfo_rooty()+clicked.winfo_height()//2],
                   "entry_xy": [entry.winfo_rootx()+entry.winfo_width()//2,
                                entry.winfo_rooty()+entry.winfo_height()//2],
                   "scroll_xy": [scroll.winfo_rootx()+scroll.winfo_width()//2,
                                 scroll.winfo_rooty()+scroll.winfo_height()//2]}
        STATE.write_text(json.dumps(payload), encoding="utf-8")
    # Low-level Windows hook verifies WM_MOUSEHWHEEL delivery independently of Tk's wheel bindings.
    hook_callback = None
    hook_handle = None
    class Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    class MouseHookData(ctypes.Structure):
        _fields_ = [("pt", Point), ("mouseData", ctypes.c_ulong), ("flags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t)]
    def install_horizontal_hook():
        nonlocal hook_callback, hook_handle
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hook_proc_type = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_size_t, ctypes.c_void_p)
        def on_mouse_hook(code, message, data_ptr):
            if code >= 0 and message == 0x020E:
                event = ctypes.cast(data_ptr, ctypes.POINTER(MouseHookData)).contents
                left, top = root.winfo_rootx(), root.winfo_rooty()
                if left <= event.pt.x < left + root.winfo_width() and top <= event.pt.y < top + root.winfo_height():
                    state["hscrolls"] += 1
                    save()
            return user32.CallNextHookEx(hook_handle, code, message, data_ptr)
        hook_callback = hook_proc_type(on_mouse_hook)
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, hook_proc_type, ctypes.c_void_p, ctypes.c_ulong]
        hook_handle = user32.SetWindowsHookExW(14, hook_callback, kernel32.GetModuleHandleW(None), 0)
        if not hook_handle:
            raise ctypes.WinError()
    def ready():
        root.after(150, install_horizontal_hook)
        state["ready"] = True
        save()
    root.after(500, ready)
    def cleanup_hook(_event=None):
        nonlocal hook_handle
        if hook_handle:
            ctypes.windll.user32.UnhookWindowsHookEx(hook_handle)
            hook_handle = None
    root.bind("<Destroy>", lambda event: cleanup_hook() if event.widget is root else None)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


def read_state() -> dict:
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def wait_until(predicate, timeout: float, label: str):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.15)
    raise TimeoutError(label)


def navigate_with_retry(page, url: str):
    failures = []
    for attempt in range(3):
        try:
            return page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as exc:
            failures.append(f"attempt {attempt + 1}: {type(exc).__name__}: {exc}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError("Render navigation failed after retries: " + " | ".join(failures))


def agent_log_contains_after(offset: int, marker: str) -> bool:
    log_path = Path(os.getenv("APPDATA", str(Path.home()))) / "RemoteDeskPro" / "agent.log"
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(offset)
            return marker in handle.read()
    except OSError:
        return False


def approve_host_consent() -> None:
    # The real desktop app's explicit consent dialog is approved, not bypassed.
    windows = wait_until(lambda: pyautogui.getWindowsWithTitle("Remote access request"),
                         35, "Host consent dialog did not appear")
    dialog = windows[0]
    dialog.activate()
    time.sleep(0.4)
    pyautogui.click(dialog.left + 170, dialog.top + 212)
    time.sleep(0.5)
    hwnd = ctypes.windll.user32.FindWindowW(None, "RDP E2E Input Target")
    if hwnd:
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)


def run_viewer(config: dict, target: subprocess.Popen) -> dict:
    result: dict = {"checks": {}, "coordinates": {}, "latency_ms": {}, "errors": [], "websocket_frames": [], "page_console_errors": []}
    if not CHROME.exists():
        raise RuntimeError(f"Chrome executable not found: {CHROME}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=str(CHROME), args=["--disable-gpu"])
        try:
            context = browser.new_context(viewport={"width": 390, "height": 844},
                                          device_scale_factor=1, is_mobile=True, has_touch=True)
            context.add_init_script("localStorage.setItem('rdp-token', " + json.dumps(config["access_token"]) + ");")
            context.add_init_script("""(() => {
              const Native = window.WebSocket; window.__rdpSockets = []; window.__rdpE2eDropped = false;
              function Wrapped(...args) { const ws = new Native(...args); window.__rdpSockets.push(ws); const add = ws.addEventListener.bind(ws);
                ws.addEventListener = (type, listener, options) => { if (type !== "message") return add(type, listener, options);
                  const wrapped = event => { if (!window.__rdpE2eDropped && typeof event.data === "string") { try {
                    if (JSON.parse(event.data).type === "transfer_ack") { window.__rdpE2eDropped = true; window.setTimeout(() => ws.close(4001, "E2E simulated interruption"), 0); }
                  } catch {} } return listener.call(ws, event); }; return add(type, wrapped, options); }; return ws; }
              Wrapped.prototype = Native.prototype; Object.setPrototypeOf(Wrapped, Native); window.WebSocket = Wrapped;
            })();""")
            page = context.new_page()
            page.on("console", lambda msg: result["page_console_errors"].append(msg.text) if msg.type == "error" else None)
            def observe_socket(ws):
                ws.on("framereceived", lambda payload: result["websocket_frames"].append({"direction":"in","kind":"binary" if isinstance(payload, bytes) else "text","bytes":len(payload) if isinstance(payload, bytes) else len(str(payload))}))
            page.on("websocket", observe_socket)
            page.set_default_timeout(20000)
            navigate_with_retry(page, SERVER + "/")
            page.get_by_role("heading", name="Remote Control", exact=True).wait_for()
            result["checks"]["viewer_authenticated"] = True
            page.get_by_placeholder("Enter 9-digit ID").fill(config["device_id"])
            page.get_by_placeholder("Enter 6-digit password").fill(config["dynamic_password"])
            t0 = time.perf_counter()
            page.get_by_role("button", name="Connect", exact=True).first.click()
            wait_until(lambda: pyautogui.getWindowsWithTitle("Remote access request"),
                       35, "Host consent dialog did not appear")
            result["latency_ms"]["connect_to_consent"] = round((time.perf_counter()-t0)*1000, 1)
            log_path = Path(os.getenv("APPDATA", str(Path.home()))) / "RemoteDeskPro" / "agent.log"
            log_offset = log_path.stat().st_size if log_path.exists() else 0
            approve_host_consent()
            approval_started = time.perf_counter()
            wait_until(lambda: agent_log_contains_after(log_offset, "Connected (Live)"),
                       30, "Host approval was not acknowledged by the agent")
            result["latency_ms"]["consent_to_approved"] = round((time.perf_counter()-approval_started)*1000, 1)
            target_window_handle = wait_until(lambda: pyautogui.getWindowsWithTitle("RDP E2E Input Target"), 8, "Test target window not found after consent")
            target_window_handle[0].activate()
            result["checks"]["relay_session_approved"] = True
            page.get_by_role("button", name="Control", exact=True).click()
            canvas = page.locator("canvas").first
            canvas.wait_for(state="visible")
            canvas.scroll_into_view_if_needed()
            try:
                wait_until(lambda: canvas.evaluate("c => c.width > 300 && c.height > 200"), 20,
                           "Remote screen frames did not arrive")
            except TimeoutError:
                result["diagnostics"] = {"page_status":page.locator(".connection-status").inner_text(),
                    "canvas":canvas.evaluate("c => ({width:c.width,height:c.height,rect:c.getBoundingClientRect().toJSON()})"),
                    "all_canvases":page.locator("canvas").evaluate_all("xs => xs.map(c=>({width:c.width,height:c.height}))"),
                    "body_tail":page.locator("body").inner_text()[-1200:]}
                page.screenshot(path=str(Path(tempfile.gettempdir()) / "rdp-live-e2e-diagnostics.png"), full_page=True)
                raise RuntimeError("Remote screen frames did not arrive; diagnostics=" + json.dumps(result["diagnostics"]) + "; frames=" + json.dumps(result["websocket_frames"]))
            rect = canvas.bounding_box()
            dims = canvas.evaluate("c => ({width:c.width,height:c.height})")
            state = wait_until(lambda: (s if (s := read_state()).get("ready") else None),
                               10, "Windows input target did not initialize")

            def point(key: str):
                x, y = state[key]
                image_aspect = dims["width"] / max(1, dims["height"])
                box_aspect = rect["width"] / max(1, rect["height"])
                content_width, content_height, left, top = rect["width"], rect["height"], 0, 0
                if box_aspect > image_aspect:
                    content_width = rect["height"] * image_aspect
                    left = (rect["width"] - content_width) / 2
                else:
                    content_height = rect["width"] / image_aspect
                    top = (rect["height"] - content_height) / 2
                return {"x": rect["x"] + left + (x / dims["width"]) * content_width,
                        "y": rect["y"] + top + (y / dims["height"]) * content_height}

            # Touch tap: real Chromium touchscreen input -> React Pointer Events -> relay.
            click = point("click_xy")
            before = pyautogui.position()
            started = time.perf_counter()
            try:
                page.touchscreen.tap(click["x"], click["y"])
                wait_until(lambda: (s if (s := read_state()).get("clicks", 0) >= 1 else None),
                           10, "Windows target did not register the touch tap")
                after = pyautogui.position()
                result["checks"]["touch_click"] = True
                result["coordinates"]["cursor_before"] = list(before)
                result["coordinates"]["cursor_after_touch"] = list(after)
                result["coordinates"]["touch_target"] = [state["click_xy"][0], state["click_xy"][1]]
                result["latency_ms"]["touch_to_click"] = round((time.perf_counter()-started)*1000, 1)
                if abs(after.x-state["click_xy"][0]) > 35 or abs(after.y-state["click_xy"][1]) > 35:
                    result["checks"]["touch_cursor_alignment"] = False
                    result["errors"].append(f"touch cursor mismatch: actual={(after.x,after.y)} target={state['click_xy']}")
                else:
                    result["checks"]["touch_cursor_alignment"] = True
            except Exception as exc:
                result["checks"]["touch_click"] = False
                result["errors"].append(f"touch: {type(exc).__name__}: {exc}")
                result["latency_ms"]["touch_timeout"] = round((time.perf_counter()-started)*1000, 1)

            # A separate mouse click checks the same target even if touch delivery fails.
            if read_state().get("clicks", 0) < 1:
                mouse_started = time.perf_counter()
                page.mouse.click(click["x"], click["y"])
                try:
                    wait_until(lambda: (s if (s := read_state()).get("clicks", 0) >= 1 else None),
                               8, "Windows target did not register mouse click")
                    result["checks"]["mouse_click"] = True
                    result["latency_ms"]["mouse_click_to_event"] = round((time.perf_counter()-mouse_started)*1000, 1)
                except Exception as exc:
                    result["checks"]["mouse_click"] = False
                    result["errors"].append(f"mouse click: {type(exc).__name__}: {exc}")

            # Explicit pointer move: verify the Windows cursor before wheel dispatch.
            scroll = point("scroll_xy")
            started = time.perf_counter()
            page.mouse.move(scroll["x"], scroll["y"])
            expected_cursor = state["scroll_xy"]
            try:
                wait_until(lambda: (pos if abs((pos := pyautogui.position()).x-expected_cursor[0]) <= 35 and abs(pos.y-expected_cursor[1]) <= 35 else None),
                           8, "Windows cursor did not reach the scroll target")
                actual_cursor = pyautogui.position()
                result["checks"]["cursor_move"] = True
                result["coordinates"]["cursor_move_actual"] = [actual_cursor.x, actual_cursor.y]
                result["coordinates"]["cursor_move_expected"] = expected_cursor
                result["latency_ms"]["pointer_move_round_trip"] = round((time.perf_counter()-started)*1000, 1)
            except Exception as exc:
                result["checks"]["cursor_move"] = False
                result["errors"].append(f"cursor: {type(exc).__name__}: {exc}")

            # Vertical scroll: native Windows wheel input over the Tk text widget.
            scroll = point("scroll_xy")
            started = time.perf_counter()
            page.mouse.move(scroll["x"], scroll["y"])
            page.mouse.click(scroll["x"], scroll["y"])
            time.sleep(0.35)
            cursor_before_wheel = pyautogui.position()
            page.mouse.wheel(0, 720)
            result["coordinates"]["cursor_at_scroll"] = [cursor_before_wheel.x, cursor_before_wheel.y]
            try:
                wait_until(lambda: (s if (s := read_state()).get("scrolls", 0) >= 1 else None),
                           3, "Windows target did not receive mouse wheel input")
                result["checks"]["vertical_scroll"] = True
                result["latency_ms"]["scroll_to_event"] = round((time.perf_counter()-started)*1000, 1)
            except TimeoutError as exc:
                result["checks"]["vertical_scroll"] = False
                result["errors"].append(str(exc))
                result["latency_ms"]["scroll_timeout"] = round((time.perf_counter()-started)*1000, 1)

            # Horizontal scroll: native Windows horizontal wheel input.
            started = time.perf_counter()
            page.mouse.wheel(720, 0)
            try:
                wait_until(lambda: (s if (s := read_state()).get("hscrolls", 0) >= 1 else None),
                           8, "Windows target did not receive horizontal wheel input")
                result["checks"]["horizontal_scroll"] = True
                result["latency_ms"]["horizontal_scroll_to_event"] = round((time.perf_counter()-started)*1000, 1)
            except TimeoutError as exc:
                result["checks"]["horizontal_scroll"] = False
                result["errors"].append(str(exc))
                result["latency_ms"]["horizontal_scroll_timeout"] = round((time.perf_counter()-started)*1000, 1)

            # Focus the target Entry through the live remote canvas and send real key events.
            entry = point("entry_xy")
            page.mouse.move(entry["x"], entry["y"])
            page.mouse.click(entry["x"], entry["y"])
            started = time.perf_counter()
            try:
                page.keyboard.type("RDP_OK", delay=70)
                wait_until(lambda: (s if (s := read_state()).get("entry") == "RDP_OK" else None),
                           12, "Windows target did not receive the complete keystroke sequence")
                result["checks"]["keystrokes"] = True
                result["latency_ms"]["keystrokes_to_entry"] = round((time.perf_counter()-started)*1000, 1)
            except Exception as exc:
                result["checks"]["keystrokes"] = False
                result["errors"].append(f"keyboard: {type(exc).__name__}: {exc}")
            # Zstandard transfer with one deliberate viewer socket interruption after the first ACK.
            transfer_source = Path(tempfile.gettempdir()) / "rdp-transfer-e2e-source.bin"
            transfer_destination = Path(tempfile.gettempdir()) / "rdp-transfer-e2e-received.bin"
            transfer_payload = os.urandom(2 * 1024 * 1024)
            transfer_source.write_bytes(transfer_payload)
            expected_transfer_hash = hashlib.sha256(transfer_payload).hexdigest()
            page.locator('input[type="file"]').set_input_files(str(transfer_source))
            page.get_by_label("Zstandard compression (WASM)").check()
            page.get_by_role("button", name="Send selected file").click()
            save_dialog = wait_until(lambda: (items if (items := pyautogui.getWindowsWithTitle("Save As")) else None), 35, "Host save dialog did not appear")
            save_dialog[0].activate(); time.sleep(0.3); pyautogui.hotkey("ctrl", "a")
            pyautogui.write(str(transfer_destination), interval=0.005); pyautogui.press("enter")
            wait_until(lambda: page.evaluate("() => window.__rdpE2eDropped === true"), 45, "Transfer did not receive first ACK / disconnect trigger")
            result["checks"]["transfer_disconnect_injected"] = True
            wait_until(lambda: (items if (items := (pyautogui.getWindowsWithTitle("Remote Desk Pro") or pyautogui.getWindowsWithTitle("Remote access request"))) else None), 45, "Host did not request consent after reconnect")
            approve_host_consent()
            resumed_dialog = wait_until(lambda: (items if (items := pyautogui.getWindowsWithTitle("Save As")) else None), 35, "Host resume destination dialog did not appear")
            resumed_dialog[0].activate(); time.sleep(0.3); pyautogui.hotkey("ctrl", "a")
            pyautogui.write(str(transfer_destination), interval=0.005); pyautogui.press("enter")
            wait_until(lambda: "File received and SHA-256 verified" in page.locator(".transfer-tools").inner_text(), 90, "Resumed Zstandard transfer failed SHA-256 verification")
            received_hash = hashlib.sha256(transfer_destination.read_bytes()).hexdigest()
            result["checks"]["zstd_transfer_resume"] = received_hash == expected_transfer_hash
            result["checks"]["transfer_sha256_match"] = received_hash == expected_transfer_hash
            result["transfer"] = {"bytes": len(transfer_payload), "compression": "zstd", "disconnects_injected": 1, "sha256": received_hash}
            if received_hash != expected_transfer_hash: result["errors"].append("Resumed transfer SHA-256 mismatch")
            transfer_source.unlink(missing_ok=True); transfer_destination.unlink(missing_ok=True)
            result["target"] = read_state()
            result["canvas"] = {"css_rect": rect, "remote_frame": dims}
            context.close()
        finally:
            browser.close()
    return result


def main() -> int:
    config = load_agent_config()
    STATE.unlink(missing_ok=True)
    target = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--target"],
                              cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_until(lambda: (s if (s := read_state()).get("ready") else None), 12,
                   "Test target window failed to initialize")
        report = run_viewer(config, target)
        report["result"] = "PASS" if all(report.get("checks", {}).get(k) for k in
            ("viewer_authenticated", "relay_session_approved", "touch_click",
             "cursor_move", "vertical_scroll", "horizontal_scroll", "keystrokes",
             "zstd_transfer_resume", "transfer_sha256_match")) else "PARTIAL"
        report["device_id_suffix"] = config["device_id"][-3:]
        measured = [v for k, v in report.get("latency_ms", {}).items()
                    if k in ("touch_to_click", "pointer_move_round_trip",
                             "scroll_to_event", "horizontal_scroll_to_event",
                             "keystrokes_to_entry")]
        report["round_trip_latency_ms"] = ({
            "samples": len(measured), "min": round(min(measured), 1),
            "avg": round(sum(measured)/len(measured), 1), "max": round(max(measured), 1)
        } if measured else {"samples": 0, "min": None, "avg": None, "max": None})
        report_path = ROOT / "tests" / "e2e_remote_control_live_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if report["result"] == "PASS" else 2
    except Exception as exc:
        failure = {"result":"FAIL", "error":f"{type(exc).__name__}: {exc}",
                   "target_state":read_state()}
        (ROOT / "tests" / "e2e_remote_control_live_report.json").write_text(
            json.dumps(failure, indent=2), encoding="utf-8")
        print(json.dumps(failure, indent=2))
        return 1
    finally:
        target.terminate()
        try:
            target.wait(timeout=5)
        except subprocess.TimeoutExpired:
            target.kill()
        STATE.unlink(missing_ok=True)


if __name__ == "__main__":
    if "--target" in sys.argv:
        target_window()
        raise SystemExit(0)
    raise SystemExit(main())

