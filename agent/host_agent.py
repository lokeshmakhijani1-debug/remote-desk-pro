"""Visible-consent host bridge. Streaming starts only after explicit local approval."""
import argparse
import asyncio
import json
import logging
import os
import sys
from io import BytesIO
import mss
import pyautogui
import websockets
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("remote-desk-agent")

async def ask_host_consent(device_id: str) -> bool:
    print("\n" + "=" * 68)
    print(f"REMOTE ACCESS REQUEST FOR DEVICE {device_id}")
    print("Screen capture and remote input are disabled until you approve.")
    print("Type ALLOW to approve this session, or press Enter to deny.")
    print("=" * 68)
    return (await asyncio.to_thread(input, "Approve this session? ")).strip().upper() == "ALLOW"

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
        streaming = asyncio.Event()
        try:
            async for packet in ws:
                if isinstance(packet, bytes):
                    continue
                message = json.loads(packet)
                if message.get("type") == "viewer_joined":
                    if stream_task and not stream_task.done():
                        continue
                    if await ask_host_consent(args.device_id):
                        streaming.set()
                        await ws.send(json.dumps({"type":"host_approved"}))
                        stream_task = asyncio.create_task(stream_screen(ws, streaming))
                        log.info("Session approved; screen sharing is active.")
                    else:
                        await ws.send(json.dumps({"type":"host_denied"}))
                elif message.get("type") == "viewer_left":
                    streaming.clear()
                    if stream_task:
                        stream_task.cancel()
                        stream_task = None
                    log.info("Viewer disconnected; screen sharing stopped.")
                elif message.get("type") == "control" and streaming.is_set():
                    try:
                        apply_control(message)
                    except Exception as exc:
                        log.warning("Input event rejected: %s", exc)
        finally:
            streaming.clear()
            if stream_task:
                stream_task.cancel()

def main():
    parser = argparse.ArgumentParser(description="Remote Desk Pro visible-consent host agent")
    parser.add_argument("--server", default=os.getenv("RDP_SERVER", "https://remote-desk-pro-pj29.onrender.com"))
    parser.add_argument("--device-id", default=os.getenv("RDP_DEVICE_ID"))
    parser.add_argument("--secret", default=os.getenv("RDP_AGENT_SECRET"))
    args = parser.parse_args()
    if not args.device_id or not args.secret:
        parser.error("Provide --device-id and --secret from the pairing screen.")
    if not sys.stdin.isatty():
        parser.error("An interactive terminal is required for local session approval.")
    print("Remote Desk Pro Host Agent — visible-consent mode")
    print("This process is not installed as a service and does not auto-start.")
    pyautogui.FAILSAFE = True
    asyncio.run(run(args))

if __name__ == "__main__":
    main()
