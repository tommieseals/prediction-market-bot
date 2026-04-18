<#
.SYNOPSIS
    Quick Status CLI - Unified system status at a glance
.DESCRIPTION
    Aggregates status from all monitoring scripts into a compact view.
    Shows nodes, disk, RAM, security, services, API usage, trading P&L, and Git status.
.EXAMPLE
    .\quick-status.ps1           # Full quick status
    .\quick-status.ps1 -Minimal  # One-line summary only
    .\quick-status.ps1 -Json     # Output as JSON for other scripts
.NOTES
    Author: Bottom Bitch Bot
    Created: 2026-03-12
#>

param(
    [switch]$Minimal,
    [switch]$Json,
    [switch]$NoColor
)

$ClawdRoot = Join-Path $env:USERPROFILE "clawd"

$ErrorActionPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Write-Status {
    param([string]$Icon, [string]$Label, [string]$Value, [string]$Status = "OK")
    if ($NoColor) {
        Write-Host "$Icon $Label`: $Value"
    } else {
        $color = switch ($Status) {
            "OK"       { "Green" }
            "WARN"     { "Yellow" }
            "CRITICAL" { "Red" }
            "INFO"     { "Cyan" }
            default    { "White" }
        }
        Write-Host "$Icon " -NoNewline
        Write-Host "$Label`: " -NoNewline -ForegroundColor Gray
        Write-Host $Value -ForegroundColor $color
    }
}

$results = @{
    timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    nodes = @{ online = 0; total = 3; details = @() }
    disk = @{ status = "OK"; details = @() }
    ram = @{ status = "OK"; details = @() }
    security = @{ score = "?"; status = "UNKNOWN" }
    services = @{ healthy = 0; total = 0; status = "UNKNOWN" }
    nvidia = @{ used = 0; limit = 50; status = "OK" }
    trading = @{ pnl = 0; positions = 0; status = "UNKNOWN" }
    git = @{ uncommitted = 0; status = "OK" }
}

# === NODE CHECK ===
Write-Host ""
if (-not $Minimal) {
    Write-Host "Checking systems..." -ForegroundColor DarkGray
}

$nodes = @(
    @{ name = "Dell"; ip = "localhost"; critical = $true },
    @{ name = "Mac-Mini"; ip = "100.88.105.106"; user = "tommie"; critical = $true },
    @{ name = "Mac-Pro"; ip = "100.86.80.74"; user = "administrator"; critical = $false }
)

foreach ($node in $nodes) {
    $online = $false
    $diskPct = 0
    $ramPct = 0
    
    if ($node.ip -eq "localhost") {
        $online = $true
        
        $disk = Get-PSDrive C -ErrorAction SilentlyContinue
        if ($disk) {
            $diskPct = [math]::Round(($disk.Used / ($disk.Used + $disk.Free)) * 100)
        }
        
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
        if ($os) {
            $ramPct = [math]::Round((($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize) * 100)
        }
    } else {
        $target = if ($node.user) { "$($node.user)@$($node.ip)" } else { $node.ip }
        $sshResult = ssh -o ConnectTimeout=5 -o BatchMode=yes $target "echo OK" 2>$null
        $online = ($sshResult -eq "OK")
        
        if ($online) {
            $diskInfo = ssh -o ConnectTimeout=5 $target "df -h / | tail -1 | awk '{print `$5}'" 2>$null
            if ($diskInfo -match '(\d+)%') {
                $diskPct = [int]$Matches[1]
            }
            
            $memInfo = ssh -o ConnectTimeout=5 $target "memory_pressure 2>/dev/null | grep 'free percentage' | awk '{print `$NF}' | tr -d '%'" 2>$null
            if ($memInfo -match '\d+') {
                $ramPct = 100 - [int]$memInfo
            }
        }
    }
    
    $results.nodes.details += @{
        name = $node.name
        online = $online
        disk = $diskPct
        ram = $ramPct
        critical = $node.critical
    }
    
    if ($online) { $results.nodes.online++ }
    
    if ($diskPct -gt 90) {
        $results.disk.status = "CRITICAL"
        $results.disk.details += "$($node.name) at $diskPct%"
    } elseif ($diskPct -gt 80 -and $results.disk.status -ne "CRITICAL") {
        $results.disk.status = "WARN"
        $results.disk.details += "$($node.name) at $diskPct%"
    }
    
    if ($ramPct -gt 90) {
        $results.ram.status = "CRITICAL"
        $results.ram.details += "$($node.name) at $ramPct%"
    } elseif ($ramPct -gt 85 -and $results.ram.status -ne "CRITICAL") {
        $results.ram.status = "WARN"
        $results.ram.details += "$($node.name) at $ramPct%"
    }
}

# === SERVICE CHECK ===
$services = @(
    @{ node = "localhost"; name = "Ollama"; check = { (Get-Process ollama -ErrorAction SilentlyContinue) -ne $null } },
    @{ node = "Mac-Mini"; name = "Ollama"; check = { (ssh -o ConnectTimeout=5 tommie@100.88.105.106 "pgrep ollama" 2>$null) -ne $null } },
    @{ node = "Mac-Mini"; name = "Clawdbot"; check = { (ssh -o ConnectTimeout=5 tommie@100.88.105.106 "pgrep -f clawdbot" 2>$null) -ne $null } }
)

$results.services.total = $services.Count
foreach ($svc in $services) {
    try {
        if (& $svc.check) {
            $results.services.healthy++
        }
    } catch {}
}

$results.services.status = if ($results.services.healthy -eq $results.services.total) { "OK" }
                           elseif ($results.services.healthy -gt 0) { "WARN" }
                           else { "CRITICAL" }

# === GIT STATUS ===
$gitStatus = git -C $ClawdRoot status --porcelain 2>$null
if ($gitStatus) {
    $results.git.uncommitted = ($gitStatus | Measure-Object).Count
    $results.git.status = if ($results.git.uncommitted -gt 20) { "WARN" } else { "INFO" }
}

# === NVIDIA API USAGE ===
$nvidiaState = Join-Path $ClawdRoot "memory\\nvidia-usage.json"
if (Test-Path $nvidiaState) {
    $usage = Get-Content $nvidiaState | ConvertFrom-Json -ErrorAction SilentlyContinue
    if ($usage -and $usage.date -eq (Get-Date).ToString("yyyy-MM-dd")) {
        $results.nvidia.used = $usage.count
    }
}
$results.nvidia.status = if ($results.nvidia.used -gt 45) { "CRITICAL" }
                         elseif ($results.nvidia.used -gt 35) { "WARN" }
                         else { "OK" }

# === SECURITY ===
$securityReport = Get-ChildItem (Join-Path $ClawdRoot "memory\security-audit-*.md") -ErrorAction SilentlyContinue | 
                  Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($securityReport) {
    $content = Get-Content $securityReport.FullName -Raw -ErrorAction SilentlyContinue
    if ($content -match 'Grade:\s*([A-F][+-]?)') {
        $results.security.score = $Matches[1]
        $results.security.status = switch -Regex ($Matches[1]) {
            '^A' { "OK" }
            '^B' { "OK" }
            '^C' { "WARN" }
            default { "CRITICAL" }
        }
    }
}

# === TRADING P&L ===
$trackResolved = Join-Path $ClawdRoot "TerminatorBot\track_resolved.py"
if (Test-Path $trackResolved) {
    try {
        $pnlOutput = python $trackResolved 2>$null
        if ($pnlOutput -match 'Total P&L:\s*\$?([-\d.]+)') {
            $results.trading.pnl = [double]$Matches[1]
        }
        if ($pnlOutput -match '(\d+)\s*open positions?') {
            $results.trading.positions = [int]$Matches[1]
        }
        $results.trading.status = if ($results.trading.pnl -ge 0) { "OK" } else { "WARN" }
    } catch {}
}

# === OUTPUT ===
if ($Json) {
    $results | ConvertTo-Json -Depth 4
    exit
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"

if ($Minimal) {
    $nodeStatus = "$($results.nodes.online)/$($results.nodes.total)"
    $svcStatus = "$($results.services.healthy)/$($results.services.total)"
    $alerts = @()
    
    if ($results.nodes.online -lt $results.nodes.total) { $alerts += "nodes" }
    if ($results.disk.status -ne "OK") { $alerts += "disk" }
    if ($results.ram.status -ne "OK") { $alerts += "ram" }
    if ($results.services.status -ne "OK") { $alerts += "services" }
    if ($results.nvidia.used -gt 40) { $alerts += "api" }
    
    $alertStr = if ($alerts.Count -gt 0) { " [!] " + ($alerts -join ",") } else { " [OK]" }
    
    Write-Host "[$timestamp] Nodes:$nodeStatus Svc:$svcStatus Git:$($results.git.uncommitted) API:$($results.nvidia.used)/50$alertStr"
    exit
}

# Full output
Write-Host ""
Write-Host "============================================" -ForegroundColor DarkGray
Write-Host "[QUICK STATUS] " -NoNewline -ForegroundColor Cyan
Write-Host "($timestamp)" -ForegroundColor DarkGray
Write-Host "============================================" -ForegroundColor DarkGray

# Nodes
$nodeIcon = if ($results.nodes.online -eq $results.nodes.total) { "[PC]" } else { "[!!]" }
$nodeStatus = if ($results.nodes.online -eq $results.nodes.total) { "OK" } else { "WARN" }
$nodeDetails = ($results.nodes.details | ForEach-Object { 
    $symbol = if ($_.online) { "+" } else { "X" }
    "$($_.name):$symbol"
}) -join " "
Write-Status $nodeIcon "NODES" "$($results.nodes.online)/$($results.nodes.total) online ($nodeDetails)" $nodeStatus

# Disk
$diskIcon = switch ($results.disk.status) { "OK" { "[HD]" }; "WARN" { "[!!]" }; default { "[XX]" } }
$diskMsg = if ($results.disk.details.Count -gt 0) { $results.disk.details -join ", " } else { "All OK" }
Write-Status $diskIcon "DISK" $diskMsg $results.disk.status

# RAM
$ramIcon = switch ($results.ram.status) { "OK" { "[MEM]" }; "WARN" { "[!!]" }; default { "[XX]" } }
$ramMsg = if ($results.ram.details.Count -gt 0) { $results.ram.details -join ", " } else { "All OK" }
Write-Status $ramIcon "RAM" $ramMsg $results.ram.status

# Services
$svcIcon = switch ($results.services.status) { "OK" { "[SVC]" }; "WARN" { "[!!]" }; default { "[XX]" } }
Write-Status $svcIcon "SERVICES" "$($results.services.healthy)/$($results.services.total) healthy" $results.services.status

# Security
$secIcon = switch ($results.security.status) { "OK" { "[SEC]" }; "WARN" { "[!!]" }; default { "[XX]" } }
Write-Status $secIcon "SECURITY" "Grade: $($results.security.score)" $results.security.status

# NVIDIA API
$apiIcon = switch ($results.nvidia.status) { "OK" { "[API]" }; "WARN" { "[!!]" }; default { "[XX]" } }
$apiPct = [math]::Round(($results.nvidia.used / $results.nvidia.limit) * 100)
Write-Status $apiIcon "NVIDIA API" "$($results.nvidia.used)/$($results.nvidia.limit) used ($apiPct%)" $results.nvidia.status

# Trading
if ($results.trading.status -ne "UNKNOWN") {
    $tradeIcon = if ($results.trading.pnl -ge 0) { "[$$$]" } else { "[---]" }
    $pnlStr = if ($results.trading.pnl -ge 0) { "+$" + $results.trading.pnl } else { "-$" + [math]::Abs($results.trading.pnl) }
    Write-Status $tradeIcon "TRADING" "$pnlStr ($($results.trading.positions) positions)" $results.trading.status
}

# Git
$gitIcon = switch ($results.git.status) { "OK" { "[GIT]" }; "INFO" { "[GIT]" }; default { "[!!]" } }
$gitMsg = if ($results.git.uncommitted -eq 0) { "Clean" } else { "$($results.git.uncommitted) uncommitted" }
Write-Status $gitIcon "GIT" $gitMsg $results.git.status

Write-Host "============================================" -ForegroundColor DarkGray

# Suggestions
$issues = @()
if ($results.nodes.online -lt $results.nodes.total) { $issues += "* Run tailscale-monitor.ps1 to diagnose nodes" }
if ($results.ram.status -ne "OK") { $issues += "* High RAM - check top processes" }
if ($results.disk.status -ne "OK") { $issues += "* High disk - run cleanup" }
if ($results.services.status -ne "OK") { $issues += "* Run service-auto-healer.ps1" }
if ($results.git.uncommitted -gt 20) { $issues += "* Run daily-auto-commit.ps1" }

if ($issues.Count -gt 0) {
    Write-Host ""
    Write-Host "Suggested Actions:" -ForegroundColor Yellow
    $issues | ForEach-Object { Write-Host $_ -ForegroundColor Gray }
}

Write-Host ""
