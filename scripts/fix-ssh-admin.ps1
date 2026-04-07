# Run this as Administrator to fix SSH key permissions
$keyFile = "C:\ProgramData\ssh\administrators_authorized_keys"
$macMiniKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPlp9pSOCwbrNapYAuO146H08Z9Dyv8tnaAkRe+GQacE tommie@Tommies-Mac-mini.local"

Write-Host "=== SSH Key Fix Script ===" -ForegroundColor Cyan

# Check if key already exists
$content = Get-Content $keyFile -ErrorAction SilentlyContinue
if ($content -match "tommie@Tommies-Mac-mini") {
    Write-Host "Key already in file" -ForegroundColor Green
} else {
    Add-Content -Path $keyFile -Value $macMiniKey
    Write-Host "Key added" -ForegroundColor Green
}

# Fix permissions (critical for Windows OpenSSH)
Write-Host "Fixing permissions..." -ForegroundColor Yellow
icacls $keyFile /inheritance:r
icacls $keyFile /grant "NT AUTHORITY\SYSTEM:(R)"
icacls $keyFile /grant "BUILTIN\Administrators:(R)"

# Show current permissions
Write-Host "`nCurrent permissions:" -ForegroundColor Cyan
icacls $keyFile

# Restart SSH service
Write-Host "`nRestarting SSH service..." -ForegroundColor Yellow
Restart-Service sshd
Write-Host "SSH service restarted" -ForegroundColor Green

# Show file contents
Write-Host "`nFile contents:" -ForegroundColor Cyan
Get-Content $keyFile

Write-Host "`n=== Done! Test with: ssh User@100.119.87.108 ===" -ForegroundColor Green
Read-Host "Press Enter to close"
