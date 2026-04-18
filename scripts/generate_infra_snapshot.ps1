# Generate Infrastructure Snapshot (source-of-truth draft)
$ErrorActionPreference = 'Continue'
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$docPath = "C:\Users\USER\clawd\docs\infra_snapshot.md"

$local = hostname
$gpu = & nvidia-smi --query-gpu=temperature.gpu,memory.used,memory.total --format=csv,noheader 2>$null

$macMini = ""
try {
    $macMini = ssh -o ConnectTimeout=10 tommie@100.88.105.106 "hostname; uptime; df -h / | tail -1" 2>$null
} catch { }

$lines = @()
$lines += "# Infrastructure Snapshot"
$lines += "Generated: $timestamp"
$lines += ""
$lines += "## RTX Workstation (local)"
$lines += "Host: $local"
$lines += "GPU: $gpu"
$lines += ""
$lines += "## Mac Mini (100.88.105.106)"
if ($macMini) { $lines += $macMini } else { $lines += "UNREACHABLE" }
$lines += ""
$lines += "## Mac Pro"
$lines += "IP mismatch in docs (100.84.100.23 vs 100.86.80.74). Verify live IP and update." 
$lines += ""
$lines += "## Google Cloud"
$lines += "100.107.231.87 (backup node)"

$lines | Set-Content -Path $docPath
Write-Host "Snapshot written: $docPath"
