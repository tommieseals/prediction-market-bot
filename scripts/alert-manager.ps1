# Alert Manager - Central incident tracking for all monitoring scripts
# Usage:
#   Fire:     .\alert-manager.ps1 -Fire -Source "Service-Healer" -Severity "critical" -Message "Ollama down"
#   Resolve:  .\alert-manager.ps1 -Resolve -Source "Service-Healer" -Key "ollama-mac-mini"
#   Dashboard: .\alert-manager.ps1 -Dashboard
#   History:  .\alert-manager.ps1 -ShowHistory -Days 7
#   Stats:    .\alert-manager.ps1 -Stats

param(
    [switch]$Fire,
    [switch]$Resolve,
    [switch]$Dashboard,
    [switch]$ShowHistory,
    [switch]$Stats,
    [switch]$Clear,
    
    [string]$Source,
    [string]$Severity = "warning",
    [string]$Message,
    [string]$Key,
    
    [int]$DedupeMinutes = 15,
    [int]$Days = 7,
    [switch]$NoTelegram,
    [switch]$Json
)

$StateFile = "C:\Users\User\clawd\memory\alert-manager-state.json"
$HistFile = "C:\Users\User\clawd\memory\alert-manager-history.json"
$TelegramToken = "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU"
$TelegramChatId = "939543801"

$SeverityConfig = @{
    "critical" = @{ Label = "[!!!]"; Priority = 1; Color = "Red" }
    "warning"  = @{ Label = "[!!]"; Priority = 2; Color = "Yellow" }
    "info"     = @{ Label = "[i]"; Priority = 3; Color = "Cyan" }
}

function Get-AlertState {
    if (Test-Path $StateFile) {
        try {
            return Get-Content $StateFile -Raw | ConvertFrom-Json
        } catch {
            return @{ incidents = @(); lastUpdated = $null }
        }
    }
    return @{ incidents = @(); lastUpdated = $null }
}

function Save-AlertState($state) {
    $state.lastUpdated = (Get-Date).ToString("o")
    $state | ConvertTo-Json -Depth 10 | Set-Content $StateFile -Force
}

function Get-HistData {
    $result = [System.Collections.ArrayList]@()
    if (Test-Path $HistFile) {
        try {
            $content = Get-Content $HistFile -Raw -ErrorAction SilentlyContinue
            if ($content -and $content.Trim() -ne "" -and $content.Trim() -ne "[]") {
                $parsed = $content | ConvertFrom-Json -ErrorAction SilentlyContinue
                if ($parsed) {
                    foreach ($item in $parsed) {
                        [void]$result.Add($item)
                    }
                }
            }
        } catch {}
    }
    return ,$result
}

function Save-HistData($data) {
    if ($data.Count -gt 1000) {
        $data = $data | Select-Object -Last 1000
    }
    $data | ConvertTo-Json -Depth 10 | Set-Content $HistFile -Force
}

function Send-TgAlert($text) {
    if ($NoTelegram) { return }
    try {
        $uri = "https://api.telegram.org/bot$TelegramToken/sendMessage"
        $body = @{
            chat_id = $TelegramChatId
            text = $text
            parse_mode = "HTML"
        }
        Invoke-RestMethod -Uri $uri -Method Post -Body $body -ErrorAction SilentlyContinue | Out-Null
    } catch {}
}

function Get-AlertKey($src, $msg) {
    $combined = "$src-$msg".ToLower()
    $combined = $combined -replace '[^a-z0-9]', '-'
    $combined = $combined -replace '-+', '-'
    return $combined.Substring(0, [Math]::Min(50, $combined.Length))
}

# Fire Alert
if ($Fire) {
    if (-not $Source -or -not $Message) {
        Write-Host "[ERROR] -Fire requires -Source and -Message" -ForegroundColor Red
        exit 1
    }
    
    $state = Get-AlertState
    $histData = Get-HistData
    
    $alertKey = if ($Key) { $Key } else { Get-AlertKey $Source $Message }
    $now = Get-Date
    
    $existing = $state.incidents | Where-Object { $_.key -eq $alertKey }
    if ($existing) {
        $lastFired = [DateTime]::Parse($existing.lastFired)
        $minutesAgo = ($now - $lastFired).TotalMinutes
        
        if ($minutesAgo -lt $DedupeMinutes) {
            $existing.count = $existing.count + 1
            $existing.lastFired = $now.ToString("o")
            Save-AlertState $state
            
            if (-not $Json) {
                Write-Host "[DEDUPE] Alert suppressed (fired $([int]$minutesAgo) min ago, count: $($existing.count))" -ForegroundColor DarkGray
            }
            exit 0
        }
    }
    
    $sev = $Severity.ToLower()
    if (-not $SeverityConfig.ContainsKey($sev)) { $sev = "warning" }
    $label = $SeverityConfig[$sev].Label
    
    $incident = @{
        key = $alertKey
        source = $Source
        severity = $sev
        message = $Message
        firstFired = if ($existing) { $existing.firstFired } else { $now.ToString("o") }
        lastFired = $now.ToString("o")
        count = if ($existing) { $existing.count + 1 } else { 1 }
        status = "open"
    }
    
    if ($existing) {
        $state.incidents = @($state.incidents | Where-Object { $_.key -ne $alertKey }) + $incident
    } else {
        $state.incidents = @($state.incidents) + $incident
    }
    Save-AlertState $state
    
    $histEntry = @{
        timestamp = $now.ToString("o")
        action = "fired"
        key = $alertKey
        source = $Source
        severity = $sev
        message = $Message
    }
    [void]$histData.Add($histEntry)
    Save-HistData $histData
    
    $tgEmoji = switch($sev) { "critical" { "!!!" } "warning" { "!!" } default { "i" } }
    $tgText = "[$tgEmoji] [$($sev.ToUpper())] $Source - $Message"
    if ($incident.count -gt 1) {
        $tgText += " (x$($incident.count))"
    }
    Send-TgAlert $tgText
    
    if ($Json) {
        $incident | ConvertTo-Json
    } else {
        $color = $SeverityConfig[$sev].Color
        Write-Host "$label [$sev] " -ForegroundColor $color -NoNewline
        Write-Host "$($Source): $Message" -ForegroundColor White
    }
    exit 0
}

# Resolve Alert
if ($Resolve) {
    if (-not $Source -and -not $Key) {
        Write-Host "[ERROR] -Resolve requires -Source or -Key" -ForegroundColor Red
        exit 1
    }
    
    $state = Get-AlertState
    $histData = Get-HistData
    $now = Get-Date
    
    $toResolve = @()
    if ($Key) {
        $toResolve = @($state.incidents | Where-Object { $_.key -eq $Key })
    } elseif ($Source) {
        $toResolve = @($state.incidents | Where-Object { $_.source -eq $Source -and $_.status -eq "open" })
    }
    
    if ($toResolve.Count -eq 0) {
        if (-not $Json) {
            Write-Host "[INFO] No matching open incidents to resolve" -ForegroundColor DarkGray
        }
        exit 0
    }
    
    foreach ($inc in $toResolve) {
        $inc | Add-Member -NotePropertyName "status" -NotePropertyValue "resolved" -Force
        $inc | Add-Member -NotePropertyName "resolvedAt" -NotePropertyValue $now.ToString("o") -Force
        
        $firstFired = [DateTime]::Parse($inc.firstFired)
        $duration = $now - $firstFired
        $inc | Add-Member -NotePropertyName "duration" -NotePropertyValue $duration.ToString() -Force
        
        $histEntry = @{
            timestamp = $now.ToString("o")
            action = "resolved"
            key = $inc.key
            source = $inc.source
            severity = $inc.severity
            message = $inc.message
            duration = $duration.ToString()
        }
        [void]$histData.Add($histEntry)
        
        $durationStr = if ($duration.TotalHours -ge 1) {
            "$([int]$duration.TotalHours)h $($duration.Minutes)m"
        } else {
            "$([int]$duration.TotalMinutes)m"
        }
        $tgText = "[OK] [RESOLVED] $($inc.source) - $($inc.message) (duration: $durationStr)"
        Send-TgAlert $tgText
        
        if (-not $Json) {
            Write-Host "[OK] [RESOLVED] $($inc.source): $($inc.message) (duration: $durationStr)" -ForegroundColor Green
        }
    }
    
    $state.incidents = @($state.incidents | Where-Object { $_.status -ne "resolved" })
    Save-AlertState $state
    Save-HistData $histData
    exit 0
}

# Dashboard
if ($Dashboard) {
    $state = Get-AlertState
    
    if ($Json) {
        $state.incidents | ConvertTo-Json -Depth 10
        exit 0
    }
    
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "              ALERT MANAGER DASHBOARD" -ForegroundColor Cyan
    Write-Host "              $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
    
    $openIncidents = @($state.incidents | Where-Object { $_.status -eq "open" })
    
    if ($openIncidents.Count -eq 0) {
        Write-Host "  [OK] No active incidents - all systems nominal" -ForegroundColor Green
        Write-Host ""
    } else {
        $sorted = $openIncidents | Sort-Object { $SeverityConfig[$_.severity].Priority }
        
        Write-Host "  ACTIVE INCIDENTS: $($openIncidents.Count)" -ForegroundColor White
        Write-Host "  ------------------------------------------------------------" -ForegroundColor DarkGray
        
        foreach ($inc in $sorted) {
            $label = $SeverityConfig[$inc.severity].Label
            $color = $SeverityConfig[$inc.severity].Color
            $firstFired = [DateTime]::Parse($inc.firstFired)
            $duration = (Get-Date) - $firstFired
            $durationStr = if ($duration.TotalHours -ge 1) {
                "$([int]$duration.TotalHours)h $($duration.Minutes)m"
            } else {
                "$([int]$duration.TotalMinutes)m"
            }
            
            Write-Host "  $label " -NoNewline
            Write-Host "[$($inc.severity.ToUpper())] " -ForegroundColor $color -NoNewline
            Write-Host "$($inc.source)" -ForegroundColor White
            Write-Host "     $($inc.message)" -ForegroundColor Gray
            Write-Host "     Open for: $durationStr | Occurrences: $($inc.count)" -ForegroundColor DarkGray
            Write-Host ""
        }
    }
    
    $histData = Get-HistData
    $fired = 0
    $resolved = 0
    foreach ($entry in $histData) {
        try {
            if ($entry.timestamp) {
                $ts = [DateTime]::Parse($entry.timestamp)
                if (((Get-Date) - $ts).TotalHours -le 24) {
                    if ($entry.action -eq "fired") { $fired++ }
                    elseif ($entry.action -eq "resolved") { $resolved++ }
                }
            }
        } catch {}
    }
    
    Write-Host "  ------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "  Last 24h: $fired fired, $resolved resolved" -ForegroundColor DarkGray
    Write-Host ""
    exit 0
}

# History
if ($ShowHistory) {
    $histData = Get-HistData
    $cutoff = (Get-Date).AddDays(-$Days)
    $recent = [System.Collections.ArrayList]@()
    foreach ($entry in $histData) {
        try {
            if ($entry.timestamp) {
                $ts = [DateTime]::Parse($entry.timestamp)
                if ($ts -ge $cutoff) {
                    [void]$recent.Add(@{ entry = $entry; ts = $ts })
                }
            }
        } catch {}
    }
    $recent = $recent | Sort-Object { $_.ts } -Descending | ForEach-Object { $_.entry }
    
    if ($Json) {
        $recent | ConvertTo-Json -Depth 10
        exit 0
    }
    
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "              ALERT HISTORY (Last $Days Days)" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
    
    if ($recent.Count -eq 0) {
        Write-Host "  No alerts in the last $Days days" -ForegroundColor Gray
    } else {
        $cnt = 0
        foreach ($entry in $recent) {
            if ($cnt -ge 30) { break }
            $cnt++
            try {
                $ts = [DateTime]::Parse($entry.timestamp)
                $icon = if ($entry.action -eq "fired") { "[FIRE]" } else { "[OK]" }
                $iconColor = if ($entry.action -eq "fired") { "Red" } else { "Green" }
                
                Write-Host "  $icon " -ForegroundColor $iconColor -NoNewline
                Write-Host "$($ts.ToString('MM/dd HH:mm')) " -ForegroundColor DarkGray -NoNewline
                Write-Host "$($entry.source): $($entry.message)" -ForegroundColor Gray
                
                if ($entry.duration) {
                    Write-Host "       Duration: $($entry.duration)" -ForegroundColor DarkGray
                }
            } catch {}
        }
    }
    Write-Host ""
    exit 0
}

# Stats
if ($Stats) {
    $histData = Get-HistData
    $state = Get-AlertState
    
    $openNow = @($state.incidents | Where-Object { $_.status -eq "open" }).Count
    $fired24h = 0
    $resolved24h = 0
    $fired7d = 0
    $resolved7d = 0
    $bySource = @{}
    
    foreach ($entry in $histData) {
        try {
            if (-not $entry.timestamp) { continue }
            $ts = [DateTime]::Parse($entry.timestamp)
            $age = (Get-Date) - $ts
            
            if ($age.TotalHours -le 24) {
                if ($entry.action -eq "fired") {
                    $fired24h++
                    if (-not $bySource.ContainsKey($entry.source)) {
                        $bySource[$entry.source] = 0
                    }
                    $bySource[$entry.source]++
                } else {
                    $resolved24h++
                }
            }
            
            if ($age.TotalDays -le 7) {
                if ($entry.action -eq "fired") { $fired7d++ }
                else { $resolved7d++ }
            }
        } catch {}
    }
    
    if ($Json) {
        @{
            openNow = $openNow
            last24h = @{ fired = $fired24h; resolved = $resolved24h }
            last7d = @{ fired = $fired7d; resolved = $resolved7d }
            bySource = $bySource
        } | ConvertTo-Json -Depth 10
        exit 0
    }
    
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "              ALERT STATISTICS" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Currently Open:    $openNow" -ForegroundColor $(if ($openNow -gt 0) { "Yellow" } else { "Green" })
    Write-Host "  Total All Time:    $($histData.Count)"
    Write-Host ""
    Write-Host "  Last 24 Hours:" -ForegroundColor White
    Write-Host "    Fired:     $fired24h"
    Write-Host "    Resolved:  $resolved24h"
    Write-Host ""
    Write-Host "  Last 7 Days:" -ForegroundColor White
    Write-Host "    Fired:     $fired7d"
    Write-Host "    Resolved:  $resolved7d"
    Write-Host ""
    
    if ($bySource.Count -gt 0) {
        Write-Host "  Top Sources (24h):" -ForegroundColor White
        $bySource.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object {
            Write-Host "    $($_.Key): $($_.Value)"
        }
    }
    Write-Host ""
    exit 0
}

# Clear
if ($Clear) {
    $confirm = Read-Host "Clear all incidents and history? (yes/no)"
    if ($confirm -eq "yes") {
        @{ incidents = @(); lastUpdated = (Get-Date).ToString("o") } | ConvertTo-Json | Set-Content $StateFile
        @() | ConvertTo-Json | Set-Content $HistFile
        Write-Host "[OK] All data cleared" -ForegroundColor Green
    } else {
        Write-Host "Cancelled" -ForegroundColor Gray
    }
    exit 0
}

# Default: Show dashboard
$state = Get-AlertState

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "              ALERT MANAGER DASHBOARD" -ForegroundColor Cyan
Write-Host "              $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$openIncidents = @($state.incidents | Where-Object { $_.status -eq "open" })

if ($openIncidents.Count -eq 0) {
    Write-Host "  [OK] No active incidents - all systems nominal" -ForegroundColor Green
} else {
    Write-Host "  ACTIVE INCIDENTS: $($openIncidents.Count)" -ForegroundColor White
    foreach ($inc in $openIncidents) {
        $label = $SeverityConfig[$inc.severity].Label
        Write-Host "  $label $($inc.source): $($inc.message)" -ForegroundColor $SeverityConfig[$inc.severity].Color
    }
}
Write-Host ""
Write-Host "Usage: -Fire, -Resolve, -Dashboard, -ShowHistory, -Stats" -ForegroundColor DarkGray
Write-Host ""
