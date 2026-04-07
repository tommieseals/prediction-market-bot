# Start Whale Tracker API
# Run this to start the API server on port 8081

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

Write-Host "Starting Whale Tracker API on port 8081..." -ForegroundColor Cyan
python whale_api.py
