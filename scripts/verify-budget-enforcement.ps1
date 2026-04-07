# VERIFY BUDGET ENFORCEMENT - Confirm hardcoded limits are active
# Run this to verify the token budget system is properly installed
# Created: 2026-04-07

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  BUDGET ENFORCEMENT VERIFICATION" -ForegroundColor Cyan
Write-Host "  Checking hardcoded token limit system..." -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

$allGood = $true

# Check 1: Enforcement scripts exist
Write-Host "Checking enforcement scripts..." -ForegroundColor Cyan

$requiredScripts = @(
    "C:\Users\USER\clawd\scripts\token-budget-enforcer.ps1",
    "C:\Users\USER\clawd\scripts\clawdbot-budget-wrapper.ps1",
    "C:\Users\USER\clawd\scripts\token-usage-monitor.ps1",
    "C:\Users\USER\clawd\scripts\start-clawdbot-with-budget.ps1",
    "C:\Users\USER\clawd\scripts\check-token-budget.ps1"
)

foreach ($script in $requiredScripts) {
    $scriptName = Split-Path $script -Leaf
    if (Test-Path $script) {
        Write-Host "   OK: $scriptName" -ForegroundColor Green
    } else {
        Write-Host "   MISSING: $scriptName" -ForegroundColor Red
        $allGood = $false
    }
}

Write-Host ""

# Check 2: Genome files exist
Write-Host "Checking genome files..." -ForegroundColor Cyan

$requiredGenome = @(
    "C:\Users\USER\clawd\genome\budget_governance.md",
    "C:\Users\USER\clawd\genome\core_safety.md"
)

foreach ($file in $requiredGenome) {
    $fileName = Split-Path $file -Leaf
    if (Test-Path $file) {
        Write-Host "   OK: $fileName" -ForegroundColor Green
    } else {
        Write-Host "   MISSING: $fileName" -ForegroundColor Red
        $allGood = $false
    }
}

Write-Host ""

# Check 3: Log directory exists
Write-Host "Checking log directory..." -ForegroundColor Cyan

if (Test-Path "C:\Users\USER\clawd\logs") {
    Write-Host "   OK: logs directory exists" -ForegroundColor Green
} else {
    Write-Host "   Creating logs directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "C:\Users\USER\clawd\logs" -Force | Out-Null
    Write-Host "   OK: logs directory created" -ForegroundColor Green
}

Write-Host ""

# Check 4: Test enforcer import
Write-Host "Testing enforcer script..." -ForegroundColor Cyan

try {
    . "C:\Users\USER\clawd\scripts\token-budget-enforcer.ps1"
    Write-Host "   OK: Enforcer script loads" -ForegroundColor Green
    
    # Test the Get-TokenBudgetStatus function
    $status = Get-TokenBudgetStatus
    Write-Host "   OK: Get-TokenBudgetStatus works" -ForegroundColor Green
    
} catch {
    Write-Host "   ERROR: Enforcer failed: $($_.Exception.Message)" -ForegroundColor Red
    $allGood = $false
}

Write-Host ""

# Check 5: Verify hardcoded limits
Write-Host "Verifying hardcoded limits..." -ForegroundColor Cyan

if ($status) {
    $limits = @{
        Daily = 50000
        Hourly = 10000
        Weekly = 200000
        Monthly = 500000
    }
    
    foreach ($key in $limits.Keys) {
        $expected = $limits[$key]
        $actual = $status.$key.Limit
        if ($actual -eq $expected) {
            Write-Host "   OK: $key limit is $expected tokens" -ForegroundColor Green
        } else {
            Write-Host "   ERROR: $key limit should be $expected but is $actual" -ForegroundColor Red
            $allGood = $false
        }
    }
} else {
    Write-Host "   ERROR: Could not verify limits" -ForegroundColor Red
    $allGood = $false
}

Write-Host ""

# Check 6: Emergency flag status
Write-Host "Checking emergency mode..." -ForegroundColor Cyan

if (Test-Path "C:\Users\USER\clawd\.token-emergency") {
    Write-Host "   WARNING: Emergency mode is ACTIVE" -ForegroundColor Red
    Write-Host "   System is currently locked" -ForegroundColor Red
} else {
    Write-Host "   OK: No emergency mode" -ForegroundColor Green
}

Write-Host ""

# Check 7: Current budget status
Write-Host "Current budget status..." -ForegroundColor Cyan

if ($status) {
    $dailyPct = [int]$status.Daily.Percent
    $hourlyPct = [int]$status.Hourly.Percent
    $weeklyPct = [int]$status.Weekly.Percent
    $monthlyPct = [int]$status.Monthly.Percent
    
    Write-Host "   Daily:   $($status.Daily.Used) / $($status.Daily.Limit) tokens ($dailyPct percent)" -ForegroundColor $(if ($dailyPct -gt 80) { "Red" } elseif ($dailyPct -gt 60) { "Yellow" } else { "Green" })
    Write-Host "   Hourly:  $($status.Hourly.Used) / $($status.Hourly.Limit) tokens ($hourlyPct percent)" -ForegroundColor $(if ($hourlyPct -gt 80) { "Red" } elseif ($hourlyPct -gt 60) { "Yellow" } else { "Green" })
    Write-Host "   Weekly:  $($status.Weekly.Used) / $($status.Weekly.Limit) tokens ($weeklyPct percent)" -ForegroundColor $(if ($weeklyPct -gt 80) { "Red" } elseif ($weeklyPct -gt 60) { "Yellow" } else { "Green" })
    Write-Host "   Monthly: $($status.Monthly.Used) / $($status.Monthly.Limit) tokens ($monthlyPct percent)" -ForegroundColor $(if ($monthlyPct -gt 80) { "Red" } elseif ($monthlyPct -gt 60) { "Yellow" } else { "Green" })
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan

# Final verdict
if ($allGood) {
    Write-Host ""
    Write-Host "VERIFICATION PASSED" -ForegroundColor Green
    Write-Host "All budget enforcement systems are operational." -ForegroundColor Green
    Write-Host ""
    Write-Host "To start Clawdbot:" -ForegroundColor Cyan
    Write-Host "  C:\Users\USER\clawd\scripts\start-clawdbot-with-budget.ps1" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To check budget:" -ForegroundColor Cyan
    Write-Host "  C:\Users\USER\clawd\scripts\check-token-budget.ps1" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "VERIFICATION FAILED" -ForegroundColor Red
    Write-Host "Some components are missing or broken." -ForegroundColor Red
    Write-Host "Review the errors above." -ForegroundColor Red
    Write-Host ""
    exit 1
}
