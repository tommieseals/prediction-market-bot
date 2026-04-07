# Auto-Remediation Scripts

Automated remediation scripts for Mac Mini/Pro infrastructure monitoring.

## Scripts

### 1. `auto-cleanup.sh`
**Purpose:** Cleans logs and temp files when disk usage exceeds threshold

**Features:**
- Configurable disk threshold (default: 80%)
- Safe cleanup targets (logs, caches, temp files)
- Age-based deletion (won't delete recent files)
- Dry-run mode for testing

**Usage:**
```bash
# Check Mac Mini, dry-run first
./auto-cleanup.sh --host mac-mini --dry-run

# Actually clean when disk > 80%
./auto-cleanup.sh --host mac-mini

# Force cleanup regardless of disk usage
./auto-cleanup.sh --host mac-mini --force

# Lower threshold to 70%
./auto-cleanup.sh --host mac-mini --threshold 70 --verbose
```

### 2. `auto-restart-services.sh`
**Purpose:** Checks and restarts ollama/clawdbot if they're down

**Features:**
- Health checks before restart
- Multiple retry attempts
- Service verification after restart
- Dry-run mode for testing

**Usage:**
```bash
# Check all services on Mac Mini
./auto-restart-services.sh --host mac-mini --dry-run

# Check only ollama
./auto-restart-services.sh --host mac-mini --service ollama

# Check clawdbot gateway
./auto-restart-services.sh --host mac-mini --service clawdbot

# With verbose output
./auto-restart-services.sh --host mac-mini --verbose
```

## Common Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Show what would happen without making changes |
| `--host HOST` | Target host: `mac-mini`, `mac-pro`, or IP address |
| `--local` | Run on local machine (no SSH) |
| `--verbose` | Show detailed output |
| `--help` | Show help message |

## Host Aliases

| Alias | IP Address |
|-------|------------|
| `mac-mini` / `mini` | 100.88.105.106 |
| `mac-pro` / `pro` | 100.89.75.126 |

## Integration with Monitoring

### From Cron
```bash
# Check services every 5 minutes
*/5 * * * * /path/to/auto-restart-services.sh --host mac-mini

# Clean disk daily at 3 AM
0 3 * * * /path/to/auto-cleanup.sh --host mac-mini --force
```

### From Main Monitoring Script
```bash
# In your monitoring script:
source ./scripts/auto-cleanup.sh --host "$HOST" --threshold 80
source ./scripts/auto-restart-services.sh --host "$HOST" --service all
```

### Programmatic Call
```bash
# Check if cleanup needed
if ./auto-cleanup.sh --host mac-mini --dry-run | grep -q "Cleanup required"; then
    ./auto-cleanup.sh --host mac-mini
fi
```

## Logs

All scripts log to `/tmp/clawd-remediation/`:
- `auto-cleanup-YYYYMMDD.log`
- `auto-restart-services-YYYYMMDD.log`

## Safety Features

1. **Dry-run mode** - Always test with `--dry-run` first
2. **Age-based cleanup** - Only deletes files older than N days
3. **Safe paths only** - Won't touch system files or user data
4. **Retry logic** - Multiple attempts before giving up
5. **Comprehensive logging** - Full audit trail
6. **Exit codes** - Machine-readable status for automation

## Exit Codes

### auto-cleanup.sh
| Code | Meaning |
|------|---------|
| 0 | Success (cleanup done or not needed) |
| 1 | Error during cleanup |
| 2 | Invalid arguments |

### auto-restart-services.sh
| Code | Meaning |
|------|---------|
| 0 | All services running |
| 1 | Service restart failed |
| 2 | Invalid arguments |
| 3 | Connection failed |
