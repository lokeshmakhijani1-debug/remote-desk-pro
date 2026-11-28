import sys, time, threading, uvicorn
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

threading.Thread(target=run_server, daemon=True).start()
time.sleep(3)

sys.argv = ["host_agent.py", "--server", "http://127.0.0.1:8000"]
import agent.host_agent as ha
if hasattr(ha, "main"):
    ha.main()
else:
    while True:
        time.sleep(1)
