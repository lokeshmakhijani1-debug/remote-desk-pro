$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = Get-Command python -ErrorAction Stop
if (-not (Test-Path ".venv-build")) { & $python.Source -m venv .venv-build }
$venvPython = Join-Path $PSScriptRoot ".venv-build\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt pyinstaller
& $venvPython -m PyInstaller --noconfirm --clean --onefile --windowed --name RemoteDeskPro-Agent --collect-all mss --collect-all pyautogui --collect-all pyperclip --collect-all imageio_ffmpeg --collect-data imageio_ffmpeg --collect-data certifi --collect-all webview --hidden-import workflow_engine --hidden-import telemetry --hidden-import win32gui --hidden-import win32process --hidden-import psutil --hidden-import session_recorder --hidden-import privacy_overlay --hidden-import tkinter --hidden-import desktop_app --hidden-import certifi --hidden-import websockets.asyncio.client --hidden-import websockets.asyncio.connection host_agent.py
