# TOKEN USAGE MONITOR - Real-time token tracking and enforcement
# Runs as background service to monitor and enforce token budgets
# Created: 2026-04-07 by directive from Rusty

# Import enforcer
. "C:\Users\USER\clawd\scripts\token-budget-enforcer.ps1"

$MONITOR_LOG = "C:\Users\USER\clawd\logs\token-monitor.log"
$CHECK_INTERVAL = 60 # Check every 60 seconds
$ALERT_SCRIPT = "C:\Users\USER\clawd\scripts\forward-to-telegram.ps1"

function Write-MonitorLog {
    param([string]$Message)
    $entry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $Message"
    Add-Content -Path $MONITOR_LOG -Value $entry
}

function Monitor-TokenUsage {
    Write-MonitorLog "Token usage monitor started"
    Write-Host "🔍 Token usage monitor running..." -ForegroundColor Cyan
    
    $lastAlertTime = @{
        Hourly = $null
        Daily = $null
        Weekly = $null
        Monthly = $null
    }
    
    while ($true) {
        try {
            # Get current status
            $status = Get-TokenBudgetStatus
            
            # Check for emergency mode
            if ($status.EmergencyMode) {
                Write-MonitorLog "EMERGENCY MODE DETECTED - Monitor paused"
                Write-Host "❌ Emergency mode active - monitor paused" -ForegroundColor Red
                Start-Sleep -Seconds $CHECK_INTERVAL
                continue
            }
            
            # Check daily usage and enforce limits
            if ($status.Daily.Percent -ge 100) {
                Write-MonitorLog "CRITICAL: Daily limit exceeded ($($status.Daily.Used)/$($status.Daily.Limit))"
                Invoke-EmergencyShutdown "Daily token limit exceeded: $($status.Daily.Used)/$($status.Daily.Limit)"
            }
            
            # 90% daily warning
            if ($status.Daily.Percent -ge 90 -and ($null -eq $lastAlertTime.Daily -or ((Get-Date) - $lastAlertTime.Daily).TotalMinutes -gt 30)) {
                Write-MonitorLog "WARNING: 90% daily limit ($($status.Daily.Used)/$($status.Daily.Limit))"
                & $ALERT_SCRIPT -Message "⚠️ 90% daily token limit: $($status.Daily.Used)/$($status.Daily.Limit) ($($status.Daily.Percent)%)"
                $lastAlertTime.Daily = Get-Date
            }
            
            # 80% daily warning
            elseif ($status.Daily.Percent -ge 80 -and ($null -eq $lastAlertTime.Daily -or ((Get-Date) - $lastAlertTime.Daily).TotalHours -gt 2)) {
                Write-MonitorLog "WARNING: 80% daily limit ($($status.Daily.Used)/$($status.Daily.Limit))"
                & $ALERT_SCRIPT -Message "⚠️ 80% daily token limit: $($status.Daily.Used)/$($status.Daily.Limit) ($($status.Daily.Percent)%)"
                $lastAlertTime.Daily = Get-Date
            }
            
            # Hourly limit check
            if ($status.Hourly.Percent -ge 100) {
                Write-MonitorLog "CRITICAL: Hourly limit exceeded ($($status.Hourly.Used)/$($status.Hourly.Limit))"
                & $ALERT_SCRIPT -Message "🚨 HOURLY token limit exceeded: $($status.Hourly.Used)/$($status.Hourly.Limit)"
            }
            
            # Weekly limit check
            if ($status.Weekly.Percent -ge 90 -and ($null -eq $lastAlertTime.Weekly -or ((Get-Date) - $lastAlertTime.Weekly).TotalHours -gt 12)) {
                Write-MonitorLog "WARNING: 90% weekly limit ($($status.Weekly.Used)/$($status.Weekly.Limit))"
                & $ALERT_SCRIPT -Message "⚠️ 90% weekly token limit: $($status.Weekly.Used)/$($status.Weekly.Limit) ($($status.Weekly.Percent)%)"
                $lastAlertTime.Weekly = Get-Date
            }
            
            # Monthly limit check
            if ($status.Monthly.Percent -ge 100) {
                Write-MonitorLog "CRITICAL: Monthly limit exceeded ($($status.Monthly.Used)/$($status.Monthly.Limit))"
                Invoke-EmergencyShutdown "Monthly token limit exceeded: $($status.Monthly.Used)/$($status.Monthly.Limit)"
            }
            
            # Log status every hour
            $currentMinute = (Get-Date).Minute
            if ($currentMinute -eq 0) {
                Write-MonitorLog "Status - Hourly: $($status.Hourly.Percent)% | Daily: $($status.Daily.Percent)% | Weekly: $($status.Weekly.Percent)% | Monthly: $($status.Monthly.Percent)%"
            }
            
        } catch {
            Write-MonitorLog "ERROR: $($_.Exception.Message)"
            Write-Host "❌ Monitor error: $($_.Exception.Message)" -ForegroundColor Red
        }
        
        # Wait for next check
        Start-Sleep -Seconds $CHECK_INTERVAL
    }
}

# Start monitoring
Write-Host "Starting token usage monitor..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Monitor-TokenUsage
