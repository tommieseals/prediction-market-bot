<#
.SYNOPSIS
    Memory Consolidator - Distill old daily logs into MEMORY.md learnings
    
.DESCRIPTION
    Reads memory files older than a threshold, extracts key sections and
    highlights, and appends a summary to MEMORY.md.
    
.EXAMPLE
    .\memory-consolidator.ps1              # Analyze files older than 7 days
    .\memory-consolidator.ps1 -Days 14     # Analyze files older than 14 days
    .\memory-consolidator.ps1 -Preview     # Preview only (no changes)
    .\memory-consolidator.ps1 -Archive     # Also archive processed files
#>

param(
    [int]$Days = 7,
    [switch]$Preview,
    [switch]$Archive,
    [switch]$Force
)

$ErrorActionPreference = "Continue"
$MemoryDir = "C:\Users\User\clawd\memory"
$ArchiveDir = "C:\Users\User\clawd\memory\archive"
$MemoryFile = "C:\Users\User\clawd\MEMORY.md"
$Cutoff = (Get-Date).AddDays(-$Days)

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "      MEMORY CONSOLIDATOR" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Processing files older than: $Days days ($($Cutoff.ToString('yyyy-MM-dd')))" -ForegroundColor DarkGray

# Find daily log files (YYYY-MM-DD.md format)
$DailyFiles = Get-ChildItem -Path $MemoryDir -Filter "????-??-??.md" -ErrorAction SilentlyContinue | Where-Object { 
    $dateStr = $_.BaseName
    try {
        $fileDate = [DateTime]::ParseExact($dateStr, "yyyy-MM-dd", $null)
        return $Force -or ($fileDate -lt $Cutoff)
    } catch {
        return $false
    }
} | Sort-Object Name

if ($DailyFiles.Count -eq 0) {
    Write-Host ""
    Write-Host "[OK] No files older than $Days days to process." -ForegroundColor Green
    exit 0
}

Write-Host ""
Write-Host "[FILES] Found $($DailyFiles.Count) files to process:" -ForegroundColor Yellow
foreach ($f in $DailyFiles) {
    Write-Host "   - $($f.Name)" -ForegroundColor DarkGray
}

# Smart extraction function - finds key content
function Extract-KeyContent {
    param([string]$Content, [string]$FileName)
    
    $Insights = @()
    
    # Extract headers (## and ### sections)
    $HeaderMatches = [regex]::Matches($Content, '(?m)^##+ (.+)$')
    $Headers = @()
    foreach ($m in $HeaderMatches) {
        $h = $m.Groups[1].Value.Trim()
        if ($h -and $h -notmatch '^(daily|log|notes?|todo|tasks?)$') {
            $Headers += $h
        }
    }
    if ($Headers.Count -gt 0) {
        $Insights += "**Topics:** $($Headers -join ', ')"
    }
    
    # Look for key patterns
    $Patterns = @{
        'Fixed/Solved' = '(?i)(fixed|solved|resolved|working now)[:\s]+([^\n]+)'
        'Learned' = '(?i)(learned|discovered|realized|found out)[:\s]+([^\n]+)'
        'Decision' = '(?i)(decided|decision|going with|chose)[:\s]+([^\n]+)'
        'Important' = '(?i)(important|critical|remember|note)[:\s]+([^\n]+)'
        'Issue' = '(?i)(problem|issue|bug|broken|error)[:\s]+([^\n]+)'
    }
    
    foreach ($key in $Patterns.Keys) {
        $Matches = [regex]::Matches($Content, $Patterns[$key])
        if ($Matches.Count -gt 0) {
            $firstMatch = $Matches[0].Groups[2].Value.Trim()
            if ($firstMatch.Length -gt 10 -and $firstMatch.Length -lt 200) {
                $Insights += "**${key}:** $firstMatch"
            }
        }
    }
    
    # Look for bullet points with key words
    $BulletMatches = [regex]::Matches($Content, '(?m)^[-*]\s+(.+(?:important|key|remember|learned|fixed|solved|decided).+)$')
    foreach ($m in $BulletMatches) {
        $bullet = $m.Groups[1].Value.Trim()
        if ($bullet.Length -gt 20 -and $bullet.Length -lt 200) {
            $Insights += "- $bullet"
        }
    }
    
    # Count stats
    $LineCount = ($Content -split "`n").Count
    $WordCount = ($Content -split '\s+').Count
    
    if ($Insights.Count -eq 0) {
        # Fallback: just report size
        $Insights += "**Stats:** $LineCount lines, $WordCount words"
        
        # Try to get first meaningful paragraph
        $Paragraphs = $Content -split "`n`n" | Where-Object { $_.Trim().Length -gt 50 }
        if ($Paragraphs.Count -gt 0) {
            $FirstPara = $Paragraphs[0].Trim().Substring(0, [Math]::Min(150, $Paragraphs[0].Length))
            $Insights += "**Summary:** $FirstPara..."
        }
    }
    
    return $Insights
}

# Process each file
$AllInsights = @()
$ProcessedFiles = @()

foreach ($File in $DailyFiles) {
    Write-Host ""
    Write-Host "[FILE] Processing: $($File.Name)" -ForegroundColor Yellow
    
    $Content = Get-Content $File.FullName -Raw -ErrorAction SilentlyContinue
    if (-not $Content -or $Content.Length -lt 50) {
        Write-Host "   [SKIP] Too short or empty" -ForegroundColor DarkGray
        continue
    }
    
    $Insights = Extract-KeyContent -Content $Content -FileName $File.Name
    
    if ($Insights.Count -gt 0) {
        Write-Host "   [OK] Extracted $($Insights.Count) insights:" -ForegroundColor Green
        foreach ($insight in $Insights) {
            Write-Host "      $insight" -ForegroundColor White
        }
        $AllInsights += @{
            Date = $File.BaseName
            Insights = $Insights -join "`n"
        }
        $ProcessedFiles += $File
    } else {
        Write-Host "   [SKIP] No key content found" -ForegroundColor DarkGray
    }
}

# Generate consolidated report
if ($AllInsights.Count -eq 0) {
    Write-Host ""
    Write-Host "[WARN] No insights extracted from any files." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "      CONSOLIDATION SUMMARY" -ForegroundColor Cyan  
Write-Host "======================================" -ForegroundColor Cyan

$DateStr = Get-Date -Format 'yyyy-MM-dd'
$DateRange = "$($DailyFiles[0].BaseName) to $($DailyFiles[-1].BaseName)"
$ConsolidatedText = @"

---

## Memory Consolidation - $DateStr

**Source:** $($ProcessedFiles.Count) daily logs ($DateRange)

"@

foreach ($Item in $AllInsights) {
    $ConsolidatedText += @"

### $($Item.Date)
$($Item.Insights)

"@
}

Write-Host $ConsolidatedText

if ($Preview) {
    Write-Host ""
    Write-Host "[PREVIEW] No changes made. Run without -Preview to save." -ForegroundColor Yellow
    exit 0
}

# Append to MEMORY.md
Write-Host ""
Write-Host "[SAVE] Appending to MEMORY.md..." -ForegroundColor Cyan
Add-Content -Path $MemoryFile -Value $ConsolidatedText -Encoding UTF8
Write-Host "   [OK] Added $($AllInsights.Count) entries" -ForegroundColor Green

# Archive if requested
if ($Archive -and $ProcessedFiles.Count -gt 0) {
    Write-Host ""
    Write-Host "[ARCHIVE] Moving processed files..." -ForegroundColor Cyan
    
    if (-not (Test-Path $ArchiveDir)) {
        New-Item -ItemType Directory -Path $ArchiveDir | Out-Null
    }
    
    foreach ($File in $ProcessedFiles) {
        $DestPath = Join-Path $ArchiveDir $File.Name
        Move-Item -Path $File.FullName -Destination $DestPath -Force
        Write-Host "   [MOVED] $($File.Name)" -ForegroundColor DarkGray
    }
    
    Write-Host "   [OK] Archived $($ProcessedFiles.Count) files" -ForegroundColor Green
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "   CONSOLIDATION COMPLETE" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host "   Files processed: $($ProcessedFiles.Count)"
Write-Host "   Insights extracted: $($AllInsights.Count)"
Write-Host ""
