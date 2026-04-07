# Clawdbot Watchdog - Monitors and restarts gateway if it dies
# Runs in background, checks every 60 seconds

$logFile = "$env:USERPROFILE\clawd\logs\watchdog.log"

function Write-Log($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp - $msg" | Out-File -Append $logFile
}

Write-Log "Watchdog started"

while ($true) {
    # Check if clawdbot gateway is running
    $nodeProcs = Get-Process -Name "node" -ErrorAction SilentlyContinue
    $clawdbotRunning = $false
    
    foreach ($proc in $nodeProcs) {
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)").CommandLine
            if ($cmdLine -like "*clawdbot*" -or $cmdLine -like "*gateway*") {
                $clawdbotRunning = $true
                break
            }
        } catch {}
    }
    
    if (-not $clawdbotRunning) {
        Write-Log "Clawdbot not running! Restarting..."
        Start-Process "powershell.exe" -ArgumentList "-WindowStyle Hidden -Command `"clawdbot gateway start`"" -WindowStyle Hidden
        Write-Log "Restart command sent"
        Start-Sleep -Seconds 30  # Wait for startup before checking again
    }
    
    Start-Sleep -Seconds 60
}
