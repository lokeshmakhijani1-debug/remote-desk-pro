"""Frozen Windows EXE reconnect regression against an injected local WebSocket relay."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import tempfile
import websockets

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.getenv("RDP_TEST_EXE", str(ROOT / "agent" / "dist" / "RemoteDeskPro-Agent.exe")))

async def main():
    handshakes = 0

    async def relay(ws):
        nonlocal handshakes
        auth = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert auth.get("type") == "auth"
        assert auth.get("secret") == "local-smoke-only"
        handshakes += 1
        await ws.send(json.dumps({"type": "connected", "device_id": "build-smoke"}))
        await asyncio.sleep(0.45)
        # Abort the transport rather than performing a graceful close handshake;
        # this simulates a relay TCP reset and exercises the real reconnect path.
        ws.transport.abort()

    smoke_root = Path(tempfile.mkdtemp(prefix="rdp-frozen-smoke-"))
    env = os.environ.copy()
    env["APPDATA"] = str(smoke_root)
    console_path = smoke_root / "exe_console.log"

    server = await websockets.serve(relay, "127.0.0.1", 0, ping_interval=None)
    port = server.sockets[0].getsockname()[1]
    with console_path.open("wb") as console_file:
        proc = subprocess.Popen(
            [str(EXE), "--server", f"http://127.0.0.1:{port}",
             "--device-id", "build-smoke", "--secret", "local-smoke-only"],
            cwd=str(ROOT / "agent"), env=env,
            stdout=console_file, stderr=subprocess.STDOUT,
        )
        try:
            await asyncio.sleep(20)
        finally:
            process_exit_before_cleanup = proc.poll()
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    server.close()
    await server.wait_closed()

    console_text = console_path.read_text(encoding="utf-8", errors="replace")
    log_path = smoke_root / "RemoteDeskPro" / "agent.log"
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    connected_logs = log_text.count("Connected to relay. Waiting for a viewer...")
    assert handshakes >= 3, (
        f"expected at least 3 handshakes, got {handshakes}; "
        f"process_exit_before_cleanup={process_exit_before_cleanup}; "
        f"EXE log: {log_text or '<no log file>'}; console: {console_text}"
    )
    assert connected_logs >= 3, f"expected >=3 frozen EXE connection logs, got {connected_logs}\n{log_text}"
    assert "Relay/network interruption" in log_text, "frozen EXE did not log the injected reset"
    print(json.dumps({
        "status": "PASS",
        "handshakes": handshakes,
        "connected_log_entries": connected_logs,
        "rotating_log_created": log_path.exists(),
        "log_path": str(log_path),
    }, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
