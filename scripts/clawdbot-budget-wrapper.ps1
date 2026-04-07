# CLAWDBOT BUDGET WRAPPER - Enforces token limits before ANY API call
# This wrapper MUST be used to start Clawdbot - direct starts are not allowed
# Created: 2026-04-07 by directive from Rusty

param(
    [string]$Command = "gateway",
    [string]$SubCommand = "start",
    [switch]$Force
)

# Import the enforcer
. "C:\Users\USER\clawd\scripts\token-budget-enforcer.ps1"

$EMERGENCY_FLAG = "C:\Users\USER\clawd\.token-emergency"
$CONFIG_PATH = "$env:USERPROFILE\.clawdbot\clawdbot.json"
$WRAPPER_LOG = "C:\Users\USER\clawd\logs\budget-wrapper.log"

function Write-WrapperLog {
    param([string]$Message)
    $entry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $Message"
    Add-Content -Path $WRAPPER_LOG -Value $entry
    Write-Host $entry
}

# Check for emergency mode
if (Test-Path $EMERGENCY_FLAG) {
    Write-Host "❌ EMERGENCY MODE ACTIVE" -ForegroundColor Red
    Write-Host "Token budget exceeded. Clear emergency flag to resume:" -ForegroundColor Red
    Write-Host "  rm $EMERGENCY_FLAG" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Emergency details:" -ForegroundColor Yellow
    Get-Content $EMERGENCY_FLAG
    exit 1
}

# Get current budget status
$status = Get-TokenBudgetStatus
Write-WrapperLog "Budget check - Daily: $($status.Daily.Used)/$($status.Daily.Limit) ($($status.Daily.Percent)%)"

# Check if we're approaching limits
if ($status.Daily.Percent -gt 90) {
    Write-Host "⚠️  WARNING: 90% of daily token budget used" -ForegroundColor Red
    Write-Host "Daily: $($status.Daily.Used)/$($status.Daily.Limit) tokens" -ForegroundColor Yellow
    
    if (-not $Force) {
        Write-Host "Use -Force to override this warning (not recommended)" -ForegroundColor Yellow
        exit 1
    }
}

if ($status.Daily.Percent -gt 80) {
    Write-Host "⚠️  WARNING: 80% of daily token budget used" -ForegroundColor Yellow
    Write-Host "Daily: $($status.Daily.Used)/$($status.Daily.Limit) tokens" -ForegroundColor Yellow
}

# Display current status
Write-Host "`n📊 Token Budget Status:" -ForegroundColor Cyan
Write-Host "  Hourly:  $($status.Hourly.Used)/$($status.Hourly.Limit) ($($status.Hourly.Percent)%)" -ForegroundColor $(if ($status.Hourly.Percent -gt 80) { "Red" } else { "Green" })
Write-Host "  Daily:   $($status.Daily.Used)/$($status.Daily.Limit) ($($status.Daily.Percent)%)" -ForegroundColor $(if ($status.Daily.Percent -gt 80) { "Red" } else { "Green" })
Write-Host "  Weekly:  $($status.Weekly.Used)/$($status.Weekly.Limit) ($($status.Weekly.Percent)%)" -ForegroundColor $(if ($status.Weekly.Percent -gt 80) { "Red" } else { "Green" })
Write-Host "  Monthly: $($status.Monthly.Used)/$($status.Monthly.Limit) ($($status.Monthly.Percent)%)" -ForegroundColor $(if ($status.Monthly.Percent -gt 80) { "Red" } else { "Green" })
Write-Host ""

# Start Clawdbot with monitoring
Write-WrapperLog "Starting Clawdbot $Command $SubCommand"
Write-Host "🚀 Starting Clawdbot with budget enforcement..." -ForegroundColor Green

try {
    # Start Clawdbot
    $clawdbotCmd = "clawdbot $Command $SubCommand"
    Write-WrapperLog "Executing: $clawdbotCmd"
    
    # Run with budget monitoring
    Invoke-Expression $clawdbotCmd
    
} catch {
    Write-WrapperLog "ERROR: $($_.Exception.Message)"
    Write-Host "❌ Clawdbot failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
