<#
.SYNOPSIS
    Check infrastructure health across all nodes
.EXAMPLE
    .\infra-status.ps1
#>

Write-Host ""
Write-Host "======== TOMMIE'S AI EMPIRE - STATUS ========" -ForegroundColor Cyan
Write-Host ""

$nodes = @(
    @{ name = "Mac Mini"; ip = "100.88.105.106"; ollama = $true },
    @{ name = "Mac Pro"; ip = "100.89.75.126"; ollama = $true },
    @{ name = "Google Cloud"; ip = "100.107.231.87"; ollama = $true },
    @{ name = "iPhone"; ip = "100.114.130.38"; ollama = $false }
)

foreach ($node in $nodes) {
    $ping = ping -n 1 -w 1000 $node.ip 2>$null | Select-String "TTL="
    
    if ($ping) {
        Write-Host "$($node.name.PadRight(15)) [$($node.ip)]  " -NoNewline
        Write-Host "ONLINE" -ForegroundColor Green
        
        if ($node.ollama) {
            try {
                $response = Invoke-RestMethod -Uri "http://$($node.ip):11434/api/tags" -TimeoutSec 3
                $models = $response.models.name -join ", "
                Write-Host "                 Models: $models" -ForegroundColor DarkGray
            } catch {
                Write-Host "                 Ollama: Not responding" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "$($node.name.PadRight(15)) [$($node.ip)]  " -NoNewline
        Write-Host "OFFLINE" -ForegroundColor Red
    }
}

Write-Host ""
