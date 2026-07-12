<#
.SYNOPSIS
    KylinOS SecOps Agent - single-host status self-check

.DESCRIPTION
    Prints three status sections to quickly judge whether the local Agent is healthy:
      1) Process : are backend.exe and the Agent desktop exe alive
      2) Port    : is the backend listen port (default 8000) reachable
      3) Health  : are GET /health and /metrics reachable and OK
    Pure Windows PowerShell 5.1+, no third-party dependencies.

.PARAMETER Port
    Backend listen port, default 8000

.PARAMETER HostName
    Backend address, default 127.0.0.1

.EXAMPLE
    .\check-agent-status.ps1
    .\check-agent-status.ps1 -Port 8000
#>
param(
    [int]    $Port = 8000,
    [string] $HostName = '127.0.0.1'
)

$ErrorActionPreference = 'SilentlyContinue'
$ESC = [char]27
$Reset = "$ESC[0m"

function Write-Section($title) {
    Write-Host ""
    Write-Host "$ESC[1;36m=== $title ===$Reset"
}

function Write-Status($ok, $msg) {
    if ($ok) { $mark = "$ESC[32m[OK]$Reset" } else { $mark = "$ESC[31m[FAIL]$Reset" }
    Write-Host ("  {0} {1}" -f $mark, $msg)
}

$backendExe = 'backend.exe'
$base       = "http://${HostName}:${Port}"

# ---- 1. Process ----
Write-Section "1. Process"
$be = Get-Process -Name ($backendExe -replace '\.exe$') -ErrorAction SilentlyContinue
if ($be) { Write-Status $true "backend.exe running (PID: $($be.Id))" } else { Write-Status $false "backend.exe not running" }

# The desktop shell exe is named 麒麟OS安全智能运维Agent.exe (Chinese). Match it with a
# wildcard on the ASCII substring "Agent" so the script stays encoding-safe (ASCII-only).
$ae = Get-Process -Name '*Agent*' -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike 'backend*' }
if ($ae) { Write-Status $true "Agent desktop process running (PID: $($ae[0].Id))" } else { Write-Status $false "Agent desktop process not running (desktop window may not be started)" }

# ---- 2. Port ----
Write-Section "2. Port (Port $Port)"
$tcp = Test-NetConnection -ComputerName $HostName -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
Write-Status $tcp "port $Port listening"
if (-not $tcp) {
    Write-Section "Conclusion"
    Write-Status $false "Agent not ready (port unreachable). Start the desktop app first, then retry."
    exit 1
}

# ---- 3. Health ----
Write-Section "3. Health (Health and Metrics)"
try {
    $h = Invoke-RestMethod -Uri "$base/health" -TimeoutSec 5
    Write-Status $true "/health -> status=$($h.status), version=$($h.version), service=$($h.service)"
} catch {
    Write-Status $false "/health unreachable: $_"
}

try {
    $m = Invoke-WebRequest -Uri "$base/metrics" -TimeoutSec 5 -UseBasicParsing
    $up = ($m.Content -split "`n" | Where-Object { $_ -like 'kylin_agent_uptime_seconds*' }) -join ''
    $rq = ($m.Content -split "`n" | Where-Object { $_ -like 'kylin_agent_requests_total*' }) -join ''
    Write-Status $true "/metrics reachable  $up  $rq"
} catch {
    Write-Status $false "/metrics unreachable: $_"
}

# ---- Conclusion ----
Write-Section "Conclusion"
if ($be -and $tcp) {
    Write-Status $true "Agent process and port are healthy and ready to serve."
    exit 0
} else {
    Write-Status $false "Anomaly detected, see details above. Logs: install dir resources/logs/."
    exit 1
}
