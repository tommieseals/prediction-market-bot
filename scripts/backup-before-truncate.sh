#!/bin/bash
# Backup Before Truncate Script
# Run this BEFORE truncating any logs
# Sends backup to Mac Pro for permanent storage

set -e

DATE=$(date +%Y-%m-%d_%H%M%S)
MAC_PRO="administrator@100.86.80.74"
BACKUP_NAME="logs-backup-${DATE}"
LOCAL_BACKUP="/tmp/${BACKUP_NAME}"
REMOTE_BACKUP="~/fort-knox-backups/"

echo "=== Backup Before Truncate: $(date) ==="

# Create local staging directory
mkdir -p "${LOCAL_BACKUP}"

# 1. Backup current logs
echo "Backing up logs..."
if [ -d "$HOME/clawd/logs" ]; then
    cp -r "$HOME/clawd/logs" "${LOCAL_BACKUP}/clawd-logs"
fi

if [ -d "$HOME/.clawdbot/logs" ]; then
    cp -r "$HOME/.clawdbot/logs" "${LOCAL_BACKUP}/clawdbot-logs"
fi

# 2. Backup shared memory (important!)
echo "Backing up shared memory..."
if [ -d "$HOME/shared-memory" ]; then
    cp -r "$HOME/shared-memory" "${LOCAL_BACKUP}/shared-memory"
fi

# 3. Create compressed archive
echo "Compressing..."
cd /tmp
tar -czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}"

# 4. Send to Mac Pro
echo "Sending to Mac Pro..."
ssh "${MAC_PRO}" "mkdir -p ${REMOTE_BACKUP}"
scp "/tmp/${BACKUP_NAME}.tar.gz" "${MAC_PRO}:${REMOTE_BACKUP}/"

# 5. Verify transfer
echo "Verifying..."
ssh "${MAC_PRO}" "ls -la ${REMOTE_BACKUP}/${BACKUP_NAME}.tar.gz"

# 6. Cleanup local temp
rm -rf "${LOCAL_BACKUP}"
rm -f "/tmp/${BACKUP_NAME}.tar.gz"

echo ""
echo "=== Backup Complete ==="
echo "Stored at: ${MAC_PRO}:${REMOTE_BACKUP}/${BACKUP_NAME}.tar.gz"
echo ""
echo "Now safe to truncate logs."
