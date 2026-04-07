# TOKEN BUDGET ENFORCER - HARDCODED LIMITS
# This script enforces ABSOLUTE token limits that CANNOT be bypassed
# Created: 2026-04-07 by directive from Rusty

# HARDCODED LIMITS - DO NOT MODIFY WITHOUT EXPLICIT APPROVAL
$HARD_LIMITS = @{
    DailyTokenLimit = 50000        # Hard daily limit
    HourlyTokenLimit = 10000       # Hard hourly limit  
    WeeklyTokenLimit = 200000      # Hard weekly limit
    MonthlyTokenLimit = 500000     # Hard monthly limit
    EmergencyShutdownAt = 45000    # Emergency shutdown threshold (90% of daily)
}

$LOG_PATH = "C:\Users\USER\clawd\logs\token-usage.jsonl"
$ALERT_SCRIPT = "C:\Users\USER\clawd\scripts\forward-to-telegram.ps1"
$EMERGENCY_FLAG = "C:\Users\USER\clawd\.token-emergency"

function Get-TokenUsage {
    param([int]$Hours = 24)
    
    if (-not (Test-Path $LOG_PATH)) {
        return @{ Total = 0; Count = 0 }
    }
    
    $cutoff = (Get-Date).AddHours(-$Hours)
    $usage = Get-Content $LOG_PATH | 
        ForEach-Object { $_ | ConvertFrom-Json } |
        Where-Object { [DateTime]$_.timestamp -gt $cutoff } |
        Measure-Object -Property tokens -Sum
    
    return @{
        Total = [int]$usage.Sum
        Count = $usage.Count
    }
}

function Log-TokenUsage {
    param(
        [int]$Tokens,
        [string]$Model,
        [string]$Purpose
    )
    
    $entry = @{
        timestamp = (Get-Date).ToString("o")
        tokens = $Tokens
        model = $Model
        purpose = $Purpose
        host = $env:COMPUTERNAME
    } | ConvertTo-Json -Compress
    
    Add-Content -Path $LOG_PATH -Value $entry
}

function Send-Alert {
    param([string]$Message)
    
    if (Test-Path $ALERT_SCRIPT) {
        & $ALERT_SCRIPT -Message "🚨 TOKEN ALERT: $Message"
    }
}

function Invoke-EmergencyShutdown {
    param([string]$Reason)
    
    # Create emergency flag
    Set-Content -Path $EMERGENCY_FLAG -Value @"
EMERGENCY SHUTDOWN TRIGGERED
Timestamp: $(Get-Date -Format "o")
Reason: $Reason
DO NOT RESTART WITHOUT AUTHORIZATION
"@
    
    Send-Alert "EMERGENCY SHUTDOWN: $Reason"
    
    # Kill all Clawdbot processes
    Get-Process -Name "node" -ErrorAction SilentlyContinue | 
        Where-Object { $_.CommandLine -like "*clawdbot*" } | 
        Stop-Process -Force
    
    Write-Host "EMERGENCY SHUTDOWN COMPLETE" -ForegroundColor Red
    exit 1
}

function Test-TokenBudget {
    param(
        [int]$RequestedTokens,
        [string]$Model = "claude",
        [string]$Purpose = "unknown"
    )
    
    # Check for emergency flag
    if (Test-Path $EMERGENCY_FLAG) {
        throw "Token budget enforcer in EMERGENCY mode. Clear $EMERGENCY_FLAG to resume."
    }
    
    # Get current usage
    $hourly = Get-TokenUsage -Hours 1
    $daily = Get-TokenUsage -Hours 24
    $weekly = Get-TokenUsage -Hours 168
    $monthly = Get-TokenUsage -Hours 720
    
    # HARDCODED CHECKS - CANNOT BE BYPASSED
    
    # Check emergency shutdown threshold
    if ($daily.Total -ge $HARD_LIMITS.EmergencyShutdownAt) {
        Invoke-EmergencyShutdown "Daily token limit reached: $($daily.Total)/$($HARD_LIMITS.DailyTokenLimit)"
    }
    
    # Check if request would exceed daily limit
    if (($daily.Total + $RequestedTokens) -gt $HARD_LIMITS.DailyTokenLimit) {
        Invoke-EmergencyShutdown "Request would exceed daily limit: $($daily.Total + $RequestedTokens)/$($HARD_LIMITS.DailyTokenLimit)"
    }
    
    # Check hourly limit
    if (($hourly.Total + $RequestedTokens) -gt $HARD_LIMITS.HourlyTokenLimit) {
        Send-Alert "Hourly limit would be exceeded: $($hourly.Total + $RequestedTokens)/$($HARD_LIMITS.HourlyTokenLimit)"
        throw "Hourly token limit would be exceeded"
    }
    
    # Check weekly limit
    if (($weekly.Total + $RequestedTokens) -gt $HARD_LIMITS.WeeklyTokenLimit) {
        Send-Alert "Weekly limit would be exceeded: $($weekly.Total + $RequestedTokens)/$($HARD_LIMITS.WeeklyTokenLimit)"
        throw "Weekly token limit would be exceeded"
    }
    
    # Check monthly limit
    if (($monthly.Total + $RequestedTokens) -gt $HARD_LIMITS.MonthlyTokenLimit) {
        Invoke-EmergencyShutdown "Monthly limit would be exceeded: $($monthly.Total + $RequestedTokens)/$($HARD_LIMITS.MonthlyTokenLimit)"
    }
    
    # Warning thresholds (80%)
    if ($daily.Total -gt ($HARD_LIMITS.DailyTokenLimit * 0.8)) {
        Send-Alert "⚠️ 80% daily limit reached: $($daily.Total)/$($HARD_LIMITS.DailyTokenLimit)"
    }
    
    # Log the usage
    Log-TokenUsage -Tokens $RequestedTokens -Model $Model -Purpose $Purpose
    
    return $true
}

function Get-TokenBudgetStatus {
    $hourly = Get-TokenUsage -Hours 1
    $daily = Get-TokenUsage -Hours 24
    $weekly = Get-TokenUsage -Hours 168
    $monthly = Get-TokenUsage -Hours 720
    
    return @{
        Hourly = @{
            Used = $hourly.Total
            Limit = $HARD_LIMITS.HourlyTokenLimit
            Remaining = $HARD_LIMITS.HourlyTokenLimit - $hourly.Total
            Percent = [math]::Round(($hourly.Total / $HARD_LIMITS.HourlyTokenLimit) * 100, 1)
        }
        Daily = @{
            Used = $daily.Total
            Limit = $HARD_LIMITS.DailyTokenLimit
            Remaining = $HARD_LIMITS.DailyTokenLimit - $daily.Total
            Percent = [math]::Round(($daily.Total / $HARD_LIMITS.DailyTokenLimit) * 100, 1)
        }
        Weekly = @{
            Used = $weekly.Total
            Limit = $HARD_LIMITS.WeeklyTokenLimit
            Remaining = $HARD_LIMITS.WeeklyTokenLimit - $weekly.Total
            Percent = [math]::Round(($weekly.Total / $HARD_LIMITS.WeeklyTokenLimit) * 100, 1)
        }
        Monthly = @{
            Used = $monthly.Total
            Limit = $HARD_LIMITS.MonthlyTokenLimit
            Remaining = $HARD_LIMITS.MonthlyTokenLimit - $monthly.Total
            Percent = [math]::Round(($monthly.Total / $HARD_LIMITS.MonthlyTokenLimit) * 100, 1)
        }
        EmergencyMode = Test-Path $EMERGENCY_FLAG
    }
}

# Functions are available when dot-sourced
# No Export-ModuleMember needed for dot-sourcing
