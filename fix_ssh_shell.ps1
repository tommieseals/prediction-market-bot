# SSH Shell Fix — Run this as Administrator
# Changes default SSH shell from PowerShell to cmd.exe for cross-platform compatibility
# This lets Jarvis (Mac Pro bot) run commands over SSH without PowerShell syntax errors

Write-Host "Updating SSH DefaultShell to cmd.exe..." -ForegroundColor Cyan

New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\cmd.exe" -PropertyType String -Force
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShellCommandOption -Value "/c" -PropertyType String -Force

Write-Host "Restarting sshd..." -ForegroundColor Cyan
Restart-Service sshd

Write-Host ""
Write-Host "Verifying:" -ForegroundColor Cyan
Get-ItemProperty "HKLM:\SOFTWARE\OpenSSH" | Select-Object DefaultShell, DefaultShellCommandOption
Get-Service sshd | Select-Object Name, Status

Write-Host ""
Write-Host "Done! SSH now uses cmd.exe /c for commands." -ForegroundColor Green
Write-Host "Jarvis (Mac Pro) should be able to SSH in now." -ForegroundColor Green
