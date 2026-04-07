<#
.SYNOPSIS
    Tailscale Network Health Monitor
.DESCRIPTION
    Monitors Tailscale connectivity across all nodes in the infrastructure.
    Tracks uptime, detects outages, and can send Telegram alerts.
.PARAMETER Watch
    Enable continuous monitoring mode
.PARAMETER Interval
    Seconds between checks in watch mode (default: 300)
.PARAMETER Alert
    Send Telegram alerts on status changes
.PARAMETER Quiet
    Only show problems
.EXAMPLE
    .\tailscale-monitor.ps1
    .\tailscale-monitor.ps1 -Watch -Interval 60
    .\tailscale-monitor.ps1 -Alert
#>

param(
    [switch]$Watch,
    [int]$Interval = 300,
    [switch]$Alert,
    [switch]$Quiet
)

$ErrorActionPreference = "SilentlyContinue"

# Node definitions
$Nodes = @{
    "Dell" = @{
        IP = "100.119.87.108"
        SSH = $null
        Role = "Windows Workstation"
        Critical = $true
    }
    "Mac-Mini" = @{
        IP = "100.88.105.106"
        SSH = "tommie@100.88.105.106"
        Role = "Local AI / Ollama"
        Critical = $true
    }
    "Mac-Pro" = @{
        IP = "100.89.75.126"
        SSH = "administrator@100.89.75.126"
        Role = "Heavy AI Workloads"
        Critical = $false
    }
    "Google-Cloud" = @{
        IP = "100.107.231.87"
        SSH = "tommieseals@100.107.231.87"
        Role = "7B Models (Reserved)"
        Critical = $false
    }
}

$StateFile = "C:\Users\User\clawd\memory\tailscale-state.json"

function Get-State {
    if (Test-Path $StateFile) {
        try {
            return Get-Content $StateFile -Raw | ConvertFrom-Json
        } catch {
            # Corrupted file, start fresh
        }
    }
    return @{
        lastCheck = $null
        nodeStatus = @{}
        incidents = @()
        uptimeStart = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    }
}

function Save-State($state) {
    $state | ConvertTo-Json -Depth 5 | Out-File $StateFile -Encoding utf8
}

function Test-TailscaleLocal {
    try {
        $status = tailscale status --json 2>$null | ConvertFrom-Json
        if ($status.Self.Online) {
            return @{
                Online = $true
                IP = $status.Self.TailscaleIPs[0]
                Name = $status.Self.HostName
            }
        }
    } catch {}
    return @{ Online = $false; IP = $null; Name = $null }
}

function Test-NodeConnectivity($node, $info) {
    $result = @{
        Name = $node
        IP = $info.IP
        Role = $info.Role
        Critical = $info.Critical
        Reachable = $false
        SSHWorking = $false
        TailscaleUp = $false
        Latency = $null
    }
    
    $tcpTest = Test-NetConnection -ComputerName $info.IP -Port 22 -WarningAction SilentlyContinue
    $result.Reachable = $tcpTest.TcpTestSucceeded
    if ($tcpTest.PingReplyDetails) {
        $result.Latency = $tcpTest.PingReplyDetails.RoundtripTime
    }
    
    if ($info.SSH) {
        $sshTest = ssh -o ConnectTimeout=5 -o BatchMode=yes $info.SSH "echo OK" 2>$null
        $result.SSHWorking = ($sshTest -eq "OK")
        
        if ($result.SSHWorking) {
            $tsStatus = ssh -o ConnectTimeout=5 $info.SSH "tailscale status --self 2>/dev/null | head -1" 2>$null
            $result.TailscaleUp = ($tsStatus -match $info.IP)
        }
    } else {
        $result.SSHWorking = $true
        $localTs = Test-TailscaleLocal
        $result.TailscaleUp = $localTs.Online
    }
    
    return $result
}

function Send-TelegramAlert($message) {
    if (-not $Alert) { return }
    
    $botToken = $env:TELEGRAM_BOT_TOKEN
    $chatId = "939543801"
    
    if (-not $botToken) {
        Write-Host "[!] TELEGRAM_BOT_TOKEN not set" -ForegroundColor Yellow
        return
    }
    
    try {
        $uri = "https://api.telegram.org/bot$botToken/sendMessage"
        $body = @{
            chat_id = $chatId
            text = $message
            parse_mode = "Markdown"
        }
        Invoke-RestMethod -Uri $uri -Method Post -Body $body | Out-Null
    } catch {
        Write-Host "[!] Alert send failed" -ForegroundColor Yellow
    }
}

function Run-Check {
    param([switch]$IsWatchMode)
    
    $state = Get-State
    $timestamp = Get-Date
    $results = @()
    $problems = @()
    
    if (-not $Quiet) {
        Write-Host ""
        Write-Host "[TAILSCALE NETWORK MONITOR]" -ForegroundColor Cyan
        Write-Host "   $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
        Write-Host ""
    }
    
    $localTs = Test-TailscaleLocal
    if (-not $Quiet) {
        if ($localTs.Online) {
            Write-Host "[OK] Local Tailscale: $($localTs.IP) ($($localTs.Name))" -ForegroundColor Green
        } else {
            Write-Host "[!!] Local Tailscale: OFFLINE" -ForegroundColor Red
            $problems += "Dell Tailscale is offline!"
        }
        Write-Host ""
    }
    
    foreach ($nodeName in $Nodes.Keys) {
        $nodeInfo = $Nodes[$nodeName]
        $result = Test-NodeConnectivity $nodeName $nodeInfo
        $results += $result
        
        $previousStatus = $null
        if ($state.nodeStatus -and $state.nodeStatus.$nodeName) {
            $previousStatus = $state.nodeStatus.$nodeName
        }
        
        $currentOnline = $result.Reachable -and ($result.TailscaleUp -or $result.SSHWorking)
        
        if (-not $state.nodeStatus) {
            $state.nodeStatus = @{}
        }
        
        if ($previousStatus -and $previousStatus.online -ne $currentOnline) {
            $eventType = "DOWN"
            if ($currentOnline) { $eventType = "RECOVERED" }
            
            $incident = @{
                timestamp = $timestamp.ToString("yyyy-MM-dd HH:mm:ss")
                node = $nodeName
                event = $eventType
            }
            
            if (-not $state.incidents) { $state.incidents = @() }
            $incidents = [System.Collections.ArrayList]@($state.incidents)
            $incidents.Add($incident) | Out-Null
            
            if ($incidents.Count -gt 50) {
                $incidents = $incidents[-50..-1]
            }
            $state.incidents = $incidents
            
            if ($nodeInfo.Critical) {
                $status = "OFFLINE"
                if ($currentOnline) { $status = "ONLINE" }
                $msg = "[Alert] *$nodeName* is now *$status*"
                Send-TelegramAlert $msg
            }
        }
        
        $lastSeenVal = $timestamp.ToString("yyyy-MM-dd HH:mm:ss")
        if (-not $currentOnline -and $previousStatus -and $previousStatus.lastSeen) {
            $lastSeenVal = $previousStatus.lastSeen
        }
        
        $state.nodeStatus.$nodeName = @{
            online = $currentOnline
            lastSeen = $lastSeenVal
            lastCheck = $timestamp.ToString("yyyy-MM-dd HH:mm:ss")
        }
        
        if (-not $Quiet -or -not $currentOnline) {
            $statusIcon = "[OK]"
            $statusColor = "Green"
            if (-not $currentOnline) {
                $statusIcon = "[!!]"
                $statusColor = "Red"
            }
            
            $criticalTag = ""
            if ($nodeInfo.Critical) { $criticalTag = " [CRITICAL]" }
            
            Write-Host "$statusIcon $nodeName ($($nodeInfo.IP))$criticalTag" -ForegroundColor $statusColor
            Write-Host "   Role: $($nodeInfo.Role)" -ForegroundColor DarkGray
            
            if ($currentOnline) {
                $latencyStr = "N/A"
                if ($result.Latency) { $latencyStr = "$($result.Latency)ms" }
                
                $sshStr = "FAIL"
                if ($result.SSHWorking) { $sshStr = "OK" }
                
                $tsStr = "DOWN"
                if ($result.TailscaleUp) { $tsStr = "UP" }
                
                Write-Host "   Latency: $latencyStr | SSH: $sshStr | Tailscale: $tsStr" -ForegroundColor DarkGray
            } else {
                Write-Host "   [!] Node unreachable!" -ForegroundColor Yellow
                $problems += "$nodeName is unreachable"
            }
            Write-Host ""
        }
    }
    
    $onlineCount = ($results | Where-Object { $_.Reachable }).Count
    $totalCount = $results.Count
    $criticalDown = $results | Where-Object { $_.Critical -and -not $_.Reachable }
    
    if (-not $Quiet) {
        Write-Host "----------------------------------------" -ForegroundColor DarkGray
        
        $summaryColor = "Green"
        if ($onlineCount -ne $totalCount) { $summaryColor = "Yellow" }
        Write-Host "SUMMARY: $onlineCount/$totalCount nodes online" -ForegroundColor $summaryColor
        
        if ($criticalDown) {
            $downNames = ($criticalDown | ForEach-Object { $_.Name }) -join ", "
            Write-Host "[!!!] CRITICAL NODES DOWN: $downNames" -ForegroundColor Red
        }
        
        if ($state.incidents -and $state.incidents.Count -gt 0) {
            $recentIncidents = $state.incidents | Select-Object -Last 3
            Write-Host ""
            Write-Host "Recent incidents:" -ForegroundColor DarkGray
            foreach ($inc in $recentIncidents) {
                $icon = "[-]"
                if ($inc.event -eq "RECOVERED") { $icon = "[+]" }
                Write-Host "   $icon $($inc.timestamp) - $($inc.node): $($inc.event)" -ForegroundColor DarkGray
            }
        }
    }
    
    $state.lastCheck = $timestamp.ToString("yyyy-MM-dd HH:mm:ss")
    Save-State $state
    
    return @{
        Online = $onlineCount
        Total = $totalCount
        Problems = $problems
        CriticalDown = $criticalDown
    }
}

# Main
if ($Watch) {
    Write-Host "[*] Starting continuous monitoring (every $Interval seconds)" -ForegroundColor Cyan
    Write-Host "   Press Ctrl+C to stop" -ForegroundColor DarkGray
    Write-Host ""
    
    while ($true) {
        Clear-Host
        $result = Run-Check -IsWatchMode
        
        $nextColor = "DarkGray"
        if ($result.CriticalDown) { $nextColor = "Yellow" }
        
        Write-Host ""
        Write-Host "[*] Next check in $Interval seconds..." -ForegroundColor $nextColor
        
        Start-Sleep -Seconds $Interval
    }
} else {
    $result = Run-Check
    
    if ($result.CriticalDown) {
        exit 1
    }
    exit 0
}
