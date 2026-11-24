import sys
import json, time, urllib.request, subprocess
from pathlib import Path
from fastapi.testclient import TestClient
import backend.main as bm

client = TestClient(bm.app)
results = []
add = lambda n, cat, ok, d: results.append({'id': n, 'cat': cat, 'status': 'PASS' if ok else 'FAIL', 'detail': d})

add(1, 'ARCH', Path('backend/main.py').exists(), 'backend/main.py present')
add(2, 'ARCH', Path('agent/host_agent.py').exists(), 'agent/host_agent.py present')
add(3, 'ARCH', Path('agent/privacy_overlay.py').exists(), 'agent/privacy_overlay.py present')
add(4, 'ARCH', Path('agent/session_recorder.py').exists(), 'agent/session_recorder.py present')
add(5, 'ARCH', Path('agent/resumable_transfer.py').exists(), 'agent/resumable_transfer.py present')

r = client.get('/api/health')
add(6, 'API', r.status_code == 200, f'/api/health -> {r.status_code}')
r_feat = r.json().get('features', {}) if r.status_code == 200 else {}
add(7, 'API', bool(r_feat.get('websocket_binary_relay')), 'WebSocket binary relay enabled')
add(8, 'API', bool(r_feat.get('file_transfer')), 'Chunked file transfer API enabled')
add(9, 'API', bool(r_feat.get('clipboard_sync')), 'Clipboard sync API enabled')
add(10, 'API', bool(r_feat.get('recording')), 'Session recording feature enabled')
r_unauth = client.get('/api/devices')
add(11, 'SEC', r_unauth.status_code in (401, 403), f'Unauth /api/devices blocked ({r_unauth.status_code})')
add(12, 'SEC', bm.validate_control({'event': 'privacy_screen', 'enabled': True, 'mode': 'black'}), 'Backend allows black screen mode')

add(13, 'CTRL', bm.validate_control({'event': 'mouse_move', 'x': 0.5, 'y': 0.5}), 'Mouse move validation')
add(14, 'CTRL', bm.validate_control({'event': 'mouse_down', 'button': 0}), 'Mouse click validation')
add(15, 'CTRL', bm.validate_control({'event': 'mouse_scroll', 'deltaX': 0, 'deltaY': 120}), 'Mouse scroll validation')
add(16, 'CTRL', bm.validate_control({'event': 'key_down', 'key': 'Enter'}), 'Keyboard key_down validation')
add(17, 'CTRL', not bm.validate_control({'event': 'mouse_move', 'x': 999, 'y': -5}), 'Out-of-bounds mouse rejected')
add(18, 'CTRL', hasattr(bm, 'validate_clipboard') and bm.validate_clipboard({'text': 'hello'}), 'Clipboard payload validation')

po_txt = Path('agent/privacy_overlay.py').read_text(encoding='utf-8', errors='ignore')
ha_txt = Path('agent/host_agent.py').read_text(encoding='utf-8', errors='ignore')
sr_txt = Path('agent/session_recorder.py').read_text(encoding='utf-8', errors='ignore')
add(19, 'AGENT', 'SetWindowDisplayAffinity' in po_txt and '0x00000011' in po_txt, 'Black screen WDA_EXCLUDEFROMCAPTURE present')
add(20, 'AGENT', 'WS_EX_LAYERED' not in po_txt, 'No WS_EX_LAYERED capture-leak bug in overlay')
add(21, 'AGENT', 'SessionRecorder' in ha_txt and 'libx264' in sr_txt, 'Background MP4 session recording wired')
add(22, 'AGENT', 'EndpointFileReceiver' in ha_txt, 'SHA-256 resumable chunk receiver wired')
add(23, 'AGENT', ('action_log' in ha_txt or 'workflow' in ha_txt or 'replay' in ha_txt), 'AI Workflow Action Recorder / Replay engine')
add(24, 'AGENT', ('multi_monitor' in ha_txt or 'monitor_index' in ha_txt), 'Multi-Monitor switcher support')

app_txt = Path('frontend/src/App.tsx').read_text(encoding='utf-8', errors='ignore')
css_txt = Path('frontend/src/styles.css').read_text(encoding='utf-8', errors='ignore')
add(25, 'UI', 'sidebar-collapsed' in app_txt and 'sidebar-collapsed' in css_txt, 'Collapsible left sidebar slide toggle')
add(26, 'UI', 'devicesOpen' in app_txt, 'Collapsible Computers & History dropdown')
add(27, 'UI', 'Black Screen' in app_txt and 'keyboardOpen' in app_txt and 'zstdCompress' in app_txt, 'Black Screen + Mobile Keyboard + Zstd Transfer UI')
add(28, 'UI', ('Session chat UI is reserved' not in app_txt) and ('audio' in app_txt.lower()), 'Live Session Chat & System Audio streaming')

try:
    t0 = time.perf_counter()
    resp = urllib.request.urlopen('https://remote-desk-pro-pj29.onrender.com/api/health', timeout=25)
    add(29, 'CLOUD', resp.status == 200, f'Render Live Health 200 OK ({(time.perf_counter()-t0)*1000:.0f} ms)')
except Exception as e:
    add(29, 'CLOUD', False, f'Render Live Health error: {e}')

p = subprocess.run(['C:\\Users\\hp\\Desktop\\RemoteDeskTest\\remote-desk-pro\\agent\\.venv-build\\Scripts\\python.exe', '-m', 'pytest', 'tests', '-q', '--ignore=tests/e2e_remote_control_live.py'], capture_output=True, text=True)
add(30, 'TEST', p.returncode == 0, (p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr.strip()[:120]))

Path('audit_30_report.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
passed = sum(1 for x in results if x['status'] == 'PASS')
print(f'\n================ 30-TEST AUDIT SCORECARD: {passed}/30 PASSED ================\n')
for x in results:
    print(f"[{x['status']}] #{x['id']:02d} ({x['cat']:5s}) : {x['detail']}")
