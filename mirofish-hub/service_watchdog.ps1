# Service Watchdog - Keeps MiroFish + Whale API running
# Run this in background: Start-Process powershell -ArgumentList "-File C:\Users\USER\clawd\mirofish-hub\service_watchdog.ps1" -WindowStyle Hidden

$services = @(
    @{Name="Whale API"; Port=8081; StartCmd={Start-Process python -ArgumentList "whale_api.py" -WorkingDirectory "C:\Users\USER\clawd\mirofish-hub" -WindowStyle Hidden}},
    @{Name="MiroFish Backend"; Port=5001; StartCmd={Start-Process python -ArgumentList "backend/run.py" -WorkingDirectory "C:\Users\USER\Desktop\mirofish-secure" -WindowStyle Hidden}},
    @{Name="MiroFish Frontend"; Port=3000; StartCmd={Start-Process powershell -ArgumentList "-Command", "cd C:\Users\USER\Desktop\mirofish-secure\frontend; npm run dev" -WindowStyle Hidden}}
)

Write-Host "$(Get-Date) - Service Watchdog Started" -ForegroundColor Green
Write-Host "Monitoring: Whale API (8081), MiroFish Backend (5001), MiroFish Frontend (3000)"
Write-Host "Check interval: 60 seconds"
Write-Host ""

while ($true) {
    foreach ($svc in $services) {
        $listening = netstat -ano | Select-String "$($svc.Port).*LISTEN"
        if (-not $listening) {
            Write-Host "$(Get-Date) - $($svc.Name) DOWN on port $($svc.Port) - Restarting..." -ForegroundColor Red
            & $svc.StartCmd
            Start-Sleep 3
            $check = netstat -ano | Select-String "$($svc.Port).*LISTEN"
            if ($check) {
                Write-Host "$(Get-Date) - $($svc.Name) RESTARTED successfully" -ForegroundColor Green
            } else {
                Write-Host "$(Get-Date) - $($svc.Name) FAILED to restart" -ForegroundColor Yellow
            }
        }
    }
    Start-Sleep 60
}
