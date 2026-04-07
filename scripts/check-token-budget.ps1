# CHECK TOKEN BUDGET - Quick status check
# Display current token usage against hardcoded limits
# Created: 2026-04-07

. "C:\Users\USER\clawd\scripts\token-budget-enforcer.ps1"

$EMERGENCY_FLAG = "C:\Users\USER\clawd\.token-emergency"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  TOKEN BUDGET STATUS" -ForegroundColor Cyan
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check emergency mode
if (Test-Path $EMERGENCY_FLAG) {
    Write-Host "❌ EMERGENCY MODE ACTIVE" -ForegroundColor Red
    Write-Host ""
    Get-Content $EMERGENCY_FLAG
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
    exit 1
}

# Get status
$status = Get-TokenBudgetStatus

# Display status with visual bars
function Get-ProgressBar {
    param([int]$Percent, [int]$Width = 40)
    
    $filled = [math]::Floor(($Percent / 100) * $Width)
    $empty = $Width - $filled
    
    $color = if ($Percent -gt 90) { "Red" }
             elseif ($Percent -gt 80) { "Yellow" }
             elseif ($Percent -gt 60) { "DarkYellow" }
             else { "Green" }
    
    $bar = ("█" * $filled) + ("░" * $empty)
    
    return @{ Bar = $bar; Color = $color }
}

# Hourly
$hourlyBar = Get-ProgressBar -Percent $status.Hourly.Percent
Write-Host "  Hourly Usage:" -ForegroundColor White
Write-Host "  $($hourlyBar.Bar)" -ForegroundColor $hourlyBar.Color
Write-Host ("  {0,6} / {1,6} tokens ({2,5}%)" -f $status.Hourly.Used, $status.Hourly.Limit, $status.Hourly.Percent) -ForegroundColor Gray
Write-Host ""

# Daily
$dailyBar = Get-ProgressBar -Percent $status.Daily.Percent
Write-Host "  Daily Usage:" -ForegroundColor White
Write-Host "  $($dailyBar.Bar)" -ForegroundColor $dailyBar.Color
Write-Host ("  {0,6} / {1,6} tokens ({2,5}%)" -f $status.Daily.Used, $status.Daily.Limit, $status.Daily.Percent) -ForegroundColor Gray
Write-Host ""

# Weekly
$weeklyBar = Get-ProgressBar -Percent $status.Weekly.Percent
Write-Host "  Weekly Usage:" -ForegroundColor White
Write-Host "  $($weeklyBar.Bar)" -ForegroundColor $weeklyBar.Color
Write-Host ("  {0,6} / {1,6} tokens ({2,5}%)" -f $status.Weekly.Used, $status.Weekly.Limit, $status.Weekly.Percent) -ForegroundColor Gray
Write-Host ""

# Monthly
$monthlyBar = Get-ProgressBar -Percent $status.Monthly.Percent
Write-Host "  Monthly Usage:" -ForegroundColor White
Write-Host "  $($monthlyBar.Bar)" -ForegroundColor $monthlyBar.Color
Write-Host ("  {0,6} / {1,6} tokens ({2,5}%)" -f $status.Monthly.Used, $status.Monthly.Limit, $status.Monthly.Percent) -ForegroundColor Gray
Write-Host ""

Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan

# Warnings
if ($status.Daily.Percent -gt 90) {
    Write-Host ""
    Write-Host "🚨 CRITICAL: 90% daily limit reached" -ForegroundColor Red
    Write-Host "   Emergency shutdown at 90% ($($status.Daily.Limit * 0.9) tokens)" -ForegroundColor Red
}
elseif ($status.Daily.Percent -gt 80) {
    Write-Host ""
    Write-Host "⚠️  WARNING: 80% daily limit reached" -ForegroundColor Yellow
}

if ($status.Hourly.Percent -gt 90) {
    Write-Host ""
    Write-Host "⚠️  WARNING: 90% hourly limit reached" -ForegroundColor Yellow
}

Write-Host ""
