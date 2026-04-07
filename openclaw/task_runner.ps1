param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("proactive", "morning-pulse", "meta", "eval")]
    [string]$Mode
)

$ErrorActionPreference = "Stop"
$projectRoot = "C:\Users\User\clawd"
$pythonPath = "C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe"
$logDir = Join-Path $projectRoot "openclaw\audits\task-runs"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Set-Location $projectRoot

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir ("{0}-{1}.log" -f $Mode, $timestamp)

& $pythonPath -m openclaw.main --mode=$Mode *>&1 | Tee-Object -FilePath $logFile
exit $LASTEXITCODE
