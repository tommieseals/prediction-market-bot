# START CLAWDBOT WITH BUDGET ENFORCEMENT
# This is the ONLY approved way to start Clawdbot
# Enforces hardcoded token limits and starts monitoring
# Created: 2026-04-07 by directive from Rusty

param(
    [switch]$Force,
    [switch]$SkipMonitor
)

$EMERGENCY_FLAG = "C:\Users\USER\clawd\.token-emergency"
$ENFORCER_SCRIPT = "C:\Users\USER\clawd\scripts\token-budget-enforcer.ps1"
$MONITOR_SCRIPT = "C:\Users\USER\clawd\scripts\token-usage-monitor.ps1"
$WRAPPER_SCRIPT = "C:\Users\USER\clawd\scripts\clawdbot-budget-wrapper.ps1"

Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  CLAWDBOT BUDGET-ENFORCED STARTUP" -ForegroundColor Cyan
Write-Host "  Hardcoded token limits - NO BYPASS ALLOWED" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check for emergency mode
if (Test-Path $EMERGENCY_FLAG) {
    Write-Host "❌ EMERGENCY MODE ACTIVE - CLAWDBOT LOCKED" -ForegroundColor Red
    Write-Host ""
    Write-Host "Emergency shutdown was triggered due to token budget violation." -ForegroundColor Red
    Write-Host ""
    Write-Host "Emergency details:" -ForegroundColor Yellow
    Get-Content $EMERGENCY_FLAG
    Write-Host ""
    Write-Host "To clear emergency mode (requires authorization):" -ForegroundColor Yellow
    Write-Host "  Remove-Item '$EMERGENCY_FLAG'" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# Import and check budget
. $ENFORCER_SCRIPT
$status = Get-TokenBudgetStatus

# Display status
Write-Host "📊 Current Token Budget Status:" -ForegroundColor Cyan
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host ("  Hourly:  {0,6}/{1,6} tokens ({2,5}%) {3}" -f $status.Hourly.Used, $status.Hourly.Limit, $status.Hourly.Percent, $(if ($status.Hourly.Percent -gt 80) { "⚠️" } else { "✓" })) -ForegroundColor $(if ($status.Hourly.Percent -gt 80) { "Red" } elseif ($status.Hourly.Percent -gt 60) { "Yellow" } else { "Green" })
Write-Host ("  Daily:   {0,6}/{1,6} tokens ({2,5}%) {3}" -f $status.Daily.Used, $status.Daily.Limit, $status.Daily.Percent, $(if ($status.Daily.Percent -gt 80) { "⚠️" } else { "✓" })) -ForegroundColor $(if ($status.Daily.Percent -gt 80) { "Red" } elseif ($status.Daily.Percent -gt 60) { "Yellow" } else { "Green" })
Write-Host ("  Weekly:  {0,6}/{1,6} tokens ({2,5}%) {3}" -f $status.Weekly.Used, $status.Weekly.Limit, $status.Weekly.Percent, $(if ($status.Weekly.Percent -gt 80) { "⚠️" } else { "✓" })) -ForegroundColor $(if ($status.Weekly.Percent -gt 80) { "Red" } elseif ($status.Weekly.Percent -gt 60) { "Yellow" } else { "Green" })
Write-Host ("  Monthly: {0,6}/{1,6} tokens ({2,5}%) {3}" -f $status.Monthly.Used, $status.Monthly.Limit, $status.Monthly.Percent, $(if ($status.Monthly.Percent -gt 80) { "⚠️" } else { "✓" })) -ForegroundColor $(if ($status.Monthly.Percent -gt 80) { "Red" } elseif ($status.Monthly.Percent -gt 60) { "Yellow" } else { "Green" })
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host ""

# Check if we should proceed
if ($status.Daily.Percent -gt 95) {
    Write-Host "❌ CRITICAL: 95% of daily budget used" -ForegroundColor Red
    Write-Host "Starting Clawdbot now would likely trigger emergency shutdown." -ForegroundColor Red
    Write-Host ""
    if (-not $Force) {
        Write-Host "Use -Force to override (NOT recommended)" -ForegroundColor Yellow
        exit 1
    } else {
        Write-Host "⚠️  Force override enabled - proceeding with caution" -ForegroundColor Yellow
    }
}

if ($status.Daily.Percent -gt 85) {
    Write-Host "⚠️  WARNING: 85% of daily budget used" -ForegroundColor Yellow
    Write-Host "Remaining tokens today: $($status.Daily.Remaining)" -ForegroundColor Yellow
    Write-Host ""
}

# Start token monitor in background
if (-not $SkipMonitor) {
    Write-Host "🔍 Starting token usage monitor..." -ForegroundColor Cyan
    $monitorJob = Start-Job -FilePath $MONITOR_SCRIPT
    Write-Host "   Monitor job ID: $($monitorJob.Id)" -ForegroundColor Gray
    Write-Host ""
}

# Start Clawdbot
Write-Host "🚀 Starting Clawdbot gateway..." -ForegroundColor Green
Write-Host ""

try {
    # Use the wrapper to start
    & $WRAPPER_SCRIPT -Command "gateway" -SubCommand "start" -Force:$Force
    
} catch {
    Write-Host "❌ Failed to start Clawdbot: $($_.Exception.Message)" -ForegroundColor Red
    
    # Stop monitor if it was started
    if ($monitorJob) {
        Stop-Job -Id $monitorJob.Id
        Remove-Job -Id $monitorJob.Id
    }
    
    exit 1
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  STARTUP COMPLETE" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
