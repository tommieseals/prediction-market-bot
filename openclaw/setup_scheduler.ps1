# OpenClaw Anomaly — Windows Task Scheduler Setup (RTX)
# Run as Administrator

$pythonPath = "C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe"
$workDir = "C:\Users\User\clawd"

# Proactive cycle every 6 hours
schtasks /create /tn "OGE-Proactive" `
  /tr "$pythonPath -m openclaw.main --mode=proactive" `
  /sc hourly /mo 6 /st 00:17 `
  /sd (Get-Date -Format "MM/dd/yyyy") `
  /ru $env:USERNAME `
  /f

# Morning pulse daily at 8:03 AM
schtasks /create /tn "OGE-MorningPulse" `
  /tr "$pythonPath -m openclaw.main --mode=morning-pulse" `
  /sc daily /st 08:03 `
  /sd (Get-Date -Format "MM/dd/yyyy") `
  /ru $env:USERNAME `
  /f

# META cycle weekly Sunday 2:07 AM
schtasks /create /tn "OGE-META" `
  /tr "$pythonPath -m openclaw.main --mode=meta" `
  /sc weekly /d SUN /st 02:07 `
  /sd (Get-Date -Format "MM/dd/yyyy") `
  /ru $env:USERNAME `
  /f

# Eval harness every 12 hours (offset from proactive)
schtasks /create /tn "OGE-Eval" `
  /tr "$pythonPath -m openclaw.main --mode=eval" `
  /sc hourly /mo 12 /st 03:33 `
  /sd (Get-Date -Format "MM/dd/yyyy") `
  /ru $env:USERNAME `
  /f

Write-Host "Task Scheduler entries created:"
schtasks /query /tn "OGE-*" /fo table
