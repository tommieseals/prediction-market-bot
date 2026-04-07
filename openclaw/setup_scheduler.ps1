# OpenClaw Anomaly - Windows Task Scheduler Setup (RTX)
# Creates recurring tasks that run from the real project root via task_runner.ps1

$ErrorActionPreference = "Stop"
$runnerPath = "C:\Users\User\clawd\openclaw\task_runner.ps1"

function Register-OpenClawTask {
    param(
        [string]$TaskName,
        [string]$Mode,
        [Microsoft.Management.Infrastructure.CimInstance]$Trigger,
        [string]$Description
    )

    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runnerPath`" -Mode $Mode"
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $Trigger -Settings $settings -Description $Description -Force | Out-Null
}

$now = Get-Date
$proactiveTrigger = New-ScheduledTaskTrigger -Once -At ($now.AddMinutes(5)) -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration (New-TimeSpan -Days 3650)
$evalTrigger = New-ScheduledTaskTrigger -Once -At ($now.AddMinutes(20)) -RepetitionInterval (New-TimeSpan -Hours 12) -RepetitionDuration (New-TimeSpan -Days 3650)
$morningTrigger = New-ScheduledTaskTrigger -Daily -At 8:03AM
$metaTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 2:07AM

Register-OpenClawTask -TaskName "OpenClaw-Proactive" -Mode "proactive" -Trigger $proactiveTrigger -Description "Run the 22-step OpenClaw proactive cycle every 6 hours"
Register-OpenClawTask -TaskName "OpenClaw-MorningPulse" -Mode "morning-pulse" -Trigger $morningTrigger -Description "Run the OpenClaw morning pulse each day"
Register-OpenClawTask -TaskName "OpenClaw-META" -Mode "meta" -Trigger $metaTrigger -Description "Run the weekly OpenClaw meta cycle"
Register-OpenClawTask -TaskName "OpenClaw-Eval" -Mode "eval" -Trigger $evalTrigger -Description "Run the OpenClaw eval harness every 12 hours"

Get-ScheduledTask | Where-Object { $_.TaskName -like "OpenClaw-*" } | Select-Object TaskName, State, TaskPath

