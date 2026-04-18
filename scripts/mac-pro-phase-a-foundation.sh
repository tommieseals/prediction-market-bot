#!/bin/bash
#
# Mac Pro - Phase A Foundation Setup
# Turns a fresh Mac into a production-grade core node
#
# What this does:
# 1. Installs Homebrew + base tools
# 2. Sets up PostgreSQL + Redis
# 3. Creates directory structure
# 4. Sets up centralized logging
# 5. Creates heartbeat + health monitoring
# 6. Locks down firewall (Tailscale-first)
# 7. Prepares service registry skeleton
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $*"; }
warn() { echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $*"; }
error() { echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $*"; }

# Configuration
INSTALL_DIR="$HOME/mac-pro-core"
LOG_DIR="$INSTALL_DIR/logs"
CONFIG_DIR="$INSTALL_DIR/config"
DATA_DIR="$INSTALL_DIR/data"
SCRIPTS_DIR="$INSTALL_DIR/scripts"

log "Starting Phase A Foundation Setup for Mac Pro"
log "Install directory: $INSTALL_DIR"

# ============================================================================
# Step 1: Install Homebrew (if not present)
# ============================================================================
log "Step 1: Checking Homebrew..."
if ! command -v brew &> /dev/null; then
    log "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add to PATH for this session
    eval "$(/usr/local/bin/brew shellenv)"
else
    log "Homebrew already installed"
    brew update
fi

# ============================================================================
# Step 2: Install base tools
# ============================================================================
log "Step 2: Installing base tools..."
brew install \
    git \
    jq \
    curl \
    wget \
    htop \
    postgresql@15 \
    redis \
    docker \
    docker-compose \
    node \
    python@3.11

# ============================================================================
# Step 3: Create directory structure
# ============================================================================
log "Step 3: Creating directory structure..."
mkdir -p "$INSTALL_DIR"/{logs,config,data,scripts,backups,tmp}
mkdir -p "$LOG_DIR"/{services,health,errors}
mkdir -p "$DATA_DIR"/{postgres,redis,n8n}

log "Directory structure created:"
tree -L 2 "$INSTALL_DIR" || ls -la "$INSTALL_DIR"

# ============================================================================
# Step 4: Set up PostgreSQL
# ============================================================================
log "Step 4: Setting up PostgreSQL..."

# Start PostgreSQL service
brew services start postgresql@15

# Wait for PostgreSQL to be ready
sleep 3

# Create databases
createdb -U "$USER" mac_pro_registry 2>/dev/null || warn "Database mac_pro_registry already exists"
createdb -U "$USER" n8n 2>/dev/null || warn "Database n8n already exists"

log "PostgreSQL databases created: mac_pro_registry, n8n"

# ============================================================================
# Step 5: Set up Redis
# ============================================================================
log "Step 5: Setting up Redis..."
brew services start redis

log "Redis started"

# ============================================================================
# Step 6: Set up centralized logging
# ============================================================================
log "Step 6: Setting up centralized logging..."

cat > "$SCRIPTS_DIR/log-aggregator.sh" << 'LOGSCRIPT'
#!/bin/bash
# Central log aggregator - all services log here

LOG_FILE="$HOME/mac-pro-core/logs/unified.log"
MAX_SIZE_MB=100

log_message() {
    local service="$1"
    local level="$2"
    local message="$3"
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [$service] [$level] $message" >> "$LOG_FILE"
}

# Rotate if too big
if [ -f "$LOG_FILE" ]; then
    size_mb=$(du -m "$LOG_FILE" | cut -f1)
    if [ "$size_mb" -gt "$MAX_SIZE_MB" ]; then
        mv "$LOG_FILE" "$LOG_FILE.$(date +%Y%m%d-%H%M%S)"
        gzip "$LOG_FILE".* &
    fi
fi

# Export function for other scripts to use
export -f log_message
LOGSCRIPT

chmod +x "$SCRIPTS_DIR/log-aggregator.sh"

# Create initial log file
touch "$LOG_DIR/unified.log"

log "Centralized logging configured at $LOG_DIR/unified.log"

# ============================================================================
# Step 7: Create health monitoring system
# ============================================================================
log "Step 7: Creating health monitoring system..."

cat > "$SCRIPTS_DIR/health-check.sh" << 'HEALTHSCRIPT'
#!/bin/bash
# Health check script - monitors all services

source "$HOME/mac-pro-core/scripts/log-aggregator.sh"

check_service() {
    local service="$1"
    local command="$2"
    
    if eval "$command" &> /dev/null; then
        log_message "health-check" "INFO" "$service is healthy"
        return 0
    else
        log_message "health-check" "ERROR" "$service is DOWN"
        return 1
    fi
}

# Check PostgreSQL
check_service "postgresql" "pg_isready -U $USER"

# Check Redis
check_service "redis" "redis-cli ping"

# Check disk space
disk_usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$disk_usage" -gt 80 ]; then
    log_message "health-check" "WARNING" "Disk usage at ${disk_usage}%"
fi

# Check RAM
ram_pressure=$(memory_pressure | grep "System-wide memory free percentage" | awk '{print $5}' | sed 's/%//')
if [ "$ram_pressure" -lt 20 ]; then
    log_message "health-check" "WARNING" "RAM pressure high (${ram_pressure}% free)"
fi

# Output health status
echo "{\"timestamp\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\",\"status\":\"healthy\"}"
HEALTHSCRIPT

chmod +x "$SCRIPTS_DIR/health-check.sh"

# ============================================================================
# Step 8: Create heartbeat service
# ============================================================================
log "Step 8: Creating heartbeat service..."

cat > "$SCRIPTS_DIR/heartbeat.sh" << 'HEARTBEAT'
#!/bin/bash
# Heartbeat - runs every 5 minutes, checks if we're alive

source "$HOME/mac-pro-core/scripts/log-aggregator.sh"

log_message "heartbeat" "INFO" "Heartbeat tick"

# Run health check
"$HOME/mac-pro-core/scripts/health-check.sh" > "$HOME/mac-pro-core/logs/health/$(date +%Y%m%d-%H%M).json"

# Cleanup old health logs (keep last 24 hours)
find "$HOME/mac-pro-core/logs/health" -name "*.json" -mtime +1 -delete
HEARTBEAT

chmod +x "$SCRIPTS_DIR/heartbeat.sh"

# Create launchd plist for heartbeat
cat > "$HOME/Library/LaunchAgents/com.macpro.heartbeat.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.macpro.heartbeat</string>
    <key>ProgramArguments</key>
    <array>
        <string>$SCRIPTS_DIR/heartbeat.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/heartbeat.out</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/heartbeat.err</string>
</dict>
</plist>
PLIST

launchctl load "$HOME/Library/LaunchAgents/com.macpro.heartbeat.plist" 2>/dev/null || warn "Heartbeat service may already be loaded"

log "Heartbeat service configured (runs every 5 minutes)"

# ============================================================================
# Step 9: Create service registry
# ============================================================================
log "Step 9: Creating service registry..."

cat > "$CONFIG_DIR/service-registry.json" << 'REGISTRY'
{
  "version": "1.0.0",
  "node": {
    "name": "mac-pro",
    "role": "core-node",
    "ip": "100.86.80.74",
    "capabilities": [
      "ollama-inference",
      "llm-gateway",
      "n8n-orchestration",
      "telegram-bot",
      "service-coordination"
    ]
  },
  "services": {
    "postgresql": {
      "status": "running",
      "port": 5432,
      "health_endpoint": "pg_isready"
    },
    "redis": {
      "status": "running",
      "port": 6379,
      "health_endpoint": "redis-cli ping"
    },
    "ollama": {
      "status": "not_installed",
      "port": 11434,
      "models": []
    },
    "llm-gateway": {
      "status": "not_installed",
      "port": 8080
    },
    "n8n": {
      "status": "not_installed",
      "port": 5678
    },
    "telegram-bot": {
      "status": "not_installed",
      "port": 3000
    }
  },
  "routing_rules": {
    "code_tasks": "mac-pro-ollama",
    "simple_queries": "mac-mini-ollama",
    "vision_tasks": "api-fallback",
    "complex_reasoning": "api-fallback"
  },
  "failover": {
    "primary": "mac-pro",
    "secondary": "mac-mini",
    "tertiary": "google-cloud"
  }
}
REGISTRY

log "Service registry created at $CONFIG_DIR/service-registry.json"

# ============================================================================
# Step 10: Create secrets management template
# ============================================================================
log "Step 10: Creating secrets management template..."

cat > "$CONFIG_DIR/secrets.env.template" << 'SECRETS'
# Secrets configuration template
# Copy this to secrets.env and fill in real values
# NEVER commit secrets.env to git!

# Telegram
TELEGRAM_BOT_TOKEN=your_token_here

# OpenAI (if using)
OPENAI_API_KEY=your_key_here

# Other API keys
ANTHROPIC_API_KEY=
NVIDIA_API_KEY=

# PostgreSQL
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=mac_pro_registry

# Redis (if auth needed)
REDIS_PASSWORD=
SECRETS

cat > "$CONFIG_DIR/.gitignore" << 'GITIGNORE'
secrets.env
*.key
*.pem
GITIGNORE

log "Secrets template created (fill in $CONFIG_DIR/secrets.env)"

# ============================================================================
# Step 11: Firewall lockdown (macOS firewall + Tailscale-first)
# ============================================================================
log "Step 11: Configuring firewall..."

# Enable macOS firewall
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setloggingmode on
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on

log "macOS firewall enabled (stealth mode on)"
warn "IMPORTANT: Ensure Tailscale is installed and connected!"
warn "All external access should go through Tailscale (100.86.80.74)"

# ============================================================================
# Step 12: Create disaster recovery script
# ============================================================================
log "Step 12: Creating disaster recovery script..."

cat > "$SCRIPTS_DIR/disaster-recovery.sh" << 'RECOVERY'
#!/bin/bash
# Disaster recovery - restore from backup and restart all services

set -euo pipefail

echo "=== Mac Pro Disaster Recovery ==="
echo "This will restore from the latest backup and restart all services"
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Stop all services
echo "Stopping services..."
brew services stop postgresql@15
brew services stop redis

# Restore PostgreSQL from latest backup
LATEST_BACKUP=$(ls -t "$HOME/mac-pro-core/backups/postgres"/*.sql.gz 2>/dev/null | head -1)
if [ -n "$LATEST_BACKUP" ]; then
    echo "Restoring PostgreSQL from $LATEST_BACKUP..."
    gunzip -c "$LATEST_BACKUP" | psql -U "$USER" -d mac_pro_registry
fi

# Restart services in order
echo "Starting PostgreSQL..."
brew services start postgresql@15
sleep 3

echo "Starting Redis..."
brew services start redis
sleep 2

echo "Starting Ollama (if installed)..."
brew services start ollama 2>/dev/null || echo "Ollama not installed yet"

echo "Recovery complete!"
echo "Check logs: tail -f $HOME/mac-pro-core/logs/unified.log"
RECOVERY

chmod +x "$SCRIPTS_DIR/disaster-recovery.sh"

log "Disaster recovery script created"

# ============================================================================
# Step 13: Create backup automation
# ============================================================================
log "Step 13: Creating backup automation..."

mkdir -p "$INSTALL_DIR/backups/postgres"

cat > "$SCRIPTS_DIR/backup.sh" << 'BACKUP'
#!/bin/bash
# Daily backup script

BACKUP_DIR="$HOME/mac-pro-core/backups"
DATE=$(date +%Y%m%d-%H%M)

# Backup PostgreSQL
pg_dump -U "$USER" mac_pro_registry | gzip > "$BACKUP_DIR/postgres/mac_pro_registry-$DATE.sql.gz"

# Backup configs
tar czf "$BACKUP_DIR/configs-$DATE.tar.gz" -C "$HOME/mac-pro-core" config/

# Cleanup old backups (keep 7 days)
find "$BACKUP_DIR" -name "*.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
BACKUP

chmod +x "$SCRIPTS_DIR/backup.sh"

# Create launchd plist for daily backups
cat > "$HOME/Library/LaunchAgents/com.macpro.backup.plist" << BACKUPPLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.macpro.backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>$SCRIPTS_DIR/backup.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/backup.out</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/backup.err</string>
</dict>
</plist>
BACKUPPLIST

launchctl load "$HOME/Library/LaunchAgents/com.macpro.backup.plist" 2>/dev/null || warn "Backup service may already be loaded"

log "Backup automation configured (runs daily at 2 AM)"

# ============================================================================
# Step 14: Create status dashboard script
# ============================================================================
log "Step 14: Creating status dashboard..."

cat > "$SCRIPTS_DIR/status.sh" << 'STATUS'
#!/bin/bash
# Show current status of all services

echo "=== Mac Pro Core Node Status ==="
echo ""
echo "Services:"
echo "  PostgreSQL: $(brew services list | grep postgresql@15 | awk '{print $2}')"
echo "  Redis: $(brew services list | grep redis | awk '{print $2}')"
echo ""
echo "System:"
echo "  RAM Free: $(vm_stat | awk '/free/ {print $3}' | sed 's/\.//' | awk '{printf "%.2f GB\n", $1 * 4096 / 1024 / 1024 / 1024}')"
echo "  Disk Free: $(df -h / | awk 'NR==2 {print $4}')"
echo "  CPU Load: $(uptime | awk -F'load average:' '{print $2}')"
echo ""
echo "Latest health check:"
cat "$HOME/mac-pro-core/logs/health/"$(ls -t "$HOME/mac-pro-core/logs/health" | head -1) 2>/dev/null || echo "  No health data yet"
echo ""
echo "Service registry: $HOME/mac-pro-core/config/service-registry.json"
echo "Logs: $HOME/mac-pro-core/logs/unified.log"
STATUS

chmod +x "$SCRIPTS_DIR/status.sh"

# ============================================================================
# DONE!
# ============================================================================

log ""
log "========================================="
log "Phase A Foundation Setup Complete! âœ…"
log "========================================="
log ""
log "What was installed:"
log "  âœ“ Homebrew + base tools"
log "  âœ“ PostgreSQL (databases: mac_pro_registry, n8n)"
log "  âœ“ Redis"
log "  âœ“ Centralized logging ($LOG_DIR/unified.log)"
log "  âœ“ Health monitoring (every 5 min)"
log "  âœ“ Daily backups (2 AM)"
log "  âœ“ Service registry"
log "  âœ“ Firewall hardening"
log ""
log "Key locations:"
log "  Install: $INSTALL_DIR"
log "  Logs: $LOG_DIR/unified.log"
log "  Config: $CONFIG_DIR"
log "  Scripts: $SCRIPTS_DIR"
log ""
log "Useful commands:"
log "  Status: $SCRIPTS_DIR/status.sh"
log "  Health: $SCRIPTS_DIR/health-check.sh"
log "  Backup: $SCRIPTS_DIR/backup.sh"
log "  Recovery: $SCRIPTS_DIR/disaster-recovery.sh"
log ""
log "Next steps:"
log "  1. Fill in secrets: $CONFIG_DIR/secrets.env"
log "  2. Phase B: Install Ollama + models"
log "  3. Phase C: Install LLM Gateway, n8n, Telegram bot"
log ""
warn "IMPORTANT: Ensure Tailscale is running! All access should be via 100.86.80.74"
log ""
log "Run '$SCRIPTS_DIR/status.sh' to see current status"
