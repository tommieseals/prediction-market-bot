# Security Permission Audit (Windows)
$ErrorActionPreference = 'Continue'

$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$logDir = "C:\Users\USER\clawd\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "security_perm_audit_$timestamp.log"

$paths = @(
    "C:\Users\User\.clawdbot",
    "C:\Users\User\.clawdbot\clawdbot.json",
    "C:\Users\User\.clawdbot\credentials",
    "C:\Users\User\.clawdbot\agents\main\agent\auth-profiles.json",
    "C:\Users\User\.clawdbot\agents\interview\agent\auth-profiles.json"
)

"Security Perm Audit - $timestamp" | Out-File -FilePath $logFile
"===============================" | Out-File -FilePath $logFile -Append

foreach ($p in $paths) {
    if (-not (Test-Path $p)) {
        "$p | MISSING" | Out-File -FilePath $logFile -Append
        continue
    }
    $acl = icacls $p
    $flag = $false
    foreach ($line in $acl) {
        if ($line -match "Everyone" -or $line -match "BUILTIN\\Users") {
            if ($line -match "\(F\)" -or $line -match "\(W\)" -or $line -match "\(M\)") {
                $flag = $true
            }
        }
    }
    if ($flag) {
        "$p | WARNING: broad write permissions detected" | Out-File -FilePath $logFile -Append
    } else {
        "$p | OK" | Out-File -FilePath $logFile -Append
    }
}

Write-Host "Security perm audit complete: $logFile"
