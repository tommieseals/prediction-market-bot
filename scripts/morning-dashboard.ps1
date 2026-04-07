<#
.SYNOPSIS
    Complete morning status dashboard - all systems at a glance
.DESCRIPTION
    Shows: Node health, NVIDIA budget, TaskBot status, recent activity
.EXAMPLE
    .\morning-dashboard.ps1           # Full dashboard
    .\morning-dashboard.ps1 -Quick    # Just health, no SSH
#>

param(
    [switch]$Quick
)

$ErrorActionPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Colors
function Write-Section($text) {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor DarkCyan
    Write-Host " $text" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor DarkCyan
}

function Write-OK($text) { Write-Host "  [OK] $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "  [!!] $text" -ForegroundColor Yellow }
function Write-Fail($text) { Write-Host "  [XX] $text" -ForegroundColor Red }
function Write-Info($text) { Write-Host "  [--] $text" -ForegroundColor Gray }

# Header
Clear-Host
Write-Host ""
Write-Host "  +============================================================+" -ForegroundColor Magenta
Write-Host "  |        MORNING DASHBOARD - $(Get-Date -Format 'dddd, MMM d yyyy')          |" -ForegroundColor Magenta
Write-Host "  |                     $(Get-Date -Format 'h:mm tt') CST                          |" -ForegroundColor Magenta
Write-Host "  +============================================================+" -ForegroundColor Magenta

# ============================================================
# SECTION 1: Node Health (Correct IPs as of March 2026)
# ============================================================
Write-Section "NODE STATUS"

$nodes = @(
    @{ name = "Dell (This)"; ip = "localhost"; local = $true },
    @{ name = "Mac Mini"; ip = "100.88.105.106"; user = "tommie" },
    @{ name = "Mac Pro"; ip = "100.89.75.126"; user = "administrator" }
)

foreach ($node in $nodes) {
    Write-Host ""
    
    if ($node.local) {
        # Local Dell check
        $mem = Get-CimInstance Win32_OperatingSystem
        $memUsed = [math]::Round(($mem.TotalVisibleMemorySize - $mem.FreePhysicalMemory) / $mem.TotalVisibleMemorySize * 100)
        $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
        $diskUsed = [math]::Round(($disk.Size - $disk.FreeSpace) / $disk.Size * 100)
        
        Write-Host "  $($node.name.PadRight(15))" -NoNewline -ForegroundColor White
        Write-Host " ONLINE" -ForegroundColor Green
        
        $ramColor = if ($memUsed -gt 85) { "Red" } elseif ($memUsed -gt 75) { "Yellow" } else { "Green" }
        $diskColor = if ($diskUsed -gt 90) { "Red" } elseif ($diskUsed -gt 80) { "Yellow" } else { "Green" }
        
        Write-Host "      RAM: $memUsed%" -ForegroundColor $ramColor -NoNewline
        Write-Host "  |  Disk: $diskUsed%" -ForegroundColor $diskColor
    }
    else {
        # Remote node check via SSH (ping blocked by Mac firewalls)
        $sshResult = ssh -o ConnectTimeout=5 -o BatchMode=yes "$($node.user)@$($node.ip)" "df -h / | tail -1 | awk '{print `$5}'" 2>$null
        
        if ($LASTEXITCODE -eq 0 -and $sshResult) {
            Write-Host "  $($node.name.PadRight(15))" -NoNewline -ForegroundColor White
            Write-Host " ONLINE" -ForegroundColor Green
            
            $diskColor = "Green"
            $diskNum = [int]($sshResult -replace '%','')
            if ($diskNum -gt 90) { $diskColor = "Red" }
            elseif ($diskNum -gt 80) { $diskColor = "Yellow" }
            
            Write-Host "      Disk: $sshResult" -ForegroundColor $diskColor
        }
        else {
            Write-Host "  $($node.name.PadRight(15))" -NoNewline -ForegroundColor White
            Write-Host " OFFLINE" -ForegroundColor Red
        }
    }
}

# ============================================================
# SECTION 2: NVIDIA API Budget
# ============================================================
Write-Section "NVIDIA API BUDGET (50 per day)"

$usageFile = "C:\Users\User\clawd\memory\nvidia-usage.json"
if (Test-Path $usageFile) {
    $usage = Get-Content $usageFile | ConvertFrom-Json
    $today = (Get-Date).ToString("yyyy-MM-dd")
    
    if ($usage.date -eq $today) {
        $used = $usage.count
        $remaining = 50 - $used
        
        $color = if ($remaining -lt 10) { "Red" } elseif ($remaining -lt 20) { "Yellow" } else { "Green" }
        Write-Host "  Used today: $used / 50" -ForegroundColor $color
        Write-Host "  Remaining:  $remaining calls" -ForegroundColor $color
        
        if ($remaining -lt 10) {
            Write-Warn "Running low! Consider using local Ollama for simple tasks"
        }
    }
    else {
        Write-OK "Fresh day! 50 calls available"
    }
}
else {
    Write-Info "Usage tracking not found - creating placeholder"
    $placeholder = @{ date = (Get-Date).ToString("yyyy-MM-dd"); count = 0 }
    $placeholder | ConvertTo-Json | Out-File $usageFile -Encoding UTF8
    Write-OK "Fresh day! 50 calls available"
}

# ============================================================
# SECTION 3: Services Status
# ============================================================
Write-Section "KEY SERVICES"

# Check TaskBot tunnel
$tunnelProcess = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue
if ($tunnelProcess) {
    Write-OK "TaskBot Tunnel: Running (PID: $($tunnelProcess.Id))"
    
    # Try to get current URL
    $urlFile = "C:\Users\User\clawd\memory\taskbot-url.txt"
    if (Test-Path $urlFile) {
        $url = Get-Content $urlFile -Raw
        if ($url) {
            Write-Info "URL: $($url.Trim())"
        }
    }
}
else {
    Write-Warn "TaskBot Tunnel: Not running"
    Write-Info "Start with: .\scripts\taskbot-tunnel.ps1 -Start"
}

# Check Ollama on Mac Mini (quick check)
if (-not $Quick) {
    try {
        $ollamaResponse = Invoke-RestMethod -Uri "http://100.88.105.106:11434/api/tags" -TimeoutSec 3 -ErrorAction Stop
        $modelCount = $ollamaResponse.models.Count
        Write-OK "Mac Mini Ollama: $modelCount models loaded"
    }
    catch {
        Write-Warn "Mac Mini Ollama: Not responding"
    }
}

# ============================================================
# SECTION 4: Recent Activity Summary
# ============================================================
Write-Section "RECENT ACTIVITY"

$memoryDir = "C:\Users\User\clawd\memory"
$today = Get-Date
$recentFiles = @()

# Check last 3 days of memory files
for ($i = 0; $i -le 2; $i++) {
    $date = $today.AddDays(-$i).ToString("yyyy-MM-dd")
    $file = Join-Path $memoryDir "$date.md"
    if (Test-Path $file) {
        $recentFiles += @{
            date = $date
            path = $file
        }
    }
}

if ($recentFiles.Count -gt 0) {
    foreach ($f in $recentFiles) {
        $content = Get-Content $f.path -Raw -ErrorAction SilentlyContinue
        if ($content) {
            # Extract first heading after date
            $match = [regex]::Match($content, "^#.*?-\s*(.+)$", "Multiline")
            if ($match.Success) {
                $dayName = (Get-Date $f.date).ToString("ddd")
                $summary = $match.Groups[1].Value
                if ($summary.Length -gt 45) { $summary = $summary.Substring(0, 45) + "..." }
                Write-Host "  $dayName $($f.date): " -NoNewline -ForegroundColor Gray
                Write-Host $summary -ForegroundColor White
            }
        }
    }
}
else {
    Write-Info "No recent memory files found"
}

# ============================================================
# SECTION 5: Daily Improvements Streak
# ============================================================
Write-Section "DAILY IMPROVEMENT STREAK"

$improvementsFile = "C:\Users\User\clawd\memory\daily-improvements.md"
if (Test-Path $improvementsFile) {
    $content = Get-Content $improvementsFile -Raw
    $dates = [regex]::Matches($content, "## (\d{4}-\d{2}-\d{2})")
    
    if ($dates.Count -gt 0) {
        Write-Host "  Total improvements logged: $($dates.Count)" -ForegroundColor Green
        
        # Show last one
        $lastDate = $dates[$dates.Count - 1].Groups[1].Value
        $daysSince = ((Get-Date) - (Get-Date $lastDate)).Days
        
        if ($daysSince -eq 0) {
            Write-OK "Today's improvement: Already completed!"
        }
        elseif ($daysSince -eq 1) {
            Write-Warn "Yesterday completed - today's improvement: PENDING"
        }
        else {
            Write-Fail "Last improvement was $daysSince days ago - time to build something!"
        }
    }
}
else {
    Write-Info "No improvements log found"
}

# ============================================================
# Footer
# ============================================================
Write-Host ""
Write-Host "----------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Quick commands:" -ForegroundColor Gray
Write-Host "    .\scripts\taskbot-tunnel.ps1 -Monitor  # Watch TaskBot tunnel" -ForegroundColor DarkGray
Write-Host "    .\scripts\check-ram.ps1               # Detailed RAM check" -ForegroundColor DarkGray
Write-Host "    ssh mac-mini                          # Connect to Mac Mini" -ForegroundColor DarkGray
Write-Host ""
