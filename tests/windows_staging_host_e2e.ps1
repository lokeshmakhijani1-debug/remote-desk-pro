[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$BaseUrl,
    [Parameter(Mandatory=$true)][ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })][string]$ExePath,
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$ReportPath
)
$ErrorActionPreference = "Stop"
$BaseUrl = $BaseUrl.TrimEnd("/")
$results = [ordered]@{ status="FAIL"; target=$BaseUrl; runner="windows-latest"; checks=[ordered]@{}; device_id=$null; test_account=$null; executable_sha256=(Get-FileHash -LiteralPath $ExePath -Algorithm SHA256).Hash; errors=@() }
$process = $null
$firewallRule = "RDP-V2-E2E-" + [guid]::NewGuid().ToString("N")
$previousAppData = $env:APPDATA
$testAppData = Join-Path $env:TEMP ("rdp-v2-e2e-" + [guid]::NewGuid().ToString("N"))

function Invoke-Api {
    param([string]$Method, [string]$Path, [object]$Body=$null, [hashtable]$Headers=@{})
    $params = @{ Method=$Method; Uri="$BaseUrl$Path"; Headers=$Headers; TimeoutSec=30 }
    if ($null -ne $Body) { $params.ContentType="application/json"; $params.Body=($Body | ConvertTo-Json -Depth 12 -Compress) }
    Invoke-RestMethod @params
}
function Get-DeviceOnline {
    param([string]$DeviceId, [hashtable]$Headers)
    $devices = Invoke-Api -Method GET -Path "/api/devices" -Headers $Headers
    $device = @($devices | Where-Object { $_.device_id -eq $DeviceId } | Select-Object -First 1)
    if ($device.Count -eq 0) { return $false }
    return [bool]$device[0].online
}
function Wait-DeviceState {
    param([string]$DeviceId, [hashtable]$Headers, [bool]$ExpectedOnline, [int]$TimeoutSeconds)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try { if ((Get-DeviceOnline -DeviceId $DeviceId -Headers $Headers) -eq $ExpectedOnline) { return $true } }
        catch { Write-Host "Device-state poll retry: $($_.Exception.Message)" }
        Start-Sleep -Seconds 3
    } while ([DateTime]::UtcNow -lt $deadline)
    return $false
}
try {
    New-Item -ItemType Directory -Force -Path $testAppData | Out-Null
    $env:APPDATA = $testAppData
    $health = Invoke-Api -Method GET -Path "/health"
    if ($health.status -ne "ok" -or $health.database -ne "postgresql") { throw "Staging health/database verification failed: $($health | ConvertTo-Json -Compress)" }
    $results.checks["staging_health_postgresql"] = "PASS"

    $suffix = [guid]::NewGuid().ToString("N").Substring(0,16)
    $email = "rdp-v2-windows-e2e-$suffix@example.com"
    $password = "RdpV2-" + [guid]::NewGuid().ToString("N") + "aA9!"
    $registration = Invoke-Api -Method POST -Path "/api/auth/register" -Body @{ email=$email; password=$password }
    if (-not $registration.access_token) { throw "Staging registration did not return an access token." }
    $headers = @{ Authorization="Bearer $($registration.access_token)" }
    $results.test_account = $email
    $results.checks["temporary_test_account_registration"] = "PASS"

    $paired = Invoke-Api -Method POST -Path "/api/devices/pair" -Body @{ name="GitHub Actions Windows E2E $suffix" } -Headers $headers
    if (-not $paired.device_id -or -not $paired.agent_secret) { throw "Device pairing did not return required host credentials." }
    $results.device_id = [string]$paired.device_id
    $results.checks["real_staging_device_registration"] = "PASS"

    $resolvedExe = (Resolve-Path -LiteralPath $ExePath).Path
    $process = Start-Process -FilePath $resolvedExe -ArgumentList @("--server",$BaseUrl,"--device-id",[string]$paired.device_id,"--secret",[string]$paired.agent_secret) -PassThru -WindowStyle Hidden
    $results.agent_pid = $process.Id
    if (-not (Wait-DeviceState -DeviceId $paired.device_id -Headers $headers -ExpectedOnline $true -TimeoutSeconds 120)) { throw "Packaged Windows host agent did not register online within 120 seconds." }
    $results.checks["packaged_windows_host_online"] = "PASS"

    $logPath = Join-Path $testAppData "RemoteDeskPro\agent.log"
    $heartbeatDeadline = [DateTime]::UtcNow.AddSeconds(55)
    $heartbeatCount = 0
    do {
        if (Test-Path -LiteralPath $logPath) { $heartbeatCount = @(Select-String -LiteralPath $logPath -Pattern "Server heartbeat acknowledged\.").Count }
        if ($heartbeatCount -ge 2) { break }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $heartbeatDeadline)
    if ($heartbeatCount -lt 2) { throw "Expected at least two server heartbeat acknowledgements at the 15-second cadence; observed $heartbeatCount." }
    $results.checks["15_second_heartbeat_acknowledgements"] = "PASS"
    $results.heartbeat_ack_count = $heartbeatCount

    $hostName = ([uri]$BaseUrl).DnsSafeHost
    $remoteIps = @(Resolve-DnsName -Name $hostName -Type A -ErrorAction Stop | Where-Object { $_.IPAddress } | Select-Object -ExpandProperty IPAddress -Unique)
    if ($remoteIps.Count -eq 0) { throw "Could not resolve staging A records for controlled network interruption." }
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) { throw "Windows runner is not elevated; refusing to claim network-drop recovery without a controlled firewall test." }

    New-NetFirewallRule -DisplayName $firewallRule -Direction Outbound -Action Block -Program $resolvedExe -Protocol TCP -RemotePort 443 -RemoteAddress $remoteIps -Profile Any | Out-Null
    if (-not (Wait-DeviceState -DeviceId $paired.device_id -Headers $headers -ExpectedOnline $false -TimeoutSeconds 75)) { throw "Staging did not report host offline after controlled network interruption." }
    $results.checks["network_drop_offline_transition"] = "PASS"

    Get-NetFirewallRule -DisplayName $firewallRule -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    if (-not (Wait-DeviceState -DeviceId $paired.device_id -Headers $headers -ExpectedOnline $true -TimeoutSeconds 150)) { throw "Packaged Windows host agent did not reconnect after network restoration." }
    $results.checks["network_drop_recovery"] = "PASS"

    if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force; $process.WaitForExit(15000) }
    if (-not (Wait-DeviceState -DeviceId $paired.device_id -Headers $headers -ExpectedOnline $false -TimeoutSeconds 30)) { throw "Staging did not report host offline after Windows agent exited." }
    $results.checks["agent_exit_offline_transition"] = "PASS"
    $results.status = "PASS"
}
catch {
    $results.errors += $_.Exception.Message
    throw
}
finally {
    Get-NetFirewallRule -DisplayName $firewallRule -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    $env:APPDATA = $previousAppData
    $results.finished_at_utc = [DateTime]::UtcNow.ToString("o")
    $results | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $ReportPath -Encoding utf8
    Write-Host ($results | ConvertTo-Json -Depth 12)
}
