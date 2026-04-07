# Infra Health Check
# Logs HTTP health for key services (local + remote)
$ErrorActionPreference = 'Continue'

$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$logDir = "C:\Users\USER\clawd\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "infra_health_$timestamp.log"

function Check-Url {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSec = 8
    )
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSec
        "$Name | OK | $($resp.StatusCode) | $Url" | Out-File -FilePath $logFile -Append
    } catch {
        "$Name | FAIL | $Url | $($_.Exception.Message)" | Out-File -FilePath $logFile -Append
    }
}

"Infra Health Check - $timestamp" | Out-File -FilePath $logFile
"==================================" | Out-File -FilePath $logFile -Append

# Local (RTX)
Check-Url -Name "Interview Service" -Url "http://localhost:5100/health"
Check-Url -Name "Whale Hunter Dashboard" -Url "http://localhost:8081/consensus"
Check-Url -Name "MiroFish Backend" -Url "http://localhost:5001/health"

# Mac Mini (Orchestrator)
Check-Url -Name "Mac Mini Dashboard" -Url "http://100.88.105.106:8080/infrastructure.html"
Check-Url -Name "Mac Mini Gateway" -Url "http://100.88.105.106:18789/"

# Mac Pro (Monitoring Stack) - IP may need verification
Check-Url -Name "Grafana" -Url "http://100.89.75.126:3000"
Check-Url -Name "Prometheus" -Url "http://100.89.75.126:9090"
Check-Url -Name "Uptime Kuma" -Url "http://100.89.75.126:3001"

"Done." | Out-File -FilePath $logFile -Append
Write-Host "Health check complete: $logFile"
