#!/bin/bash
# Restart Clawdbot on Dell (100.115.12.91)
# Use this if Dell bot goes down

DELL_IP="100.115.12.91"
DELL_USER="User"

echo "[$(date)] Attempting to restart Clawdbot on Dell..."

ssh -o ConnectTimeout=15 -o BatchMode=yes ${DELL_USER}@${DELL_IP} 'powershell -Command "Stop-Process -Name node -Force -ErrorAction SilentlyContinue; Start-Sleep 2; Start-Process powershell -ArgumentList \"-WindowStyle Hidden -Command clawdbot gateway start\" -WindowStyle Hidden; Write-Host Clawdbot_restarted"'

if [ $? -eq 0 ]; then
    echo "[$(date)] SUCCESS: Clawdbot restart command sent"
else
    echo "[$(date)] FAILED: Could not reach Dell"
fi
