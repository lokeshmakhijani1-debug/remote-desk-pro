$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = Get-Command python -ErrorAction Stop
if (-not (Test-Path ".venv-build")) { & $python.Source -m venv .venv-build }
$venvPython = Join-Path $PSScriptRoot ".venv-build\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt pyinstaller
& $venvPython -m PyInstaller --noconfirm --clean --onefile --windowed --name RemoteDeskPro-Agent --collect-all mss --collect-all pyautogui --collect-all pyperclip --hidden-import tkinter --hidden-import websockets host_agent.py
