<#
.SYNOPSIS
    Weekly Progress Report Generator - Compile accomplishments across all systems
.DESCRIPTION
    Scans memory files, git commits, and project status to generate a comprehensive
    weekly progress report. Shows what got DONE, not just what was worked on.
.EXAMPLE
    .\weekly-progress-report.ps1                    # Full report for last 7 days
    .\weekly-progress-report.ps1 -Days 14           # Last 14 days
    .\weekly-progress-report.ps1 -Output "weekly-report.md"  # Save to file
    .\weekly-progress-report.ps1 -Telegram          # Send summary to Telegram
#>

param(
    [int]$Days = 7,
    [string]$Output,
    [switch]$Telegram,
    [switch]$Quiet
)

$ErrorActionPreference = "SilentlyContinue"
$ClaWdRoot = "C:\Users\User\clawd"
$StartDate = (Get-Date).AddDays(-$Days)

# Colors
function Write-Header { param($text) Write-Host "`n$text" -ForegroundColor Cyan }
function Write-Item { param($text) Write-Host "  $text" -ForegroundColor White }
function Write-Stat { param($label, $value) Write-Host "  $label`: " -NoNewline -ForegroundColor Gray; Write-Host $value -ForegroundColor Yellow }

$report = @()
$report += "# Weekly Progress Report"
$report += "**Period:** $(($StartDate).ToString('MMM dd')) - $((Get-Date).ToString('MMM dd, yyyy'))"
$report += "**Generated:** $((Get-Date).ToString('yyyy-MM-dd HH:mm'))"
$report += ""

# ===================================================================
# 1. DAILY IMPROVEMENTS
# ===================================================================
if (-not $Quiet) { Write-Header "[IMPROVEMENTS] DAILY IMPROVEMENTS" }
$report += "## Daily Improvements"
$report += ""

$improvementsFile = Join-Path $ClaWdRoot "memory\daily-improvements.md"
$improvementCount = 0
$improvementList = @()

if (Test-Path $improvementsFile) {
    $content = Get-Content $improvementsFile -Raw
    # Extract improvements with dates
    $datePattern = '## (\d{4}-\d{2}-\d{2}) \((\w+)\) - (.+)'
    $matches = [regex]::Matches($content, $datePattern)
    
    foreach ($match in $matches) {
        $date = [DateTime]::Parse($match.Groups[1].Value)
        if ($date -ge $StartDate) {
            $day = $match.Groups[2].Value
            $title = $match.Groups[3].Value
            $improvementCount++
            $improvementList += "- **$($date.ToString('MMM dd'))** ($day): $title"
            if (-not $Quiet) { Write-Item "[$($date.ToString('MM/dd'))] $title" }
        }
    }
}

if ($improvementCount -gt 0) {
    $report += $improvementList
    $report += ""
    $report += "**Total:** $improvementCount improvements this week!"
} else {
    $report += "_No daily improvements logged this period_"
}
$report += ""

# ===================================================================
# 2. GIT ACTIVITY
# ===================================================================
if (-not $Quiet) { Write-Header "[GIT] GIT COMMITS" }
$report += "## Git Activity"
$report += ""

$projectDirs = @(
    @{ Path = $ClaWdRoot; Name = "clawd" },
    @{ Path = "C:\Users\tommi\Projects\TaskBot"; Name = "TaskBot" },
    @{ Path = "C:\Users\tommi\Projects\TerminatorBot"; Name = "TerminatorBot" }
)

$totalCommits = 0
$commitsByProject = @{}

foreach ($proj in $projectDirs) {
    if (Test-Path (Join-Path $proj.Path ".git")) {
        Push-Location $proj.Path
        $commits = git log --since="$($StartDate.ToString('yyyy-MM-dd'))" --oneline 2>$null
        if ($commits) {
            $count = ($commits | Measure-Object).Count
            $totalCommits += $count
            $commitsByProject[$proj.Name] = @{
                Count = $count
                Recent = ($commits | Select-Object -First 3)
            }
            if (-not $Quiet) { 
                Write-Item "$($proj.Name): $count commits"
            }
        }
        Pop-Location
    }
}

foreach ($projName in $commitsByProject.Keys) {
    $data = $commitsByProject[$projName]
    $commitCountStr = $data.Count
    $report += "### $projName ($commitCountStr commits)"
    foreach ($commit in $data.Recent) {
        $report += "- $commit"
    }
    $remaining = $data.Count - 3
    if ($remaining -gt 0) {
        $report += "- _...and $remaining more_"
    }
    $report += ""
}

if ($totalCommits -eq 0) {
    $report += "_No git commits this period_"
}
$report += ""

# ===================================================================
# 3. MEMORY ACTIVITY
# ===================================================================
if (-not $Quiet) { Write-Header "[MEMORY] MEMORY FILES" }
$report += "## Memory and Documentation"
$report += ""

$memoryDir = Join-Path $ClaWdRoot "memory"
$recentMemory = @()

if (Test-Path $memoryDir) {
    $memoryFiles = Get-ChildItem $memoryDir -Filter "*.md" | 
        Where-Object { $_.LastWriteTime -ge $StartDate } |
        Sort-Object LastWriteTime -Descending
    
    foreach ($file in $memoryFiles | Select-Object -First 10) {
        $recentMemory += "- **$($file.Name)** (updated $($file.LastWriteTime.ToString('MMM dd')))"
        if (-not $Quiet) { Write-Item "$($file.Name) - $($file.LastWriteTime.ToString('MM/dd HH:mm'))" }
    }
}

if ($recentMemory.Count -gt 0) {
    $report += $recentMemory
} else {
    $report += "_No memory files updated this period_"
}
$report += ""

# ===================================================================
# 4. SCRIPTS CREATED/MODIFIED
# ===================================================================
if (-not $Quiet) { Write-Header "[SCRIPTS] SCRIPTS" }
$report += "## Scripts Created/Modified"
$report += ""

$scriptsDir = Join-Path $ClaWdRoot "scripts"
$recentScripts = @()

if (Test-Path $scriptsDir) {
    $scriptFiles = Get-ChildItem $scriptsDir -Include "*.ps1","*.sh","*.py" -Recurse | 
        Where-Object { $_.LastWriteTime -ge $StartDate } |
        Sort-Object LastWriteTime -Descending
    
    foreach ($file in $scriptFiles | Select-Object -First 10) {
        $size = "{0:N1} KB" -f ($file.Length / 1KB)
        $recentScripts += "- **$($file.Name)** ($size, $($file.LastWriteTime.ToString('MMM dd')))"
        if (-not $Quiet) { Write-Item "$($file.Name) - $size" }
    }
}

if ($recentScripts.Count -gt 0) {
    $report += $recentScripts
} else {
    $report += "_No scripts modified this period_"
}
$report += ""

# ===================================================================
# 5. INFRASTRUCTURE STATUS
# ===================================================================
if (-not $Quiet) { Write-Header "[INFRA] INFRASTRUCTURE" }
$report += "## Infrastructure Status (Current)"
$report += ""

# Dell (local)
$dellMem = Get-CimInstance Win32_OperatingSystem
$dellRamUsed = [math]::Round((($dellMem.TotalVisibleMemorySize - $dellMem.FreePhysicalMemory) / $dellMem.TotalVisibleMemorySize) * 100)
$dellDisk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$dellDiskUsed = [math]::Round((($dellDisk.Size - $dellDisk.FreeSpace) / $dellDisk.Size) * 100)

$report += "| Node | RAM | Disk | Status |"
$report += "|------|-----|------|--------|"
$report += "| Dell (local) | $dellRamUsed% | $dellDiskUsed% | OK |"

if (-not $Quiet) { 
    Write-Stat "Dell RAM" "$dellRamUsed%"
    Write-Stat "Dell Disk" "$dellDiskUsed%"
}

# Try Mac nodes via SSH (quick check)
$macMiniStatus = "Unknown"
$macProStatus = "Unknown"

$macMiniTest = ssh -o ConnectTimeout=3 -o BatchMode=yes tommie@100.88.105.106 "echo OK" 2>$null
if ($macMiniTest -eq "OK") { $macMiniStatus = "OK" }

$macProTest = ssh -o ConnectTimeout=3 -o BatchMode=yes administrator@100.101.89.80 "echo OK" 2>$null
if ($macProTest -eq "OK") { $macProStatus = "OK" }

$report += "| Mac Mini | - | - | $macMiniStatus |"
$report += "| Mac Pro | - | - | $macProStatus |"
$report += ""

# ===================================================================
# 6. SUMMARY STATS
# ===================================================================
$report += "## Summary"
$report += ""
$report += "| Metric | Count |"
$report += "|--------|-------|"
$report += "| Daily Improvements | $improvementCount |"
$report += "| Git Commits | $totalCommits |"
$report += "| Memory Files Updated | $($recentMemory.Count) |"
$report += "| Scripts Modified | $($recentScripts.Count) |"
$report += ""

# Streak calculation
$streakDays = 0
$checkDate = Get-Date
while ($true) {
    $dateStr = $checkDate.ToString('yyyy-MM-dd')
    if ($improvementList -match $dateStr) {
        $streakDays++
        $checkDate = $checkDate.AddDays(-1)
    } else {
        break
    }
}

if ($streakDays -gt 0) {
    $report += "**Current improvement streak:** $streakDays days!"
}
$report += ""
$report += "---"
$report += "_Generated by weekly-progress-report.ps1_"

# ===================================================================
# OUTPUT
# ===================================================================
$reportText = $report -join "`n"

if ($Output) {
    $reportText | Out-File -FilePath $Output -Encoding UTF8
    Write-Host "`n[OK] Report saved to: $Output" -ForegroundColor Green
}

if ($Telegram) {
    # Create a shorter summary for Telegram
    $telegramMsg = @"
Weekly Progress Report
$($StartDate.ToString('MMM dd')) - $((Get-Date).ToString('MMM dd'))

Improvements: $improvementCount
Git Commits: $totalCommits
Docs Updated: $($recentMemory.Count)
Scripts Modified: $($recentScripts.Count)

Infrastructure:
Dell: RAM $dellRamUsed% | Disk $dellDiskUsed%
Mac Mini: $macMiniStatus
Mac Pro: $macProStatus
"@
    
    if ($streakDays -gt 0) {
        $telegramMsg += "`n`nStreak: $streakDays days!"
    }
    
    Write-Host "`n[TELEGRAM] Telegram summary:" -ForegroundColor Cyan
    Write-Host $telegramMsg
}

if (-not $Output -and -not $Telegram) {
    Write-Host "`n$('=' * 60)" -ForegroundColor DarkGray
    Write-Host "FULL REPORT:" -ForegroundColor Cyan
    Write-Host $('=' * 60) -ForegroundColor DarkGray
    Write-Host $reportText
}

# Return stats for programmatic use
return @{
    Improvements = $improvementCount
    Commits = $totalCommits
    MemoryFiles = $recentMemory.Count
    Scripts = $recentScripts.Count
    Streak = $streakDays
}
