# Sync Whale Data to Dashboard
# Run this periodically to keep dashboard updated

$ErrorActionPreference = "Continue"

Write-Host "🐋 Syncing whale data to dashboard..." -ForegroundColor Cyan

# Export latest data
$env:PYTHONUTF8 = "1"
python C:\Users\USER\clawd\mirofish-hub\export_whale_data.py

# Copy to Mac Mini
Write-Host "📤 Uploading to Mac Mini..." -ForegroundColor Yellow
scp C:\Users\USER\clawd\mirofish-hub\whale_positions.json tommie@100.88.105.106:~/clawd/dashboard/data/whale_positions.json

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Whale data synced successfully!" -ForegroundColor Green
} else {
    Write-Host "❌ Sync failed!" -ForegroundColor Red
}
