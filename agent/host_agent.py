"""Visible-consent host bridge. Streaming starts only after explicit local approval."""
import argparse
import asyncio
import base64
import json
import logging
import os
import sys
from io import BytesIO
import mss
import pyautogui
import pyperclip
import websockets
from PIL import Image
from maintenance_curtain import MaintenanceCurtain, monitor_inventory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("remote-desk-agent")

def _consent_dialog(device_id: str, dynamic_password: str) -> bool:
    import tkinter as tk
    root = tk.Tk()
    root.title("Remote Desk Pro — Session approval")
    root.geometry("420x300")
    root.resizable(False, False)
    tk.Label(root, text="REMOTE ACCESS REQUEST", font=("Segoe UI", 14, "bold")).pack(pady=(20, 8))
    tk.Label(root, text="Device ID: " + device_id, font=("Segoe UI", 11)).pack(pady=3)
    tk.Label(root, text="Dynamic password: " + (dynamic_password or "Check the dashboard"), font=("Segoe UI", 11)).pack(pady=3)
    tk.Label(root, text="A remote viewer is requesting access to this computer.", wraplength=360).pack(pady=12)
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
    return await asyncio.to_thread(_consent_dialog, device_id, dynamic_password)

def _curtain_consent_dialog(monitor_indexes: list[int] | None) -> bool:
    import tkinter as tk
    root = tk.Tk()
    root.title("Remote Desk Pro — Maintenance Curtain approval")
    root.geometry("520x300")
    root.resizable(False, False)
    tk.Label(root, text="MAINTENANCE CURTAIN REQUEST", font=("Segoe UI", 14, "bold")).pack(pady=(22, 12))
    tk.Label(root, text="The physical displays will show a maintenance notice.",
             wraplength=440, font=("Segoe UI", 11)).pack(pady=5)
    tk.Label(root, text="IMPORTANT: The technician can still view the underlying desktop.",
             wraplength=440, foreground="#a3212d", font=("Segoe UI", 10, "bold")).pack(pady=10)
    target = "All active displays" if not monitor_indexes else ", ".join(f"Screen {i}" for i in monitor_indexes)
    tk.Label(root, text="Requested: " + target, font=("Segoe UI", 10)).pack(pady=4)
    decision = {"approved": False}
    buttons = tk.Frame(root)
    buttons.pack(pady=22)
    def finish(value: bool):
        decision["approved"] = value
        root.destroy()
    tk.Button(buttons, text="Approve Maintenance Curtain",
              command=lambda: finish(True), width=27).pack(side="left", padx=7)
    tk.Button(buttons, text="Deny", command=lambda: finish(False), width=12).pack(side="left", padx=7)
    root.protocol("WM_DELETE_WINDOW", lambda: finish(False))
    root.after(120000, lambda: finish(False))
    root.mainloop()
    return decision["approved"]

async def clipboard_watch(ws, running: asyncio.Event):
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

def apply_control(message: dict):
    event = message.get("event")
    if event == "mouse_move":
        size = pyautogui.size()
        pyautogui.moveTo(message.get("x", 0) * size.width, message.get("y", 0) * size.height, _pause=False)
    elif event in ("mouse_down", "mouse_up"):
        action = pyautogui.mouseDown if event == "mouse_down" else pyautogui.mouseUp
        action(button={0:"left",1:"middle",2:"right"}.get(message.get("button"),"left"))
    elif event == "key_down":
        key = str(message.get("key", "")).lower()
        allowed = {"enter","escape","tab","backspace","delete","space","up","down","left","right","shift","ctrl","alt","home","end"}
        if len(key) == 1 or key in allowed:
            pyautogui.press(key)

async def run(args):
    endpoint = args.server.rstrip("/") + f"/ws/host/{args.device_id}"
    endpoint = endpoint.replace("https://", "wss://").replace("http://", "ws://")
    async with websockets.connect(endpoint, max_size=8 * 1024 * 1024, ping_interval=20) as ws:
        await ws.send(json.dumps({"type":"auth","secret":args.secret}))
        response = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        if response.get("type") != "connected":
            raise RuntimeError("Server rejected the device credential.")
        log.info("Device %s connected. Waiting for a viewer.", args.device_id)
        stream_task = None
        clipboard_task = None
        incoming_file = None
        streaming = asyncio.Event()
        curtain_controller = None
        session_id = None
        loop = asyncio.get_running_loop()

        async def send_agent_event(kind: str, data: dict | None = None):
            payload = {"type": kind, "session_id": session_id, **(data or {})}
            await ws.send(json.dumps(payload))

        def emit_curtain_event(kind: str, data: dict):
            if session_id:
                asyncio.run_coroutine_threadsafe(send_agent_event(kind, data), loop)

        async def close_curtain(reason: str):
            nonlocal curtain_controller
            if curtain_controller:
                curtain_controller.stop(reason)
                await asyncio.to_thread(curtain_controller.join, 3.0)
                curtain_controller = None

        try:
            async for packet in ws:
                if isinstance(packet, bytes):
                    continue
                message = json.loads(packet)
                if message.get("type") == "viewer_joined":
                    if stream_task and not stream_task.done():
                        continue
                    session_id = str(message.get("session_id", ""))
                    if not session_id:
                        continue
                    if await ask_host_consent(args.device_id, args.dynamic_password):
                        streaming.set()
                        await send_agent_event("host_approved")
                        stream_task = asyncio.create_task(stream_screen(ws, streaming))
                        clipboard_task = asyncio.create_task(clipboard_watch(ws, streaming))
                        log.info("Session approved; screen sharing is active.")
                    else:
                        await send_agent_event("host_denied")
                elif message.get("type") == "curtain.request" and streaming.is_set():
                    if message.get("session_id") != session_id:
                        continue
                    if curtain_controller and curtain_controller.thread and curtain_controller.thread.is_alive():
                        await send_agent_event("curtain.status", {"status": "active_verified"})
                        continue
                    requested = message.get("monitor_indexes")
                    if requested is not None and (not isinstance(requested, list) or
                                                   any(not isinstance(i, int) for i in requested)):
                        await send_agent_event("curtain.status", {"status": "failed", "reason": "Invalid monitor selection"})
                        continue
                    if await asyncio.to_thread(_curtain_consent_dialog, requested):
                        await send_agent_event("curtain.approved", {"monitor_indexes": requested or []})
                        curtain_controller = MaintenanceCurtain(requested, emit_curtain_event)
                        curtain_controller.start()
                    else:
                        await send_agent_event("curtain.denied")
                elif message.get("type") == "curtain.disable":
                    if message.get("session_id") == session_id:
                        await close_curtain("viewer_disabled")
                elif message.get("type") == "viewer_left":
                    await close_curtain("viewer_disconnected")
                    streaming.clear()
                    if stream_task:
                        stream_task.cancel()
                        stream_task = None
                    if clipboard_task:
                        clipboard_task.cancel()
                        clipboard_task = None
                    if incoming_file:
                        incoming_file["handle"].close()
                        incoming_file = None
                    log.info("Viewer disconnected; screen sharing stopped.")
                elif message.get("type") == "clipboard_update" and streaming.is_set():
                    value = message.get("text", "")
                    if isinstance(value, str) and len(value) <= 65536:
                        try:
                            current = await asyncio.to_thread(pyperclip.paste)
                            if current != value:
                                await asyncio.to_thread(pyperclip.copy, value)
                        except Exception as exc:
                            log.warning("Clipboard update failed: %s", exc)
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
                        apply_control(message)
                    except Exception as exc:
                        log.warning("Input event rejected: %s", exc)
        finally:
            await close_curtain("session_ended")
            streaming.clear()
            if stream_task:
                stream_task.cancel()
            if clipboard_task:
                clipboard_task.cancel()
            if incoming_file:
                incoming_file["handle"].close()

def main():
    parser = argparse.ArgumentParser(description="Remote Desk Pro visible-consent host agent")
    parser.add_argument("--server", default=os.getenv("RDP_SERVER", "https://remote-desk-pro-pj29.onrender.com"))
    parser.add_argument("--device-id", default=os.getenv("RDP_DEVICE_ID"))
    parser.add_argument("--secret", default=os.getenv("RDP_AGENT_SECRET"))
    parser.add_argument("--dynamic-password", default=os.getenv("RDP_DYNAMIC_PASSWORD", ""))
    args = parser.parse_args()
    if not args.device_id or not args.secret:
        parser.error("Provide --device-id and --secret from the pairing screen.")
    print("Remote Desk Pro Host Agent — visible-consent mode")
    print("Unattended access is disabled. No service or auto-start is installed.")
    pyautogui.FAILSAFE = True
    asyncio.run(run(args))

if __name__ == "__main__":
    main()
