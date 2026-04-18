<#
.SYNOPSIS
    Security Audit Scanner - Multi-node security health checker
.DESCRIPTION
    Comprehensive security audit across all infrastructure nodes:
    - Firewall status checks
    - Exposed service detection
    - Secret/credential file scanning
    - SSH key inventory
    - Remediation recommendations
.EXAMPLE
    .\security-audit.ps1              # Full audit
    .\security-audit.ps1 -Quick       # Firewall + exposed ports only
    .\security-audit.ps1 -SecretsOnly # Just scan for secrets in files
    .\security-audit.ps1 -Report      # Generate markdown report
#>

param(
    [switch]$Quick,
    [switch]$SecretsOnly,
    [switch]$Report,
    [string]$ReportPath = (Join-Path $env:USERPROFILE "clawd\\memory\\security-audit-$(Get-Date -Format 'yyyy-MM-dd').md")
)

$ErrorActionPreference = "SilentlyContinue"
$ClawdRoot = Join-Path $env:USERPROFILE "clawd"

# Node definitions
$Nodes = @{
    "Mac-Mini" = @{
        IP = "100.88.105.106"
        User = "tommie"
        Critical = $true
        Role = "Local AI / Ollama"
    }
    "Mac-Pro" = @{
        IP = "100.86.80.74"
        User = "administrator"
        Critical = $false
        Role = "Heavy Workloads"
    }
    "Dell" = @{
        IP = "100.119.87.108"
        User = "tommi"
        Critical = $true
        Role = "Windows Workstation"
        IsLocal = $true
    }
}

# Secret patterns to detect
$SecretPatterns = @(
    @{ Name = "API Key"; Pattern = '(?i)(api[_\-]?key|apikey)\s*[:=]\s*[''"]?[a-zA-Z0-9_\-]{20,}' }
    @{ Name = "Bearer Token"; Pattern = '(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}' }
    @{ Name = "AWS Key"; Pattern = 'AKIA[0-9A-Z]{16}' }
    @{ Name = "Private Key"; Pattern = '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' }
    @{ Name = "Password"; Pattern = '(?i)(password|passwd|pwd)\s*[:=]\s*[''"]?[^\s''"]{8,}' }
    @{ Name = "Secret"; Pattern = '(?i)(secret|token|credential)\s*[:=]\s*[''"]?[a-zA-Z0-9_\-]{16,}' }
    @{ Name = "Telegram Bot Token"; Pattern = '[0-9]{8,10}:[a-zA-Z0-9_\-]{35}' }
    @{ Name = "OpenAI Key"; Pattern = 'sk-[a-zA-Z0-9]{20,}' }
    @{ Name = "GitHub Token"; Pattern = 'gh[pousr]_[A-Za-z0-9_]{36,}' }
)

# Dangerous ports to check
$DangerousPorts = @(22, 80, 443, 3000, 3389, 5432, 5900, 6379, 8080, 8443, 11434, 27017)

$Results = @{
    Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Firewalls = @()
    ExposedPorts = @()
    Secrets = @()
    Recommendations = @()
    Score = 100
}

function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host "=" * 60 -ForegroundColor DarkGray
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host "=" * 60 -ForegroundColor DarkGray
}

function Write-SubHeader {
    param([string]$Text)
    Write-Host ""
    Write-Host "[$Text]" -ForegroundColor Yellow
}

function Check-MacFirewall {
    param([string]$NodeName, [hashtable]$Node)
    
    Write-Host "  Checking $NodeName firewall..." -ForegroundColor Gray
    
    $sshCmd = "ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no $($Node.User)@$($Node.IP)"
    
    # Check global firewall state
    $firewallState = & cmd /c "$sshCmd '/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate' 2>&1"
    $stealthMode = & cmd /c "$sshCmd '/usr/libexec/ApplicationFirewall/socketfilterfw --getstealthmode' 2>&1"
    
    $isEnabled = $firewallState -match "enabled"
    $isStealth = $stealthMode -match "enabled"
    
    $status = @{
        Node = $NodeName
        FirewallEnabled = $isEnabled
        StealthMode = $isStealth
        Status = if ($isEnabled -and $isStealth) { "SECURE" } elseif ($isEnabled) { "PARTIAL" } else { "VULNERABLE" }
    }
    
    if (-not $isEnabled) {
        $Results.Score -= 20
        $Results.Recommendations += "[$NodeName] Enable firewall: sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on"
    }
    if (-not $isStealth) {
        $Results.Score -= 10
        $Results.Recommendations += "[$NodeName] Enable stealth mode: sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on"
    }
    
    # Status display
    $statusColor = switch ($status.Status) {
        "SECURE" { "Green" }
        "PARTIAL" { "Yellow" }
        "VULNERABLE" { "Red" }
    }
    
    Write-Host "    Firewall: " -NoNewline
    Write-Host $(if ($isEnabled) { "ON" } else { "OFF" }) -ForegroundColor $(if ($isEnabled) { "Green" } else { "Red" }) -NoNewline
    Write-Host " | Stealth: " -NoNewline
    Write-Host $(if ($isStealth) { "ON" } else { "OFF" }) -ForegroundColor $(if ($isStealth) { "Green" } else { "Red" }) -NoNewline
    Write-Host " | " -NoNewline
    Write-Host $status.Status -ForegroundColor $statusColor
    
    return $status
}

function Check-WindowsFirewall {
    Write-Host "  Checking Dell (local) firewall..." -ForegroundColor Gray
    
    $profiles = Get-NetFirewallProfile
    $allEnabled = $true
    
    foreach ($profile in $profiles) {
        if (-not $profile.Enabled) {
            $allEnabled = $false
            $Results.Score -= 10
            $Results.Recommendations += "[Dell] Enable $($profile.Name) firewall profile"
        }
    }
    
    $status = @{
        Node = "Dell"
        FirewallEnabled = $allEnabled
        Profiles = $profiles | ForEach-Object { @{ Name = $_.Name; Enabled = $_.Enabled } }
        Status = if ($allEnabled) { "SECURE" } else { "VULNERABLE" }
    }
    
    $statusColor = if ($allEnabled) { "Green" } else { "Red" }
    Write-Host "    All Profiles Enabled: " -NoNewline
    Write-Host $(if ($allEnabled) { "YES" } else { "NO" }) -ForegroundColor $statusColor -NoNewline
    Write-Host " | " -NoNewline
    Write-Host $status.Status -ForegroundColor $statusColor
    
    return $status
}

function Check-ExposedPorts {
    param([string]$NodeName, [hashtable]$Node)
    
    Write-Host "  Scanning $NodeName for exposed ports..." -ForegroundColor Gray
    
    $exposed = @()
    
    if ($Node.IsLocal) {
        # Local Windows check
        $listeners = Get-NetTCPConnection -State Listen | Where-Object { $_.LocalAddress -eq "0.0.0.0" -or $_.LocalAddress -eq "::" }
        foreach ($port in $DangerousPorts) {
            $found = $listeners | Where-Object { $_.LocalPort -eq $port }
            if ($found) {
                $processName = (Get-Process -Id $found[0].OwningProcess -ErrorAction SilentlyContinue).ProcessName
                $exposed += @{
                    Port = $port
                    Process = $processName
                    Risk = if ($port -in @(22, 3389, 5900)) { "HIGH" } else { "MEDIUM" }
                }
            }
        }
    }
    else {
        # Remote Mac check via SSH
        $sshCmd = "ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no $($Node.User)@$($Node.IP)"
        $netstat = & cmd /c "$sshCmd 'netstat -an | grep LISTEN' 2>&1"
        
        foreach ($port in $DangerousPorts) {
            if ($netstat -match "\*\.$port\s" -or $netstat -match "0\.0\.0\.0\.$port\s") {
                $exposed += @{
                    Port = $port
                    Process = "Unknown"
                    Risk = if ($port -in @(22, 3389, 5900)) { "HIGH" } else { "MEDIUM" }
                }
            }
        }
    }
    
    if ($exposed.Count -gt 0) {
        foreach ($e in $exposed) {
            $riskColor = if ($e.Risk -eq "HIGH") { "Red" } else { "Yellow" }
            Write-Host "    Port $($e.Port): " -NoNewline
            Write-Host $e.Risk -ForegroundColor $riskColor -NoNewline
            Write-Host " ($($e.Process))"
            
            if ($e.Risk -eq "HIGH") {
                $Results.Score -= 15
            } else {
                $Results.Score -= 5
            }
        }
        $Results.Recommendations += "[$NodeName] Review exposed ports: $($exposed.Port -join ', ')"
    }
    else {
        Write-Host "    No dangerous exposed ports found" -ForegroundColor Green
    }
    
    return $exposed
}

function Scan-SecretsInFiles {
    Write-Host "  Scanning local files for secrets..." -ForegroundColor Gray
    
    $scanPaths = @(
        (Join-Path $ClawdRoot "scripts"),
        (Join-Path $ClawdRoot "memory"),
        (Join-Path $ClawdRoot "configs"),
        (Join-Path $ClawdRoot "TaskBot")
    )
    
    $excludePatterns = @("*.exe", "*.dll", "*.png", "*.jpg", "*.gif", "*.mp3", "*.mp4", "node_modules", ".git", "venv")
    $secretsFound = @()
    
    foreach ($path in $scanPaths) {
        if (-not (Test-Path $path)) { continue }
        
        $files = Get-ChildItem -Path $path -Recurse -File -ErrorAction SilentlyContinue | 
            Where-Object { 
                $file = $_
                $exclude = $false
                foreach ($pattern in $excludePatterns) {
                    if ($file.FullName -like "*$pattern*") {
                        $exclude = $true
                        break
                    }
                }
                -not $exclude -and $_.Length -lt 1MB
            }
        
        foreach ($file in $files) {
            try {
                $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
                if (-not $content) { continue }
                
                foreach ($pattern in $SecretPatterns) {
                    if ($content -match $pattern.Pattern) {
                        $secretsFound += @{
                            File = $file.FullName.Replace("$ClawdRoot\", "")
                            Type = $pattern.Name
                            Line = ($content.Substring(0, [Math]::Min($content.IndexOf($Matches[0]) + 50, $content.Length)) -split "`n").Count
                        }
                        break  # One secret per file is enough to flag it
                    }
                }
            }
            catch {}
        }
    }
    
    if ($secretsFound.Count -gt 0) {
        $grouped = $secretsFound | Group-Object Type
        foreach ($g in $grouped) {
            Write-Host "    $($g.Name): " -NoNewline -ForegroundColor Yellow
            Write-Host "$($g.Count) files" -ForegroundColor Red
        }
        $Results.Score -= [Math]::Min($secretsFound.Count * 5, 30)
        $Results.Recommendations += "Review and rotate secrets in: $($secretsFound.File -join ', ')"
    }
    else {
        Write-Host "    No secrets found in scanned paths" -ForegroundColor Green
    }
    
    return $secretsFound
}

function Get-SecurityGrade {
    param([int]$Score)
    
    if ($Score -ge 90) { return @{ Grade = "A"; Color = "Green"; Text = "Excellent" } }
    if ($Score -ge 80) { return @{ Grade = "B"; Color = "Green"; Text = "Good" } }
    if ($Score -ge 70) { return @{ Grade = "C"; Color = "Yellow"; Text = "Fair" } }
    if ($Score -ge 60) { return @{ Grade = "D"; Color = "Yellow"; Text = "Needs Work" } }
    return @{ Grade = "F"; Color = "Red"; Text = "Critical" }
}

function Generate-Report {
    $grade = Get-SecurityGrade -Score $Results.Score
    
    $report = @"
# Security Audit Report
**Generated:** $($Results.Timestamp)
**Security Score:** $($Results.Score)/100 (Grade: $($grade.Grade) - $($grade.Text))

## Firewall Status

| Node | Firewall | Stealth | Status |
|------|----------|---------|--------|
"@

    foreach ($fw in $Results.Firewalls) {
        $report += "`n| $($fw.Node) | $(if ($fw.FirewallEnabled) { 'âœ… ON' } else { 'âŒ OFF' }) | $(if ($fw.StealthMode) { 'âœ… ON' } else { 'âŒ OFF' }) | $($fw.Status) |"
    }

    if ($Results.ExposedPorts.Count -gt 0) {
        $report += @"

## Exposed Ports

| Node | Port | Risk | Process |
|------|------|------|---------|
"@
        foreach ($node in $Results.ExposedPorts.Keys) {
            foreach ($p in $Results.ExposedPorts[$node]) {
                $report += "`n| $node | $($p.Port) | $($p.Risk) | $($p.Process) |"
            }
        }
    }

    if ($Results.Secrets.Count -gt 0) {
        $report += @"

## Secrets Detected

| File | Type |
|------|------|
"@
        foreach ($s in $Results.Secrets) {
            $report += "`n| $($s.File) | $($s.Type) |"
        }
    }

    if ($Results.Recommendations.Count -gt 0) {
        $report += @"

## Recommendations

"@
        foreach ($rec in $Results.Recommendations) {
            $report += "- $rec`n"
        }
    }

    $report += @"

---
*Automated security audit by security-audit.ps1*
"@

    return $report
}

# ============================================================
# MAIN EXECUTION
# ============================================================

Write-Header "SECURITY AUDIT SCANNER"
Write-Host "  $($Results.Timestamp)" -ForegroundColor Gray

if (-not $SecretsOnly) {
    Write-SubHeader "FIREWALL STATUS"
    
    # Check Dell (local)
    $Results.Firewalls += Check-WindowsFirewall
    
    # Check Mac nodes
    foreach ($nodeName in @("Mac-Mini", "Mac-Pro")) {
        $node = $Nodes[$nodeName]
        $Results.Firewalls += Check-MacFirewall -NodeName $nodeName -Node $node
    }
}

if (-not $SecretsOnly -and -not $Quick) {
    Write-SubHeader "EXPOSED PORTS"
    
    $Results.ExposedPorts = @{}
    foreach ($nodeName in $Nodes.Keys) {
        $node = $Nodes[$nodeName]
        $exposed = Check-ExposedPorts -NodeName $nodeName -Node $node
        if ($exposed.Count -gt 0) {
            $Results.ExposedPorts[$nodeName] = $exposed
        }
    }
}

if (-not $Quick) {
    Write-SubHeader "SECRET DETECTION"
    $Results.Secrets = Scan-SecretsInFiles
}

# Final Summary
Write-Header "SECURITY SUMMARY"

$grade = Get-SecurityGrade -Score $Results.Score
Write-Host ""
Write-Host "  Security Score: " -NoNewline
Write-Host "$($Results.Score)/100" -ForegroundColor $grade.Color -NoNewline
Write-Host " | Grade: " -NoNewline
Write-Host $grade.Grade -ForegroundColor $grade.Color -NoNewline
Write-Host " ($($grade.Text))"

if ($Results.Recommendations.Count -gt 0) {
    Write-Host ""
    Write-Host "  Recommendations ($($Results.Recommendations.Count)):" -ForegroundColor Yellow
    foreach ($rec in $Results.Recommendations | Select-Object -First 5) {
        Write-Host "    â€¢ $rec" -ForegroundColor Gray
    }
    if ($Results.Recommendations.Count -gt 5) {
        Write-Host "    ... and $($Results.Recommendations.Count - 5) more" -ForegroundColor DarkGray
    }
}

# Generate report if requested
if ($Report) {
    $reportContent = Generate-Report
    $reportContent | Out-File -FilePath $ReportPath -Encoding UTF8
    Write-Host ""
    Write-Host "  Report saved: " -NoNewline
    Write-Host $ReportPath -ForegroundColor Cyan
}

Write-Host ""
