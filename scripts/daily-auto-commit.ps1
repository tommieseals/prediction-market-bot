<#
.SYNOPSIS
    Daily Auto-Commit - Automatically commits and pushes memory/script changes
    
.DESCRIPTION
    Keeps GitHub activity green and preserves all daily work by:
    - Committing memory file changes (daily logs, improvements, etc.)
    - Committing script changes
    - Committing documentation updates
    - Pushing to remote repository
    - Generating activity statistics
    
.PARAMETER DryRun
    Show what would be committed without actually committing
    
.PARAMETER Force
    Commit even if there are no meaningful changes
    
.PARAMETER Message
    Custom commit message (default: auto-generated based on changes)
    
.PARAMETER NoPush
    Commit but don't push to remote
    
.PARAMETER Stats
    Show GitHub activity statistics only

.EXAMPLE
    .\daily-auto-commit.ps1
    Auto-commit and push all changes
    
.EXAMPLE
    .\daily-auto-commit.ps1 -DryRun
    Preview what would be committed
    
.EXAMPLE
    .\daily-auto-commit.ps1 -Stats
    Show activity statistics

.NOTES
    Author: Bottom Bitch Bot
    Created: 2026-03-09
    Purpose: Keep GitHub green, preserve daily work
#>

param(
    [switch]$DryRun,
    [switch]$Force,
    [string]$Message,
    [switch]$NoPush,
    [switch]$Stats
)

$RepoPath = "C:\Users\User\clawd"
$Today = Get-Date -Format "yyyy-MM-dd"
$Now = Get-Date -Format "HH:mm:ss"

# Categories of files to track
$Categories = @{
    "memory" = @{
        Pattern = "memory/*.md"
        Icon = "[MEM]"
        Name = "Memory"
    }
    "scripts" = @{
        Pattern = @("scripts/*.ps1", "scripts/*.py", "scripts/*.sh")
        Icon = "[SCR]"
        Name = "Scripts"
    }
    "docs" = @{
        Pattern = @("docs/*.md", "*.md")
        Icon = "[DOC]"
        Name = "Documentation"
    }
    "config" = @{
        Pattern = @("*.json", "*.yaml", "*.yml")
        Icon = "[CFG]"
        Name = "Config"
    }
}

function Write-Header {
    param([string]$Text)
    Write-Host "`n=========================================================" -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor White
    Write-Host "=========================================================" -ForegroundColor Cyan
}

function Write-Status {
    param(
        [string]$Status,
        [string]$Message,
        [string]$Detail = ""
    )
    
    $icon = switch ($Status) {
        "OK"      { "[OK]" }
        "WARN"    { "[!!]" }
        "ERROR"   { "[XX]" }
        "INFO"    { "[--]" }
        "SKIP"    { "[>>]" }
        "COMMIT"  { "[++]" }
        "PUSH"    { "[=>]" }
        default   { "[  ]" }
    }
    
    $color = switch ($Status) {
        "OK"      { "Green" }
        "WARN"    { "Yellow" }
        "ERROR"   { "Red" }
        "INFO"    { "Cyan" }
        "SKIP"    { "DarkGray" }
        "COMMIT"  { "Magenta" }
        "PUSH"    { "Blue" }
        default   { "White" }
    }
    
    Write-Host "  $icon " -ForegroundColor $color -NoNewline
    Write-Host $Message -ForegroundColor White -NoNewline
    if ($Detail) {
        Write-Host " - $Detail" -ForegroundColor DarkGray
    } else {
        Write-Host ""
    }
}

function Get-GitStatus {
    Push-Location $RepoPath
    try {
        $status = git status --porcelain 2>&1
        return $status
    } finally {
        Pop-Location
    }
}

function Get-ChangedFiles {
    Push-Location $RepoPath
    try {
        $status = git status --porcelain 2>&1
        $files = @()
        
        foreach ($line in $status) {
            if ($line -match "^(..)(.+)$") {
                $statusCode = $Matches[1].Trim()
                $filePath = $Matches[2].Trim()
                
                # Handle renamed files
                if ($filePath -match "->") {
                    $filePath = ($filePath -split "->" | Select-Object -Last 1).Trim()
                }
                
                $files += @{
                    Status = $statusCode
                    Path = $filePath
                    Category = Get-FileCategory $filePath
                }
            }
        }
        
        return $files
    } finally {
        Pop-Location
    }
}

function Get-FileCategory {
    param([string]$FilePath)
    
    if ($FilePath -match "^memory/") { return "memory" }
    if ($FilePath -match "^scripts/") { return "scripts" }
    if ($FilePath -match "^docs/") { return "docs" }
    if ($FilePath -match "\.(json|yaml|yml)$") { return "config" }
    if ($FilePath -match "\.md$") { return "docs" }
    return "other"
}

function Get-CommitMessage {
    param([array]$ChangedFiles)
    
    if ($Message) { return $Message }
    
    # Count by category
    $counts = @{}
    foreach ($file in $ChangedFiles) {
        $cat = $file.Category
        if (-not $counts[$cat]) { $counts[$cat] = 0 }
        $counts[$cat]++
    }
    
    # Build message
    $parts = @()
    foreach ($cat in $counts.Keys | Sort-Object) {
        $info = $Categories[$cat]
        if ($info) {
            $parts += "$($counts[$cat]) $($info.Name.ToLower())"
        } else {
            $parts += "$($counts[$cat]) other"
        }
    }
    
    $summary = $parts -join ", "
    return "Daily update ($Today): $summary"
}

function Show-Stats {
    Write-Header "GITHUB ACTIVITY STATISTICS"
    
    Push-Location $RepoPath
    try {
        # Today's commits
        $todayCommits = (git log --oneline --since="$Today 00:00:00" 2>&1 | Measure-Object).Count
        Write-Status "INFO" "Commits today" "$todayCommits"
        
        # This week
        $weekStart = (Get-Date).AddDays(-7).ToString("yyyy-MM-dd")
        $weekCommits = (git log --oneline --since="$weekStart" 2>&1 | Measure-Object).Count
        Write-Status "INFO" "Commits this week" "$weekCommits"
        
        # This month
        $monthStart = (Get-Date).ToString("yyyy-MM-01")
        $monthCommits = (git log --oneline --since="$monthStart" 2>&1 | Measure-Object).Count
        Write-Status "INFO" "Commits this month" "$monthCommits"
        
        # Streak calculation
        $streak = 0
        $checkDate = Get-Date
        while ($streak -lt 365) {
            $dateStr = $checkDate.ToString("yyyy-MM-dd")
            $nextDate = $checkDate.AddDays(1).ToString("yyyy-MM-dd")
            $dayCommits = (git log --oneline --since="$dateStr 00:00:00" --until="$nextDate 00:00:00" 2>&1 | Measure-Object).Count
            if ($dayCommits -gt 0) {
                $streak++
                $checkDate = $checkDate.AddDays(-1)
            } else {
                break
            }
        }
        Write-Status "INFO" "Current streak" "$streak days"
        
        # Last commit
        $lastCommit = git log -1 --format="%ar - %s" 2>&1
        Write-Status "INFO" "Last commit" "$lastCommit"
        
        # Pending changes
        $pending = Get-ChangedFiles
        if ($pending.Count -gt 0) {
            Write-Host ""
            Write-Status "WARN" "Uncommitted changes" "$($pending.Count) files"
            foreach ($file in $pending | Select-Object -First 10) {
                Write-Host "        * $($file.Path)" -ForegroundColor DarkGray
            }
            if ($pending.Count -gt 10) {
                Write-Host "        ... and $($pending.Count - 10) more" -ForegroundColor DarkGray
            }
        } else {
            Write-Status "OK" "Working tree clean" ""
        }
        
    } finally {
        Pop-Location
    }
}

function Do-Commit {
    param([switch]$DryRun)
    
    Write-Header "DAILY AUTO-COMMIT"
    Write-Host "  Repository: $RepoPath" -ForegroundColor DarkGray
    Write-Host "  Time: $Today $Now" -ForegroundColor DarkGray
    
    # Check if we're in a git repo
    Push-Location $RepoPath
    try {
        $isGit = git rev-parse --is-inside-work-tree 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Status "ERROR" "Not a git repository" "$RepoPath"
            return
        }
    } finally {
        Pop-Location
    }
    
    # Get changed files
    $changed = Get-ChangedFiles
    
    if ($changed.Count -eq 0) {
        Write-Status "SKIP" "No changes to commit" ""
        if (-not $Force) {
            return
        }
        Write-Status "INFO" "Force flag set, continuing anyway" ""
    }
    
    # Show what would be committed
    Write-Host "`n  Changes to commit:" -ForegroundColor Yellow
    
    $byCategory = $changed | Group-Object -Property Category
    foreach ($group in $byCategory) {
        $catInfo = $Categories[$group.Name]
        $icon = if ($catInfo) { $catInfo.Icon } else { "[OTH]" }
        Write-Host "     $icon $($group.Name.ToUpper()) ($($group.Count) files)" -ForegroundColor Cyan
        foreach ($file in $group.Group | Select-Object -First 5) {
            $statusIcon = switch ($file.Status) {
                "M"  { "~" }  # Modified
                "A"  { "+" }  # Added
                "D"  { "-" }  # Deleted
                "??" { "?" }  # Untracked
                default { "*" }
            }
            Write-Host "        $statusIcon $($file.Path)" -ForegroundColor DarkGray
        }
        if ($group.Count -gt 5) {
            Write-Host "        ... and $($group.Count - 5) more" -ForegroundColor DarkGray
        }
    }
    
    # Generate commit message
    $commitMsg = Get-CommitMessage -ChangedFiles $changed
    Write-Host "`n  Commit message:" -ForegroundColor Yellow
    Write-Host "     $commitMsg" -ForegroundColor White
    
    if ($DryRun) {
        Write-Host "`n  [DRY RUN] No changes made" -ForegroundColor Yellow
        return
    }
    
    # Do the actual commit
    Push-Location $RepoPath
    try {
        # Stage all changes
        Write-Status "COMMIT" "Staging changes..." ""
        git add -A 2>&1 | Out-Null
        
        # Commit
        Write-Status "COMMIT" "Creating commit..." ""
        $commitResult = git commit -m $commitMsg 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            if ($commitResult -match "nothing to commit") {
                Write-Status "SKIP" "Nothing to commit" ""
            } else {
                Write-Status "ERROR" "Commit failed" "$commitResult"
            }
            return
        }
        
        Write-Status "OK" "Committed successfully" ""
        
        # Push unless -NoPush
        if (-not $NoPush) {
            Write-Status "PUSH" "Pushing to remote..." ""
            $pushResult = git push 2>&1
            
            if ($LASTEXITCODE -ne 0) {
                Write-Status "ERROR" "Push failed" "$pushResult"
            } else {
                Write-Status "OK" "Pushed to remote" ""
            }
        } else {
            Write-Status "SKIP" "Push skipped (-NoPush)" ""
        }
        
        # Show new commit info
        $newCommit = git log -1 --format="%h %s" 2>&1
        Write-Host "`n  New commit: $newCommit" -ForegroundColor Green
        
    } finally {
        Pop-Location
    }
}

# Main execution
if ($Stats) {
    Show-Stats
} else {
    Do-Commit -DryRun:$DryRun
}

Write-Host ""
