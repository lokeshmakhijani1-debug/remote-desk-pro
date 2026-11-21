"""Linux cloud E2E: real Render relay + real host_agent.run_once + virtual desktop hooks."""
from __future__ import annotations
import asyncio, base64, hashlib, json, os, sys, tempfile, threading, time, uuid
from pathlib import Path
from types import SimpleNamespace
import httpx, websockets, zstandard
from playwright.async_api import async_playwright

BASE = os.getenv("RDP_BASE_URL", "https://remote-desk-pro-pj29.onrender.com").rstrip("/")
REPORT = Path("tests/artifacts/cloud_e2e_report.json")
CHUNK, TOTAL = 256 * 1024, 2 * 1024 * 1024

def check(ok, message):
    if not ok: raise AssertionError(message)

async def event(ws, kind, timeout=25):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            raw = await asyncio.wait_for(ws.recv(), max(.1, end-time.monotonic()))
        except websockets.exceptions.ConnectionClosed as exc:
            raise RuntimeError(f"Socket closed while waiting for {kind}; close_code={ws.close_code}; close_reason={ws.close_reason}") from exc
        if isinstance(raw, bytes): continue
        value = json.loads(raw)
        if value.get("type") == kind: return value
        if value.get("type") in {"transfer_error", "viewer_rejected", "host_denied"}:
            raise AssertionError(f"Relay {value}")
    raise TimeoutError(f"Waiting for {kind}")

async def main():
    result = {"status":"FAIL","target":BASE,"runner":"ubuntu-latest","checks":{},"transfer":{},"errors":[]}
    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=60) as api:
            health = (await api.get("/health")).raise_for_status().json()
            check(health.get("status") == "ok" and health.get("database") == "postgresql", f"Health/DB mismatch: {health}")
            result["checks"]["render_health_postgresql"] = "PASS"
            suffix = uuid.uuid4().hex[:12]
            registration = (await api.post("/api/auth/register", json={
                "email":f"rdp-cloud-e2e-{suffix}@example.com",
                "password":"Rdp-Cloud-"+uuid.uuid4().hex+"!"
            })).raise_for_status().json()
            token = registration["access_token"]
            headers = {"Authorization":"Bearer "+token}
            paired = (await api.post("/api/devices/pair", headers=headers,
                json={"name":"GitHub Actions headless "+suffix})).raise_for_status().json()
            session = (await api.post("/api/devices/connect", headers=headers,
                json={"device_id":paired["device_id"],"password":paired["dynamic_password"]})).raise_for_status().json()["session_token"]
            result["synthetic_device_id"] = paired["device_id"]
            result["synthetic_user_role"] = registration["user"]["role"]

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                ctx = await browser.new_context(viewport={"width":1365,"height":900})
                await ctx.add_init_script("localStorage.setItem('rdp-token', "+json.dumps(token)+");")
                page = await ctx.new_page()
                response = await page.goto(BASE+"/", wait_until="domcontentloaded", timeout=60000)
                check(response is not None and response.status == 200, "Viewer page HTTP status not 200")
                await page.get_by_role("heading", name="Remote Control", exact=True).wait_for(timeout=30000)
                result["checks"]["playwright_chromium_viewer"] = "PASS"
                await ctx.close()
            finally: await browser.close()

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"agent"))
        import host_agent
        root = Path(tempfile.mkdtemp(prefix="rdp-cloud-host-"))
        destination = root/"resumable-proof.bin"
        applied, consents, host_failures, host_status = [], 0, [], []
        connected = asyncio.Event()
        stop = threading.Event()
        async def approve(_device, _password):
            nonlocal consents
            consents += 1
            return True
        async def no_clipboard(_ws, _running): await asyncio.Event().wait()
        host_agent.set_consent_callback(approve)
        def status_hook(status):
            host_status.append(status)
            if status == "Connected to relay. Waiting for a viewer...": connected.set()
        host_agent.set_status_callback(status_hook)
        host_agent.encode_screen = lambda: b"\xff\xd8RDP-CLOUD-VIRTUAL-FRAME\xff\xd9"
        host_agent.apply_control = lambda item: (applied.append(dict(item)) or True)
        host_agent.release_all_inputs = lambda: None
        host_agent.clipboard_watch = no_clipboard
        host_agent.choose_save_path = lambda _name: str(destination)
        args = SimpleNamespace(server=BASE,device_id=paired["device_id"],secret=paired["agent_secret"],dynamic_password=paired["dynamic_password"])
        host_task = asyncio.create_task(host_agent.run_once(args, stop))
        def capture_host_failure(task):
            if not task.cancelled() and task.exception() is not None:
                host_failures.append(f"{type(task.exception()).__name__}: {task.exception()}")
        host_task.add_done_callback(capture_host_failure)
        wsbase = BASE.replace("https://","wss://").replace("http://","ws://")
        viewer = None
        try:
            await asyncio.wait_for(connected.wait(), timeout=45)
            async def new_viewer():
                ws = await websockets.connect(f"{wsbase}/ws/viewer/{paired['device_id']}",max_size=8*1024*1024,open_timeout=30)
                await event(ws,"relay_ready")
                await ws.send(json.dumps({"type":"auth","session_token":session}))
                await event(ws,"viewer_connected")
                return ws
            viewer = await new_viewer()
            await event(viewer,"host_approved")
            frame = await asyncio.wait_for(viewer.recv(),timeout=15)
            check(isinstance(frame,bytes) and b"RDP-CLOUD-VIRTUAL-FRAME" in frame,"No virtual screen frame")
            result["checks"]["live_websocket_frame_delivery"] = "PASS"

            await viewer.send(json.dumps({"type":"control","event":"mouse_move","x":0.4,"y":0.6}))
            deadline = time.monotonic()+10
            while time.monotonic()<deadline and not applied: await asyncio.sleep(.05)
            check(any(x.get("event")=="mouse_move" for x in applied),"Input relay not observed by virtual host")
            result["checks"]["input_relay_virtual_host"] = "PASS"

            payload = os.urandom(TOTAL)
            digest = hashlib.sha256(payload).hexdigest()
            tid = uuid.uuid4().hex
            compressor = zstandard.ZstdCompressor(level=3)
            chunks = [compressor.compress(payload[i:i+CHUNK]) for i in range(0,TOTAL,CHUNK)]
            manifest = {"type":"transfer_init","transfer_id":tid,"name":destination.name,"total_size":TOTAL,
                "sha256":digest,"chunk_size":CHUNK,"compression":"zstd"}
            await viewer.send(json.dumps(manifest))
            initial = await event(viewer,"transfer_resume_req")
            check(initial.get("next_offset")==0,f"Initial resume offset: {initial}")
            await viewer.send(json.dumps({"type":"transfer_chunk","transfer_id":tid,"offset":0,"data":base64.b64encode(chunks[0]).decode()}))
            ack = await event(viewer,"transfer_ack")
            check(ack.get("next_offset")==CHUNK,f"First ACK: {ack}")

            await viewer.close(code=4001,reason="intentional mid-transfer disconnect")
            viewer = None
            await asyncio.sleep(1)
            viewer = await new_viewer()
            await event(viewer,"host_approved")
            await viewer.send(json.dumps(manifest))
            resumed = await event(viewer,"transfer_resume_req")
            check(resumed.get("next_offset")==CHUNK,f"Resume did not continue from persisted ACK: {resumed}")
            for offset in range(CHUNK,TOTAL,CHUNK):
                await viewer.send(json.dumps({"type":"transfer_chunk","transfer_id":tid,"offset":offset,
                    "data":base64.b64encode(chunks[offset//CHUNK]).decode()}))
                ack = await event(viewer,"transfer_ack")
                check(ack.get("next_offset")==min(offset+CHUNK,TOTAL),f"Unexpected ACK: {ack}")
            await viewer.send(json.dumps({"type":"transfer_complete","transfer_id":tid}))
            complete = await event(viewer,"transfer_complete",timeout=30)
            check(complete.get("verified") is True and complete.get("sha256")==digest,f"Checksum result: {complete}")
            check(destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest()==digest,"Saved file checksum mismatch")
            check(consents>=2,f"Expected consent hook on both viewer sessions; got {consents}")
            result["checks"]["synthetic_auto_consent_hook"] = "PASS"
            result["host_status"] = host_status
            result["checks"]["zstd_2mib_resume_sha256"] = "PASS"
            result["transfer"] = {"bytes":TOTAL,"chunk_size":CHUNK,"chunks":len(chunks),"compression":"zstd",
                "interrupted_after_acknowledged_bytes":CHUNK,"resume_offset":resumed["next_offset"],"sha256":digest}
        finally:
            if viewer is not None: await viewer.close()
            stop.set()
            try: await asyncio.wait_for(host_task,timeout=15)
            except Exception:
                host_task.cancel()
                await asyncio.gather(host_task,return_exceptions=True)
            for f in root.glob("*"): f.unlink(missing_ok=True)
            root.rmdir()
            result["host_agent_failures"] = host_failures
            result["host_status"] = host_status
        result["status"] = "PASS"
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
        if "host_status" in locals(): result["host_status"] = host_status
        if "host_failures" in locals(): result["host_agent_failures"] = host_failures
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(result,indent=2,sort_keys=True),encoding="utf-8")
    print("CLOUD_E2E_JSON_BEGIN")
    print(json.dumps(result,indent=2,sort_keys=True))
    print("CLOUD_E2E_JSON_END")
    return 0 if result["status"]=="PASS" else 1

if __name__=="__main__": raise SystemExit(asyncio.run(main()))
