@echo off
start /b uvicorn backend.main:app --host 127.0.0.1 --port 8000
timeout /t 5
start /b python agent\host_agent.py --server "http://127.0.0.1:8000"
