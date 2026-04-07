<#
.SYNOPSIS
    Uptime Tracker & SLA Dashboard - Track node/service uptime over time
    
.DESCRIPTION
    Records uptime data for all nodes and services, tracks historical availability,
    and generates SLA reports (daily, weekly, monthly percentages).
    
.PARAMETER Check
    Run a single uptime check and record results
    
.PARAMETER Dashboard
    Show current uptime dashboard with SLA percentages
    
.PARAMETER Report
    Generate a detailed SLA report (markdown)
    
.PARAMETER Days
    Number of days to include in report (default: 30)

.PARAMETER History
    Show recent check history for a specific target
    
.PARAMETER Target
    Specific target for -History (e.g., "Mac-Mini", "Ollama")
    
.PARAMETER Prune
    Remove data older than N days

.EXAMPLE
    .\uptime-tracker.ps1 -Check              # Run uptime check
    .\uptime-tracker.ps1 -Dashboard          # Show SLA dashboard
    .\uptime-tracker.ps1 -Report -Days 7     # Generate 7-day report
#>

param(
    [switch]$Check,
    [switch]$Dashboard,
    [switch]$Report,
    [int]$Days = 30,
    [switch]$History,
    [string]$Target,
    [int]$Prune = 0
)

$DataFile = "$PSScriptRoot\..\memory\uptime-data.json"
$ReportDir = "$PSScriptRoot\..\memory"

# Define targets using simple hashtables (PSCustomObject causes issues in some contexts)
$nodes = @(
    @{ n = "Mac-Mini"; t = "node"; ip = "100.88.105.106"; crit = $true },
    @{ n = "Mac-Pro"; t = "node"; ip = "100.89.75.126"; crit = $false },
    @{ n = "Dell"; t = "node"; ip = "100.119.87.108"; crit = $true },
    @{ n = "Google-Cloud"; t = "node"; ip = "100.107.231.87"; crit = $false },
    @{ n = "Ollama-Mini"; t = "service"; cmd = "ssh tommie@100.88.105.106 'pgrep -x ollama'" },
    @{ n = "Ollama-Dell"; t = "service"; cmd = "ollama list 2>&1" },
    @{ n = "Clawdbot-Gateway"; t = "service"; cmd = "ssh tommie@100.88.105.106 'pgrep -f clawdbot'" }
)

function Get-SLAGrade($percent) {
    if ($null -eq $percent) { return "N/A" }
    if ($percent -ge 99.9) { return "A+" }
    if ($percent -ge 99.5) { return "A" }
    if ($percent -ge 99.0) { return "A-" }
    if ($percent -ge 98.0) { return "B+" }
    if ($percent -ge 95.0) { return "B" }
    if ($percent -ge 90.0) { return "C" }
    if ($percent -ge 80.0) { return "D" }
    return "F"
}

function Get-PercentColor($percent) {
    if ($null -eq $percent) { return "Gray" }
    if ($percent -ge 99.9) { return "Green" }
    if ($percent -ge 99.0) { return "DarkGreen" }
    if ($percent -ge 95.0) { return "Yellow" }
    if ($percent -ge 90.0) { return "DarkYellow" }
    return "Red"
}

function Get-UptimePercent($checks, $targetName, $hours) {
    $cutoff = (Get-Date).AddHours(-$hours)
    $relevantChecks = @($checks | Where-Object { 
        $_.name -eq $targetName -and [DateTime]$_.timestamp -gt $cutoff 
    })
    if ($relevantChecks.Count -eq 0) { return $null }
    $upCount = @($relevantChecks | Where-Object { $_.up -eq $true }).Count
    return [math]::Round(($upCount / $relevantChecks.Count) * 100, 2)
}

# Run uptime check
if ($Check) {
    Write-Host "`n[UPTIME CHECK] $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
    Write-Host ("=" * 55)
    
    $results = @()
    
    foreach ($node in $nodes) {
        $name = $node.n
        $type = $node.t
        $up = $false
        $latency = $null
        $err = $null
        
        try {
            if ($type -eq "node") {
                $start = Get-Date
                if ($name -eq "Dell") {
                    $up = $true
                    $latency = 0
                } else {
                    $user = if ($name -eq "Mac-Pro") { "administrator" } else { "tommie" }
                    $ip = $node.ip
                    $out = ssh -o ConnectTimeout=5 -o BatchMode=yes "$user@$ip" "echo OK" 2>&1
                    $end = Get-Date
                    if ($out -match "OK") {
                        $up = $true
                        $latency = [int]($end - $start).TotalMilliseconds
                    } else {
                        $err = "SSH failed"
                    }
                }
            } else {
                $start = Get-Date
                $out = Invoke-Expression $node.cmd 2>&1
                $end = Get-Date
                if ($LASTEXITCODE -eq 0 -or $out -match "\d+|NAME") {
                    $up = $true
                    $latency = [int]($end - $start).TotalMilliseconds
                } else {
                    $err = "Not running"
                }
            }
        } catch {
            $err = $_.Exception.Message
        }
        
        $status = if ($up) { "[UP]" } else { "[DOWN]" }
        $color = if ($up) { "Green" } else { "Red" }
        $lat = if ($latency) { " (${latency}ms)" } else { "" }
        
        Write-Host "  $status $name$lat" -ForegroundColor $color
        if ($err) { Write-Host "       $err" -ForegroundColor DarkGray }
        
        $results += @{
            name = $name
            type = $type
            up = $up
            latency = $latency
            error = $err
            timestamp = (Get-Date).ToString("o")
        }
    }
    
    # Load existing data
    $data = @{ checks = @(); metadata = @{ created = (Get-Date).ToString("o") } }
    if (Test-Path $DataFile) {
        try { $data = Get-Content $DataFile -Raw | ConvertFrom-Json } catch {}
    }
    
    # Add new results
    if ($null -eq $data.checks) { $data.checks = @() }
    $data.checks = @($data.checks) + $results
    $data.metadata.lastCheck = (Get-Date).ToString("o")
    $data.metadata.totalChecks = $data.checks.Count
    
    # Save
    $data | ConvertTo-Json -Depth 10 | Set-Content $DataFile -Force
    
    $upCount = ($results | Where-Object { $_.up }).Count
    Write-Host "`n  Summary: $upCount/$($results.Count) targets up" -ForegroundColor Cyan
}

# Show dashboard
if ($Dashboard) {
    $data = @{ checks = @() }
    if (Test-Path $DataFile) {
        try { $data = Get-Content $DataFile -Raw | ConvertFrom-Json } catch {}
    }
    
    if ($null -eq $data.checks -or $data.checks.Count -eq 0) {
        Write-Host "`n  No data yet. Run with -Check first.`n" -ForegroundColor Yellow
        return
    }
    
    Write-Host "`n" 
    Write-Host "  ============================================================" -ForegroundColor Cyan
    Write-Host "              UPTIME & SLA DASHBOARD                          " -ForegroundColor Cyan
    Write-Host "              $(Get-Date -Format 'yyyy-MM-dd HH:mm')                              " -ForegroundColor Cyan
    Write-Host "  ============================================================" -ForegroundColor Cyan
    
    Write-Host "`n  NODES" -ForegroundColor White
    Write-Host "  -------------------------------------------------------------"
    Write-Host "  Target          | Status | 24h    | 7d     | 30d    | Grade" -ForegroundColor Gray
    Write-Host "  -------------------------------------------------------------"
    
    foreach ($node in ($nodes | Where-Object { $_.t -eq "node" })) {
        $name = $node.n
        $lastCheck = $data.checks | Where-Object { $_.name -eq $name } | Select-Object -Last 1
        $status = if ($lastCheck.up) { " UP " } else { "DOWN" }
        $statusColor = if ($lastCheck.up) { "Green" } else { "Red" }
        
        $pct24h = Get-UptimePercent $data.checks $name 24
        $pct7d = Get-UptimePercent $data.checks $name 168
        $pct30d = Get-UptimePercent $data.checks $name 720
        $grade = Get-SLAGrade $pct30d
        
        $pct24hStr = if ($null -ne $pct24h) { "{0,5:N1}%" -f $pct24h } else { "  N/A " }
        $pct7dStr = if ($null -ne $pct7d) { "{0,5:N1}%" -f $pct7d } else { "  N/A " }
        $pct30dStr = if ($null -ne $pct30d) { "{0,5:N1}%" -f $pct30d } else { "  N/A " }
        
        $line = "  {0,-15} | " -f $name
        Write-Host $line -NoNewline
        Write-Host $status -NoNewline -ForegroundColor $statusColor
        Write-Host " | " -NoNewline
        Write-Host $pct24hStr -NoNewline -ForegroundColor (Get-PercentColor $pct24h)
        Write-Host " | " -NoNewline
        Write-Host $pct7dStr -NoNewline -ForegroundColor (Get-PercentColor $pct7d)
        Write-Host " | " -NoNewline
        Write-Host $pct30dStr -NoNewline -ForegroundColor (Get-PercentColor $pct30d)
        Write-Host " | " -NoNewline
        Write-Host $grade -ForegroundColor (Get-PercentColor $pct30d)
    }
    
    Write-Host "`n  SERVICES" -ForegroundColor White
    Write-Host "  -------------------------------------------------------------"
    
    foreach ($node in ($nodes | Where-Object { $_.t -eq "service" })) {
        $name = $node.n
        $lastCheck = $data.checks | Where-Object { $_.name -eq $name } | Select-Object -Last 1
        $status = if ($lastCheck.up) { " UP " } else { "DOWN" }
        $statusColor = if ($lastCheck.up) { "Green" } else { "Red" }
        
        $pct24h = Get-UptimePercent $data.checks $name 24
        $pct7d = Get-UptimePercent $data.checks $name 168
        $pct30d = Get-UptimePercent $data.checks $name 720
        $grade = Get-SLAGrade $pct30d
        
        $pct24hStr = if ($null -ne $pct24h) { "{0,5:N1}%" -f $pct24h } else { "  N/A " }
        $pct7dStr = if ($null -ne $pct7d) { "{0,5:N1}%" -f $pct7d } else { "  N/A " }
        $pct30dStr = if ($null -ne $pct30d) { "{0,5:N1}%" -f $pct30d } else { "  N/A " }
        
        $line = "  {0,-15} | " -f $name
        Write-Host $line -NoNewline
        Write-Host $status -NoNewline -ForegroundColor $statusColor
        Write-Host " | " -NoNewline
        Write-Host $pct24hStr -NoNewline -ForegroundColor (Get-PercentColor $pct24h)
        Write-Host " | " -NoNewline
        Write-Host $pct7dStr -NoNewline -ForegroundColor (Get-PercentColor $pct7d)
        Write-Host " | " -NoNewline
        Write-Host $pct30dStr -NoNewline -ForegroundColor (Get-PercentColor $pct30d)
        Write-Host " | " -NoNewline
        Write-Host $grade -ForegroundColor (Get-PercentColor $pct30d)
    }
    
    # Summary stats
    $totalChecks = $data.checks.Count
    $lastCheckTime = if ($data.metadata.lastCheck) { [DateTime]$data.metadata.lastCheck } else { $null }
    $dataSpan = if ($data.checks.Count -gt 1) {
        $first = [DateTime]($data.checks[0].timestamp)
        $last = [DateTime]($data.checks[-1].timestamp)
        ($last - $first).TotalHours
    } else { 0 }
    
    Write-Host "`n  -------------------------------------------------------------"
    Write-Host "  Total checks: $totalChecks | Data span: $([math]::Round($dataSpan, 1)) hours" -ForegroundColor DarkGray
    if ($lastCheckTime) {
        Write-Host "  Last check: $($lastCheckTime.ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor DarkGray
    }
    Write-Host ""
}

# Generate report
if ($Report) {
    $data = @{ checks = @() }
    if (Test-Path $DataFile) {
        try { $data = Get-Content $DataFile -Raw | ConvertFrom-Json } catch {}
    }
    
    $reportDate = Get-Date -Format "yyyy-MM-dd"
    $reportFile = "$ReportDir\sla-report-$reportDate.md"
    
    $reportLines = @()
    $reportLines += "# SLA Report - $reportDate"
    $reportLines += ""
    $reportLines += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $reportLines += "Period: Last $Days days"
    $reportLines += ""
    $reportLines += "## Summary"
    $reportLines += ""
    $reportLines += "| Target | Type | 24h | 7d | 30d | Grade |"
    $reportLines += "|--------|------|-----|-----|-----|-------|"

    foreach ($node in $nodes) {
        $name = $node.n
        $type = $node.t
        $pct24h = Get-UptimePercent $data.checks $name 24
        $pct7d = Get-UptimePercent $data.checks $name 168
        $pct30d = Get-UptimePercent $data.checks $name 720
        $grade = Get-SLAGrade $pct30d
        
        $pct24hStr = if ($null -ne $pct24h) { "{0:N2}%" -f $pct24h } else { "N/A" }
        $pct7dStr = if ($null -ne $pct7d) { "{0:N2}%" -f $pct7d } else { "N/A" }
        $pct30dStr = if ($null -ne $pct30d) { "{0:N2}%" -f $pct30d } else { "N/A" }
        
        $reportLines += "| $name | $type | $pct24hStr | $pct7dStr | $pct30dStr | $grade |"
    }
    
    # Incident analysis
    $reportLines += ""
    $reportLines += "## Incidents (Last $Days Days)"
    $reportLines += ""
    
    $cutoff = (Get-Date).AddDays(-$Days)
    $incidents = @()
    $lastState = @{}
    
    foreach ($check in ($data.checks | Sort-Object { [DateTime]$_.timestamp })) {
        if ([DateTime]$check.timestamp -lt $cutoff) { continue }
        
        $prevUp = $lastState[$check.name]
        if ($null -ne $prevUp -and $prevUp -and -not $check.up) {
            $incidents += @{
                target = $check.name
                time = $check.timestamp
                type = "down"
                error = $check.error
            }
        } elseif ($null -ne $prevUp -and -not $prevUp -and $check.up) {
            $incidents += @{
                target = $check.name
                time = $check.timestamp
                type = "recovered"
            }
        }
        $lastState[$check.name] = $check.up
    }
    
    if ($incidents.Count -eq 0) {
        $reportLines += "No incidents recorded in this period."
    } else {
        $reportLines += "| Time | Target | Event | Details |"
        $reportLines += "|------|--------|-------|---------|"
        foreach ($incident in $incidents) {
            $emoji = if ($incident.type -eq "down") { "[DOWN]" } else { "[UP]" }
            $details = if ($incident.error) { $incident.error } else { "-" }
            $reportLines += "| $($incident.time) | $($incident.target) | $emoji | $details |"
        }
    }
    
    $reportLines += ""
    $reportLines += "## Statistics"
    $reportLines += ""
    $reportLines += "- **Total checks recorded:** $($data.checks.Count)"
    $reportLines += "- **Report generated:** $(Get-Date -Format 'o')"
    $reportLines += ""
    $reportLines += "---"
    $reportLines += "*Generated by uptime-tracker.ps1*"

    $report = $reportLines -join "`n"
    $report | Set-Content $reportFile -Force
    Write-Host "`n[REPORT] Generated: $reportFile" -ForegroundColor Green
    Write-Host $report
}

# Show history for a target
if ($History) {
    if (-not $Target) {
        Write-Host "`n[ERROR] Specify -Target (e.g., -Target 'Mac-Mini')" -ForegroundColor Red
        return
    }
    
    $data = @{ checks = @() }
    if (Test-Path $DataFile) {
        try { $data = Get-Content $DataFile -Raw | ConvertFrom-Json } catch {}
    }
    
    $targetChecks = @($data.checks | Where-Object { $_.name -eq $Target } | Select-Object -Last 50)
    
    if ($targetChecks.Count -eq 0) {
        Write-Host "`n[HISTORY] No data for '$Target'" -ForegroundColor Yellow
        return
    }
    
    Write-Host "`n[HISTORY] $Target - Last $($targetChecks.Count) checks" -ForegroundColor Cyan
    Write-Host ("-" * 60)
    
    foreach ($check in $targetChecks) {
        $time = ([DateTime]$check.timestamp).ToString("MM-dd HH:mm")
        $status = if ($check.up) { "UP  " } else { "DOWN" }
        $color = if ($check.up) { "Green" } else { "Red" }
        $latency = if ($check.latency) { "$($check.latency)ms" } else { "-" }
        
        Write-Host "  $time | " -NoNewline
        Write-Host $status -NoNewline -ForegroundColor $color
        Write-Host " | $latency"
    }
}

# Prune old data
if ($Prune -gt 0) {
    $data = @{ checks = @() }
    if (Test-Path $DataFile) {
        try { $data = Get-Content $DataFile -Raw | ConvertFrom-Json } catch {}
    }
    
    $cutoff = (Get-Date).AddDays(-$Prune)
    $before = $data.checks.Count
    
    $data.checks = @($data.checks | Where-Object { [DateTime]$_.timestamp -gt $cutoff })
    $after = $data.checks.Count
    
    $data | ConvertTo-Json -Depth 10 | Set-Content $DataFile -Force
    Write-Host "`n[PRUNE] Removed $($before - $after) checks older than $Prune days" -ForegroundColor Green
}

# Default: show help
if (-not ($Check -or $Dashboard -or $Report -or $History -or $Prune)) {
    Write-Host @"

  UPTIME TRACKER & SLA DASHBOARD
  ============================================================
  
  Track node and service uptime over time, generate SLA reports.
  
  USAGE:
    .\uptime-tracker.ps1 -Check              # Run uptime check
    .\uptime-tracker.ps1 -Dashboard          # Show SLA dashboard
    .\uptime-tracker.ps1 -Report -Days 7     # Generate 7-day report
    .\uptime-tracker.ps1 -History -Target "Mac-Mini"  # Check history
    .\uptime-tracker.ps1 -Prune 90           # Remove data > 90 days

  MONITORED TARGETS:
    Nodes:    Mac-Mini, Mac-Pro, Dell, Google-Cloud
    Services: Ollama (Mini/Dell), Clawdbot-Gateway

  DATA:
    Stored in: memory\uptime-data.json
    Reports:   memory\sla-report-YYYY-MM-DD.md

"@ -ForegroundColor Cyan
}
