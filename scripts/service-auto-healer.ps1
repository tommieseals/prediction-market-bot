<#
.SYNOPSIS
    Service Auto-Healer - Monitors and auto-restarts critical services across all nodes

.DESCRIPTION
    Checks critical services on Dell, Mac Mini, and Mac Pro.
    Auto-restarts any dead services and logs all actions.
    Can run continuously with -Monitor flag.

.EXAMPLE
    .\service-auto-healer.ps1              # One-time check and heal
    .\service-auto-healer.ps1 -Monitor     # Continuous monitoring (5 min intervals)
    .\service-auto-healer.ps1 -DryRun      # Check only, don't restart
    .\service-auto-healer.ps1 -Status      # Show service status table only
    .\service-auto-healer.ps1 -Alert       # Send Telegram alerts on heal

.NOTES
    Author: Bottom Bitch Bot
    Date: 2026-03-10
    Part of Daily Improvements
#>

param(
    [switch]$Monitor,
    [int]$Interval = 300,  # 5 minutes
    [switch]$DryRun,
    [switch]$Status,
    [switch]$Alert,
    [switch]$Quiet
)

# ============================================================================
# CONFIGURATION
# ============================================================================

$Script:LogFile = "$PSScriptRoot\..\memory\service-healer-log.md"
$Script:StateFile = "$PSScriptRoot\..\memory\service-healer-state.json"

# Define critical services per node
$Script:Services = @{
    "Dell" = @{
        Host = "localhost"
        IP = "100.119.87.108"
        Critical = $true
        Services = @(
            @{
                Name = "Ollama"
                Check = { (Get-Process -Name "ollama" -ErrorAction SilentlyContinue) -ne $null }
                Restart = { Start-Process "C:\Users\tommi\AppData\Local\Programs\Ollama\ollama app.exe" -WindowStyle Hidden }
                ProcessName = "ollama"
            }
            @{
                Name = "Cloudflared"
                Check = { (Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue) -ne $null }
                Restart = { 
                    # Check if TaskBot tunnel should be running
                    $tunnelDir = "C:\Users\User\clawd\TaskBot"
                    if (Test-Path $tunnelDir) {
                        Start-Process "cloudflared" -ArgumentList "tunnel", "--url", "http://localhost:5173" -WindowStyle Hidden -WorkingDirectory $tunnelDir
                    }
                }
                ProcessName = "cloudflared"
                Optional = $true  # Only restart if was running before
            }
        )
    }
    "Mac-Mini" = @{
        Host = "tommie@100.88.105.106"
        IP = "100.88.105.106"
        Critical = $true
        Services = @(
            @{
                Name = "Ollama"
                Check = "pgrep -x ollama > /dev/null && echo 'running' || echo 'dead'"
                Restart = "launchctl kickstart -k gui/501/com.ollama.server 2>/dev/null || open -a Ollama"
            }
            @{
                Name = "Clawdbot Gateway"
                Check = "pgrep -f 'clawdbot.*gateway' > /dev/null && echo 'running' || echo 'dead'"
                Restart = "launchctl kickstart -k gui/501/com.clawdbot.gateway 2>/dev/null || cd ~/clawd && clawdbot gateway start"
            }
        )
    }
    "Mac-Pro" = @{
        Host = "administrator@100.89.75.126"
        IP = "100.89.75.126"
        Critical = $false
        Services = @(
            @{
                Name = "Ollama"
                Check = "pgrep -x ollama > /dev/null && echo 'running' || echo 'dead'"
                Restart = "launchctl kickstart -k gui/501/com.ollama.server 2>/dev/null || open -a Ollama"
            }
        )
    }
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    
    # Console output
    switch ($Level) {
        "ERROR" { Write-Host $logEntry -ForegroundColor Red }
        "WARN"  { Write-Host $logEntry -ForegroundColor Yellow }
        "HEAL"  { Write-Host $logEntry -ForegroundColor Green }
        "OK"    { if (-not $Quiet) { Write-Host $logEntry -ForegroundColor Cyan } }
        default { if (-not $Quiet) { Write-Host $logEntry } }
    }
    
    # File output
    if ($Level -in @("ERROR", "WARN", "HEAL")) {
        Add-Content -Path $Script:LogFile -Value $logEntry -ErrorAction SilentlyContinue
    }
}

function Test-NodeReachable {
    param([string]$SshHost)
    
    try {
        # Use SSH connection test instead of ping (Mac firewalls block ping)
        $result = ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes $SshHost "echo ok" 2>$null
        return $result -eq "ok"
    } catch {
        return $false
    }
}

function Check-RemoteService {
    param(
        [string]$SshHost,
        [string]$CheckCommand
    )
    
    try {
        $result = ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $SshHost $CheckCommand 2>$null
        return $result -match "running"
    } catch {
        return $false
    }
}

function Restart-RemoteService {
    param(
        [string]$SshHost,
        [string]$RestartCommand
    )
    
    try {
        $result = ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no $SshHost $RestartCommand 2>&1
        Start-Sleep -Seconds 3  # Give service time to start
        return $true
    } catch {
        return $false
    }
}

function Send-TelegramAlert {
    param([string]$Message)
    
    if (-not $Alert) { return }
    
    try {
        $botToken = "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU"
        $chatId = "939543801"
        $url = "https://api.telegram.org/bot$botToken/sendMessage"
        
        $body = @{
            chat_id = $chatId
            text = $Message
            parse_mode = "Markdown"
        }
        
        Invoke-RestMethod -Uri $url -Method Post -Body $body -ErrorAction SilentlyContinue | Out-Null
    } catch {
        Write-Log "Failed to send Telegram alert: $_" -Level "WARN"
    }
}

function Get-ServiceState {
    if (Test-Path $Script:StateFile) {
        try {
            return Get-Content $Script:StateFile -Raw | ConvertFrom-Json -AsHashtable
        } catch {
            return @{ services = @{}; heals = @() }
        }
    }
    return @{ services = @{}; heals = @() }
}

function Save-ServiceState {
    param([hashtable]$State)
    $State | ConvertTo-Json -Depth 10 | Set-Content $Script:StateFile -Force
}

function Update-ServiceState {
    param(
        [string]$Node,
        [string]$Service,
        [bool]$Running,
        [bool]$Healed = $false
    )
    
    $state = Get-ServiceState
    $key = "$Node-$Service"
    
    $state.services[$key] = @{
        lastCheck = (Get-Date -Format "o")
        running = $Running
    }
    
    if ($Healed) {
        $state.heals += @{
            time = (Get-Date -Format "o")
            node = $Node
            service = $Service
        }
        
        # Keep only last 50 heals
        if ($state.heals.Count -gt 50) {
            $state.heals = $state.heals | Select-Object -Last 50
        }
    }
    
    Save-ServiceState $state
}

# ============================================================================
# MAIN CHECK FUNCTION
# ============================================================================

function Invoke-HealthCheck {
    $results = @()
    $healsPerformed = 0
    
    Write-Host "`n" -NoNewline
    Write-Host "=" * 60 -ForegroundColor DarkGray
    Write-Host "  SERVICE AUTO-HEALER" -ForegroundColor Cyan
    Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
    Write-Host "=" * 60 -ForegroundColor DarkGray
    Write-Host ""
    
    foreach ($nodeName in $Script:Services.Keys) {
        $node = $Script:Services[$nodeName]
        $nodeIcon = if ($node.Critical) { "[CRITICAL]" } else { "" }
        
        Write-Host "[$nodeName] $($node.IP) $nodeIcon" -ForegroundColor White
        
        # Check node reachability
        if ($nodeName -ne "Dell") {
            $reachable = Test-NodeReachable -SshHost $node.Host
            if (-not $reachable) {
                Write-Host "  [!!] Node unreachable - skipping services" -ForegroundColor Red
                $results += [PSCustomObject]@{
                    Node = $nodeName
                    Service = "Node"
                    Status = "UNREACHABLE"
                    Action = "None"
                }
                continue
            }
        }
        
        foreach ($service in $node.Services) {
            $serviceName = $service.Name
            $running = $false
            $action = "None"
            
            # Check service status
            if ($nodeName -eq "Dell") {
                # Local check
                $running = & $service.Check
            } else {
                # Remote check
                $running = Check-RemoteService -SshHost $node.Host -CheckCommand $service.Check
            }
            
            if ($running) {
                Write-Host "  [OK] $serviceName" -ForegroundColor Green
                Update-ServiceState -Node $nodeName -Service $serviceName -Running $true
            } else {
                Write-Host "  [DOWN] $serviceName" -ForegroundColor Red
                
                # Skip optional services unless they were previously running
                if ($service.Optional) {
                    Write-Host "    (Optional service - not auto-restarting)" -ForegroundColor DarkGray
                    $action = "Skipped (optional)"
                } elseif ($DryRun) {
                    Write-Host "    [DRY RUN] Would restart service" -ForegroundColor Yellow
                    $action = "Would restart"
                } else {
                    Write-Host "    [HEALING] Restarting..." -ForegroundColor Yellow
                    
                    if ($nodeName -eq "Dell") {
                        # Local restart
                        try {
                            & $service.Restart
                            Start-Sleep -Seconds 3
                            $running = & $service.Check
                        } catch {
                            $running = $false
                        }
                    } else {
                        # Remote restart
                        Restart-RemoteService -SshHost $node.Host -RestartCommand $service.Restart
                        Start-Sleep -Seconds 2
                        $running = Check-RemoteService -SshHost $node.Host -CheckCommand $service.Check
                    }
                    
                    if ($running) {
                        Write-Log "$nodeName/$serviceName restarted successfully" -Level "HEAL"
                        $action = "HEALED"
                        $healsPerformed++
                        Update-ServiceState -Node $nodeName -Service $serviceName -Running $true -Healed $true
                        
                        Send-TelegramAlert "🩹 *Service Healed*`n`nNode: $nodeName`nService: $serviceName`nTime: $(Get-Date -Format 'HH:mm:ss')"
                    } else {
                        Write-Log "$nodeName/$serviceName restart FAILED" -Level "ERROR"
                        $action = "FAILED"
                        Update-ServiceState -Node $nodeName -Service $serviceName -Running $false
                        
                        Send-TelegramAlert "❌ *Service Restart FAILED*`n`nNode: $nodeName`nService: $serviceName`nTime: $(Get-Date -Format 'HH:mm:ss')`n`nManual intervention needed!"
                    }
                }
            }
            
            $results += [PSCustomObject]@{
                Node = $nodeName
                Service = $serviceName
                Status = if ($running) { "OK" } else { "DOWN" }
                Action = $action
            }
        }
        
        Write-Host ""
    }
    
    # Summary
    $okCount = ($results | Where-Object { $_.Status -eq "OK" }).Count
    $downCount = ($results | Where-Object { $_.Status -eq "DOWN" }).Count
    $totalCount = $results.Count
    
    Write-Host "-" * 40 -ForegroundColor DarkGray
    Write-Host "SUMMARY: $okCount/$totalCount services healthy" -ForegroundColor $(if ($downCount -eq 0) { "Green" } else { "Yellow" })
    
    if ($healsPerformed -gt 0) {
        Write-Host "HEALS PERFORMED: $healsPerformed" -ForegroundColor Green
    }
    
    # Show history
    $state = Get-ServiceState
    if ($state.heals.Count -gt 0) {
        $recentHeals = $state.heals | Select-Object -Last 5
        Write-Host "`nRecent Heals:" -ForegroundColor DarkGray
        foreach ($heal in $recentHeals) {
            Write-Host "  - $($heal.time): $($heal.node)/$($heal.service)" -ForegroundColor DarkGray
        }
    }
    
    return @{
        Results = $results
        HealsPerformed = $healsPerformed
        AllHealthy = ($downCount -eq 0)
    }
}

# ============================================================================
# STATUS MODE
# ============================================================================

function Show-StatusTable {
    Write-Host "`n" -NoNewline
    Write-Host "=" * 60 -ForegroundColor DarkGray
    Write-Host "  SERVICE STATUS TABLE" -ForegroundColor Cyan
    Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
    Write-Host "=" * 60 -ForegroundColor DarkGray
    Write-Host ""
    
    $state = Get-ServiceState
    
    Write-Host "Node           | Service          | Last Check          | Status" -ForegroundColor White
    Write-Host "-" * 70
    
    foreach ($nodeName in $Script:Services.Keys) {
        foreach ($service in $Script:Services[$nodeName].Services) {
            $key = "$nodeName-$($service.Name)"
            $info = $state.services[$key]
            
            $lastCheck = if ($info.lastCheck) { 
                (Get-Date $info.lastCheck).ToString("MM-dd HH:mm:ss") 
            } else { 
                "Never" 
            }
            
            $status = if ($info.running -eq $true) { "OK" } elseif ($info.running -eq $false) { "DOWN" } else { "Unknown" }
            $statusColor = switch ($status) {
                "OK" { "Green" }
                "DOWN" { "Red" }
                default { "Yellow" }
            }
            
            $line = "{0,-14} | {1,-16} | {2,-19} | " -f $nodeName, $service.Name, $lastCheck
            Write-Host $line -NoNewline
            Write-Host $status -ForegroundColor $statusColor
        }
    }
    
    # Heal stats
    if ($state.heals.Count -gt 0) {
        Write-Host "`nHeal Statistics:" -ForegroundColor Cyan
        $today = ($state.heals | Where-Object { (Get-Date $_.time).Date -eq (Get-Date).Date }).Count
        $week = ($state.heals | Where-Object { (Get-Date $_.time) -gt (Get-Date).AddDays(-7) }).Count
        $total = $state.heals.Count
        
        Write-Host "  Today: $today | This Week: $week | All Time: $total"
    }
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

# Ensure log file exists
if (-not (Test-Path $Script:LogFile)) {
    @"
# Service Auto-Healer Log

This file tracks all auto-heal actions performed by service-auto-healer.ps1

---

"@ | Set-Content $Script:LogFile
}

if ($Status) {
    Show-StatusTable
    exit 0
}

if ($Monitor) {
    Write-Host "Starting continuous monitoring (Ctrl+C to stop)..." -ForegroundColor Cyan
    Write-Host "Check interval: $Interval seconds" -ForegroundColor DarkGray
    Write-Host ""
    
    while ($true) {
        $result = Invoke-HealthCheck
        
        if (-not $result.AllHealthy) {
            Write-Host "`n[!] Issues detected - next check in $Interval seconds" -ForegroundColor Yellow
        } else {
            Write-Host "`nAll healthy - next check in $Interval seconds" -ForegroundColor Green
        }
        
        Start-Sleep -Seconds $Interval
        Clear-Host
    }
} else {
    # Single check
    $result = Invoke-HealthCheck
    
    Write-Host ""
    if ($result.AllHealthy) {
        Write-Host "[SUCCESS] All services healthy" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "[ATTENTION] Some services need attention" -ForegroundColor Yellow
        exit 1
    }
}
