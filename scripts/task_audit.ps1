# Scheduled Task Audit
$ErrorActionPreference = 'Continue'

$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$logDir = "C:\Users\USER\clawd\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "task_audit_$timestamp.log"

$tasks = @(
    "\\MiroFishConnector_Noon",
    "\\MiroFishConnector_3PM",
    "\\MiroFish_Validate_Primary",
    "\\MiroFish_Validate_Backup"
)

"Task Audit - $timestamp" | Out-File -FilePath $logFile
"==========================" | Out-File -FilePath $logFile -Append

foreach ($task in $tasks) {
    try {
        $raw = schtasks /Query /TN $task /V /FO LIST 2>$null
        if (-not $raw) {
            "$task | MISSING" | Out-File -FilePath $logFile -Append
            continue
        }
        $lastRun = ($raw | Select-String -Pattern "Last Run Time" | ForEach-Object { $_.Line.Split(':',2)[1].Trim() })
        $lastResult = ($raw | Select-String -Pattern "Last Result" | ForEach-Object { $_.Line.Split(':',2)[1].Trim() })
        $status = ($raw | Select-String -Pattern "Status" | ForEach-Object { $_.Line.Split(':',2)[1].Trim() })
        "$task | $status | LastRun=$lastRun | LastResult=$lastResult" | Out-File -FilePath $logFile -Append
    } catch {
        "$task | ERROR | $($_.Exception.Message)" | Out-File -FilePath $logFile -Append
    }
}

Write-Host "Task audit complete: $logFile"
