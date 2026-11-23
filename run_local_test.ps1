[CmdletBinding()]
param([string]$Python = "python", [string]$Npm = "npm")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendProcess = $null
$FrontendProcess = $null
$AgentProcess = $null
function Stop-ChildProcess($Process) {
    if ($null -ne $Process -and -not $Process.HasExited) { Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue }
}
try {
    Set-Location $Root
    if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) { throw "Python 3.11+ was not found." }
    if (-not (Get-Command $Npm -ErrorAction SilentlyContinue)) { throw "Node.js 20+ npm was not found." }
    & $Python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
    if ($LASTEXITCODE -ne 0) { throw "Python 3.11 or newer is required." }
    $VenvPath = Join-Path $Root ".venv"
    $VenvPython = Join-Path $VenvPath "Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) { & $Python -m venv $VenvPath; if ($LASTEXITCODE -ne 0) { throw "Could not create the project virtual environment." } }
    & $VenvPython -c "import fastapi,uvicorn,websockets,mss,PIL,pyautogui,pyperclip,certifi,zstandard,imageio_ffmpeg" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing backend and Windows-agent Python dependencies (first run or dependency update)..."
        & $VenvPython -m pip install -r (Join-Path $Root "requirements.txt") -r (Join-Path $Root "agent\requirements.txt")
        if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }
    }
    # Prevent a previously installed EXE (often configured for Render) from competing with this local Python agent.
    Get-CimInstance Win32_Process -Filter "name = 'RemoteDeskPro-Agent.exe'" -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    $LogPath = Join-Path $Root "logs"
    New-Item -ItemType Directory -Path $LogPath -Force | Out-Null
    $env:RDP_SERVER = "http://127.0.0.1:8000"
    $env:RDP_LOG_DIR = $LogPath
    $BackendProcess = Start-Process -FilePath $VenvPython -ArgumentList @("-m","uvicorn","backend.main:app","--host","0.0.0.0","--port","8000","--ws-ping-interval","15","--ws-ping-timeout","45","--ws-max-size","16777216") -WorkingDirectory $Root -PassThru -WindowStyle Minimized
    $FrontendPath = Join-Path $Root "frontend"
    if (-not (Test-Path (Join-Path $FrontendPath "node_modules"))) {
        Write-Host "Installing frontend dependencies (first run only)..."
        Push-Location $FrontendPath
        try { & $Npm install; if ($LASTEXITCODE -ne 0) { throw "npm install failed" } } finally { Pop-Location }
    }
    $FrontendProcess = Start-Process -FilePath $Npm -ArgumentList @("run","dev","--","--host","0.0.0.0") -WorkingDirectory $FrontendPath -PassThru -WindowStyle Minimized
    $Deadline = (Get-Date).AddSeconds(45)
    $Healthy = $false
    while ((Get-Date) -lt $Deadline) {
        try { $Health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 3; if ($Health.status -eq "ok") { $Healthy = $true; break } } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $Healthy) { throw "Backend did not become healthy. Inspect the minimized backend process." }
    $AgentArgs = @("agent/host_agent.py","--server","http://127.0.0.1:8000")
    if ($env:RDP_DEVICE_ID -and $env:RDP_AGENT_SECRET) {
        $AgentArgs += @("--device-id",$env:RDP_DEVICE_ID,"--secret",$env:RDP_AGENT_SECRET)
        if ($env:RDP_DYNAMIC_PASSWORD) { $AgentArgs += @("--dynamic-password",$env:RDP_DYNAMIC_PASSWORD) }
    } else { Write-Host "Agent will open its desktop sign-in/pairing UI against the local backend." }
    $AgentProcess = Start-Process -FilePath $VenvPython -ArgumentList $AgentArgs -WorkingDirectory $Root -PassThru -WindowStyle Normal
    Start-Sleep -Seconds 2
    if ($AgentProcess -and -not $AgentProcess.HasExited) {
        $AgentProcess.Refresh()
        if ($AgentProcess.MainWindowHandle -ne 0) {
            Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class RdpWindowFocus { [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow); [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); }' -ErrorAction SilentlyContinue
            [RdpWindowFocus]::ShowWindow($AgentProcess.MainWindowHandle, 9) | Out-Null
            [RdpWindowFocus]::SetForegroundWindow($AgentProcess.MainWindowHandle) | Out-Null
        }
    }
    Write-Host ""
    Write-Host "Dashboard: http://127.0.0.1:5173"
    Write-Host "Backend:   http://127.0.0.1:8000"
    Write-Host "Health:    http://127.0.0.1:8000/api/health"
    Write-Host "Log tail:  http://127.0.0.1:8000/api/logs/tail?lines=100"
    Write-Host "Backend log: $LogPath\backend.log"
    Write-Host "Agent log:   $LogPath\agent.log"
    Write-Host ""
    Write-Host "Quick verification checklist:"
    Write-Host "1. Pair/sign in the agent, connect from the dashboard, and enable Black Curtain."
    Write-Host "   Confirm the local display is black, remote frames remain live, and Ctrl+Alt+Shift+B restores the display."
    Write-Host "2. Transfer a file larger than 1 MB; confirm 512 KB chunk progress and SHA-256 verification."
    Write-Host "3. Leave the session idle for 60 seconds, briefly interrupt network access, and confirm heartbeat detection and automatic reconnect."
    Write-Host "4. Inspect logs: Get-Content .\logs\backend.log -Tail 100; Get-Content .\logs\agent.log -Tail 100"
    Write-Host ""
    Write-Host "Press Ctrl+C here to stop all processes started by this script."
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    Stop-ChildProcess $AgentProcess
    Stop-ChildProcess $FrontendProcess
    Stop-ChildProcess $BackendProcess
}

