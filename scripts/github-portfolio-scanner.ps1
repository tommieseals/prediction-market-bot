<#
.SYNOPSIS
    GitHub Portfolio Scanner - Find projects worth pushing to impress employers

.DESCRIPTION
    Scans local projects and identifies what's GitHub-ready:
    - Checks for README.md
    - Detects language/framework
    - Warns about secrets/personal data
    - Suggests improvements
    - Helps prepare code for public release

.PARAMETER Path
    Root path to scan for projects (default: clawd folder)

.PARAMETER Detailed
    Show detailed analysis for each project

.PARAMETER PrepareFor
    Generate a preparation checklist for a specific project

.EXAMPLE
    .\github-portfolio-scanner.ps1
    .\github-portfolio-scanner.ps1 -Detailed
    .\github-portfolio-scanner.ps1 -PrepareFor "taskbot-site"
#>

param(
    [string]$Path = "C:\Users\User\clawd",
    [switch]$Detailed,
    [string]$PrepareFor
)

# ANSI Colors
$Green = "`e[32m"
$Yellow = "`e[33m"
$Red = "`e[31m"
$Cyan = "`e[36m"
$Reset = "`e[0m"
$Bold = "`e[1m"

# Secret patterns to detect (NEVER push these)
$SecretPatterns = @(
    @{Pattern = 'sk-[a-zA-Z0-9]{48}'; Name = 'OpenAI API Key'},
    @{Pattern = 'sk-proj-[a-zA-Z0-9\-_]{80,}'; Name = 'OpenAI Project Key'},
    @{Pattern = 'AKIA[0-9A-Z]{16}'; Name = 'AWS Access Key'},
    @{Pattern = 'ghp_[a-zA-Z0-9]{36}'; Name = 'GitHub Personal Token'},
    @{Pattern = 'xoxb-[0-9]{11}-[0-9]{11}-[a-zA-Z0-9]{24}'; Name = 'Slack Bot Token'},
    @{Pattern = '[0-9]+:[A-Za-z0-9_-]{35}'; Name = 'Telegram Bot Token'},
    @{Pattern = 'AIza[0-9A-Za-z\-_]{35}'; Name = 'Google API Key'},
    @{Pattern = '-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'; Name = 'Private Key'},
    @{Pattern = 'password\s*[=:]\s*["\x27][^"\x27]+["\x27]'; Name = 'Hardcoded Password'},
    @{Pattern = 'api[_-]?key\s*[=:]\s*["\x27][^"\x27]{10,}["\x27]'; Name = 'API Key Assignment'}
)

# Personal data patterns (warn but don't block)
$PersonalPatterns = @(
    @{Pattern = 'tommieseals|tommie\.seals'; Name = 'Personal Name'},
    @{Pattern = 'tommieseals7700@gmail\.com'; Name = 'Personal Email'},
    @{Pattern = '\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'; Name = 'Phone Number'},
    @{Pattern = '100\.(88|101|107|119)\.\d+\.\d+'; Name = 'Tailscale IP'}
)

# Folders to always ignore
$IgnoreFolders = @(
    'node_modules', '.git', '__pycache__', 'venv', '.venv', 'env',
    'memory', 'sessions', 'private', '.cache', 'dist', 'build',
    'api-keys', 'secrets', '.next', 'coverage'
)

# File extensions for code
$CodeExtensions = @('.ps1', '.py', '.js', '.ts', '.tsx', '.jsx', '.sh', '.bash', '.go', '.rs', '.rb', '.java', '.cs', '.cpp', '.c', '.h')

function Get-ProjectScore {
    param([string]$ProjectPath)
    
    $score = 0
    $notes = @()
    
    # Check for README
    if (Test-Path (Join-Path $ProjectPath "README.md")) {
        $score += 25
        $notes += "$Green[OK] Has README$Reset"
    } else {
        $notes += "$Yellow[!] Missing README$Reset"
    }
    
    # Check for package.json (Node project)
    if (Test-Path (Join-Path $ProjectPath "package.json")) {
        $score += 15
        $notes += "$Green[OK] Node.js project$Reset"
    }
    
    # Check for requirements.txt or pyproject.toml (Python)
    if ((Test-Path (Join-Path $ProjectPath "requirements.txt")) -or 
        (Test-Path (Join-Path $ProjectPath "pyproject.toml"))) {
        $score += 15
        $notes += "$Green[OK] Python project$Reset"
    }
    
    # Check for .gitignore
    if (Test-Path (Join-Path $ProjectPath ".gitignore")) {
        $score += 10
        $notes += "$Green[OK] Has .gitignore$Reset"
    } else {
        $notes += "$Yellow[!] Missing .gitignore$Reset"
    }
    
    # Check for LICENSE
    $licenseFiles = Get-ChildItem -Path $ProjectPath -Filter "LICENSE*" -ErrorAction SilentlyContinue
    if ($licenseFiles) {
        $score += 10
        $notes += "$Green[OK] Has LICENSE$Reset"
    } else {
        $notes += "$Cyan[~] No LICENSE (optional)$Reset"
    }
    
    # Count code files
    $codeFiles = Get-ChildItem -Path $ProjectPath -Recurse -File -ErrorAction SilentlyContinue | 
        Where-Object { $CodeExtensions -contains $_.Extension -and 
                      ($IgnoreFolders | ForEach-Object { $_.FullName -notlike "*\$_\*" }) -notcontains $false }
    
    $codeCount = ($codeFiles | Measure-Object).Count
    if ($codeCount -gt 10) {
        $score += 20
        $notes += "$Green[OK] Substantial codebase ($codeCount files)$Reset"
    } elseif ($codeCount -gt 3) {
        $score += 10
        $notes += "$Cyan[~] Small project ($codeCount files)$Reset"
    } else {
        $notes += "$Yellow[!] Very few code files ($codeCount)$Reset"
    }
    
    return @{
        Score = $score
        Notes = $notes
        CodeFiles = $codeCount
    }
}

function Find-Secrets {
    param([string]$ProjectPath)
    
    $secrets = @()
    $files = Get-ChildItem -Path $ProjectPath -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { 
            $_.Length -lt 500KB -and
            ($CodeExtensions -contains $_.Extension -or 
            $_.Extension -in @('.json', '.yaml', '.yml', '.env', '.ini', '.conf', '.cfg', '.md', '.txt'))
        }
    
    foreach ($file in $files) {
        # Skip ignored folders
        $skip = $false
        foreach ($ignore in $IgnoreFolders) {
            if ($file.FullName -like "*\$ignore\*") {
                $skip = $true
                break
            }
        }
        if ($skip) { continue }
        
        try {
            $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
            if (-not $content) { continue }
            
            foreach ($pattern in $SecretPatterns) {
                if ($content -match $pattern.Pattern) {
                    $secrets += @{
                        File = $file.FullName.Replace($ProjectPath, "").TrimStart("\")
                        Type = $pattern.Name
                        Severity = "CRITICAL"
                    }
                }
            }
            
            foreach ($pattern in $PersonalPatterns) {
                if ($content -match $pattern.Pattern) {
                    $secrets += @{
                        File = $file.FullName.Replace($ProjectPath, "").TrimStart("\")
                        Type = $pattern.Name
                        Severity = "WARNING"
                    }
                }
            }
        } catch {
            # Skip unreadable files
        }
    }
    
    return $secrets
}

function Get-ProjectLanguage {
    param([string]$ProjectPath)
    
    $langs = @()
    
    if (Test-Path (Join-Path $ProjectPath "package.json")) { $langs += "JavaScript/TypeScript" }
    if (Test-Path (Join-Path $ProjectPath "requirements.txt")) { $langs += "Python" }
    if (Test-Path (Join-Path $ProjectPath "pyproject.toml")) { $langs += "Python" }
    if (Test-Path (Join-Path $ProjectPath "Cargo.toml")) { $langs += "Rust" }
    if (Test-Path (Join-Path $ProjectPath "go.mod")) { $langs += "Go" }
    $csProj = Get-ChildItem -Path $ProjectPath -Filter "*.csproj" -ErrorAction SilentlyContinue
    if ($csProj) { $langs += "C#" }
    $ps1Files = Get-ChildItem -Path $ProjectPath -Filter "*.ps1" -ErrorAction SilentlyContinue
    if ($ps1Files) { $langs += "PowerShell" }
    $shFiles = Get-ChildItem -Path $ProjectPath -Filter "*.sh" -ErrorAction SilentlyContinue
    if ($shFiles) { $langs += "Bash" }
    
    if ($langs.Count -eq 0) { return "Unknown" }
    return ($langs | Select-Object -Unique) -join ", "
}

function Show-PrepareChecklist {
    param([string]$ProjectName)
    
    $projectPath = Join-Path $Path $ProjectName
    if (-not (Test-Path $projectPath)) {
        Write-Host "${Red}Project not found: $ProjectName$Reset"
        return
    }
    
    Write-Host ""
    Write-Host "$Bold${Cyan}=== PREPARATION CHECKLIST: $ProjectName ===$Reset"
    Write-Host ("=" * 50)
    
    # Check each item
    $hasReadme = Test-Path (Join-Path $projectPath "README.md")
    $hasGitignore = Test-Path (Join-Path $projectPath ".gitignore")
    $licenseFiles = Get-ChildItem -Path $projectPath -Filter "LICENSE*" -ErrorAction SilentlyContinue
    $hasLicense = $null -ne $licenseFiles -and $licenseFiles.Count -gt 0
    $secrets = Find-Secrets -ProjectPath $projectPath
    $criticalSecrets = $secrets | Where-Object { $_.Severity -eq "CRITICAL" }
    
    Write-Host ""
    Write-Host "${Bold}Required:$Reset"
    $readmeStatus = if($hasReadme){"$Green[OK]"}else{"$Red[X]"}
    $gitignoreStatus = if($hasGitignore){"$Green[OK]"}else{"$Red[X]"}
    $secretsStatus = if($criticalSecrets.Count -eq 0){"$Green[OK]"}else{"$Red[X]"}
    Write-Host "  $readmeStatus$Reset README.md with project description"
    Write-Host "  $gitignoreStatus$Reset .gitignore file"
    Write-Host "  $secretsStatus$Reset No secrets/API keys in code"
    
    Write-Host ""
    Write-Host "${Bold}Recommended:$Reset"
    $licenseStatus = if($hasLicense){"$Green[OK]"}else{"$Yellow[~]"}
    Write-Host "  $licenseStatus$Reset LICENSE file (MIT recommended)"
    Write-Host "  $Yellow[~]$Reset Screenshots in README (if visual)"
    Write-Host "  $Yellow[~]$Reset Installation instructions"
    Write-Host "  $Yellow[~]$Reset Usage examples"
    
    if ($criticalSecrets.Count -gt 0) {
        Write-Host ""
        Write-Host "$Bold${Red}!!! SECRETS FOUND - FIX BEFORE PUSHING:$Reset"
        foreach ($secret in $criticalSecrets) {
            Write-Host "  $Red* $($secret.Type) in $($secret.File)$Reset"
        }
    }
    
    # Generate README template if missing
    if (-not $hasReadme) {
        Write-Host ""
        Write-Host "$Bold${Cyan}Suggested README.md template:$Reset"
        Write-Host ""
        $lang = Get-ProjectLanguage -ProjectPath $projectPath
        Write-Host "# $ProjectName"
        Write-Host ""
        Write-Host "Brief description of what this project does."
        Write-Host ""
        Write-Host "## Features"
        Write-Host ""
        Write-Host "* Feature 1"
        Write-Host "* Feature 2"
        Write-Host "* Feature 3"
        Write-Host ""
        Write-Host "## Installation"
        Write-Host ""
        Write-Host "    # Installation commands here"
        Write-Host ""
        Write-Host "## Usage"
        Write-Host ""
        Write-Host "    # Usage examples here"
        Write-Host ""
        Write-Host "## Tech Stack"
        Write-Host ""
        Write-Host "* $lang"
        Write-Host ""
        Write-Host "## License"
        Write-Host ""
        Write-Host "MIT"
    }
    
    Write-Host ""
}

# Main execution
if ($PrepareFor) {
    Show-PrepareChecklist -ProjectName $PrepareFor
    exit 0
}

Write-Host ""
Write-Host "$Bold${Cyan}=== GITHUB PORTFOLIO SCANNER ===$Reset"
Write-Host "Scanning: $Path"
Write-Host ("=" * 50)
Write-Host ""

# Find potential projects (directories with code)
$projects = @()
$subdirs = Get-ChildItem -Path $Path -Directory -ErrorAction SilentlyContinue |
    Where-Object { $IgnoreFolders -notcontains $_.Name -and $_.Name -notlike ".*" }

foreach ($dir in $subdirs) {
    $scoreResult = Get-ProjectScore -ProjectPath $dir.FullName
    if ($scoreResult.CodeFiles -gt 0) {
        $secrets = Find-Secrets -ProjectPath $dir.FullName
        $lang = Get-ProjectLanguage -ProjectPath $dir.FullName
        
        $projects += @{
            Name = $dir.Name
            Path = $dir.FullName
            Score = $scoreResult.Score
            Notes = $scoreResult.Notes
            CodeFiles = $scoreResult.CodeFiles
            Secrets = $secrets
            Language = $lang
            CriticalSecrets = ($secrets | Where-Object { $_.Severity -eq "CRITICAL" }).Count
            HasReadme = Test-Path (Join-Path $dir.FullName "README.md")
        }
    }
}

# Sort by score
$projects = $projects | Sort-Object -Property Score -Descending

# Display results
Write-Host "${Bold}Found $($projects.Count) potential projects:$Reset"
Write-Host ""

foreach ($proj in $projects) {
    $scoreColor = if ($proj.Score -ge 60) { $Green } 
                  elseif ($proj.Score -ge 40) { $Yellow }
                  else { $Red }
    
    if ($proj.CriticalSecrets -gt 0) {
        $statusIcon = "$Red[SECRETS]"
    } elseif (-not $proj.HasReadme) {
        $statusIcon = "$Yellow[NO README]"
    } elseif ($proj.Score -ge 60) {
        $statusIcon = "$Green[READY]"
    } else {
        $statusIcon = "$Yellow[NEEDS WORK]"
    }
    
    Write-Host "$statusIcon$Reset $Bold$($proj.Name)$Reset - ${scoreColor}Score: $($proj.Score)/100$Reset"
    Write-Host "   Language: $($proj.Language) | Files: $($proj.CodeFiles)"
    
    if ($proj.CriticalSecrets -gt 0) {
        Write-Host "   $Red!! $($proj.CriticalSecrets) secrets found - needs cleanup!$Reset"
    }
    
    if ($Detailed) {
        foreach ($note in $proj.Notes) {
            Write-Host "   $note"
        }
    }
    
    Write-Host ""
}

# Summary
Write-Host ("=" * 50)
Write-Host "${Bold}SUMMARY:$Reset"
$ready = ($projects | Where-Object { $_.Score -ge 60 -and $_.CriticalSecrets -eq 0 }).Count
$needsWork = ($projects | Where-Object { $_.Score -ge 40 -and $_.Score -lt 60 }).Count
$hasSecrets = ($projects | Where-Object { $_.CriticalSecrets -gt 0 }).Count

Write-Host "  $Green[READY] Ready to push: $ready projects$Reset"
Write-Host "  $Yellow[WORK] Needs README/cleanup: $needsWork projects$Reset"
Write-Host "  $Red[FIX] Has secrets (fix first!): $hasSecrets projects$Reset"

Write-Host ""
Write-Host "${Cyan}TIP: Run with -PrepareFor 'project-name' to get a preparation checklist$Reset"
Write-Host ""
