#!/bin/bash
#==============================================================================
# AUTO-RESTART-SERVICES.SH - Automated Service Recovery Script
#==============================================================================
# Purpose: Checks and restarts ollama/clawdbot services if they're down
# Target:  Mac Mini (100.88.105.106) / Mac Pro (100.86.80.74) via SSH
# Usage:   ./auto-restart-services.sh [OPTIONS]
#
# Options:
#   --dry-run     Show what would be done without actually restarting
#   --service SVC Check/restart specific service (ollama, clawdbot, all)
#   --host HOST   Target host (mac-mini, mac-pro, or IP address)
#   --local       Run locally instead of via SSH
#   --max-retries N  Maximum restart attempts (default: 3)
#   --wait-time N    Seconds to wait after restart (default: 10)
#   --verbose     Show detailed output
#   --help        Show this help message
#
# Exit Codes:
#   0 - All services running (or restarted successfully)
#   1 - Service restart failed
#   2 - Invalid arguments
#   3 - Connection failed
#==============================================================================

set -euo pipefail

#------------------------------------------------------------------------------
# Configuration
#------------------------------------------------------------------------------
SCRIPT_NAME="auto-restart-services"
SCRIPT_VERSION="1.0.0"
LOG_DIR="${LOG_DIR:-/tmp/clawd-remediation}"
LOG_FILE="${LOG_DIR}/${SCRIPT_NAME}-$(date +%Y%m%d).log"
DRY_RUN=false
VERBOSE=false
LOCAL_MODE=false
TARGET_HOST=""
TARGET_SERVICE="all"
MAX_RETRIES=3
WAIT_TIME=10

# Default hosts (from TOOLS.md)
MAC_MINI="100.88.105.106"
MAC_PRO="100.86.80.74"

#------------------------------------------------------------------------------
# Service Definitions
# Format: service_name:check_command:start_command:stop_command:description
#------------------------------------------------------------------------------
declare -A SERVICES

# Ollama service definition
SERVICES[ollama_check]="pgrep -x ollama > /dev/null 2>&1"
SERVICES[ollama_start]="launchctl load ~/Library/LaunchAgents/com.ollama.server.plist 2>/dev/null || ollama serve &"
SERVICES[ollama_stop]="launchctl unload ~/Library/LaunchAgents/com.ollama.server.plist 2>/dev/null || pkill -x ollama"
SERVICES[ollama_verify]="curl -s http://localhost:11434/api/tags > /dev/null 2>&1"
SERVICES[ollama_desc]="Ollama LLM Server"

# Clawdbot Gateway service definition
SERVICES[clawdbot_check]="pgrep -f 'clawdbot.*gateway' > /dev/null 2>&1 || pgrep -f 'node.*gateway' > /dev/null 2>&1"
SERVICES[clawdbot_start]="cd ~/clawd && nohup clawdbot gateway start > /tmp/clawdbot.out 2>&1 &"
SERVICES[clawdbot_stop]="clawdbot gateway stop 2>/dev/null || pkill -f 'clawdbot.*gateway'"
SERVICES[clawdbot_verify]="clawdbot gateway status 2>/dev/null | grep -qi 'running'"
SERVICES[clawdbot_desc]="Clawdbot Gateway Service"

#------------------------------------------------------------------------------
# Logging Functions
#------------------------------------------------------------------------------
setup_logging() {
    mkdir -p "$LOG_DIR"
    exec > >(tee -a "$LOG_FILE") 2>&1
}

log() {
    local level="$1"
    shift
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $*"
}

log_info()    { log "INFO" "$@"; }
log_warn()    { log "WARN" "$@"; }
log_error()   { log "ERROR" "$@"; }
log_success() { log "SUCCESS" "$@"; }
log_debug()   { $VERBOSE && log "DEBUG" "$@" || true; }
log_dry_run() { log "DRY-RUN" "$@"; }

#------------------------------------------------------------------------------
# Helper Functions
#------------------------------------------------------------------------------
show_help() {
    head -35 "$0" | grep -E "^#" | sed 's/^#//' | sed 's/^!//'
    exit 0
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --service)
                TARGET_SERVICE="$2"
                shift 2
                ;;
            --host)
                TARGET_HOST="$2"
                shift 2
                ;;
            --local)
                LOCAL_MODE=true
                shift
                ;;
            --max-retries)
                MAX_RETRIES="$2"
                shift 2
                ;;
            --wait-time)
                WAIT_TIME="$2"
                shift 2
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --help|-h)
                show_help
                ;;
            *)
                log_error "Unknown option: $1"
                exit 2
                ;;
        esac
    done
}

# Resolve host alias to IP
resolve_host() {
    case "$TARGET_HOST" in
        mac-mini|mini)
            echo "$MAC_MINI"
            ;;
        mac-pro|pro)
            echo "$MAC_PRO"
            ;;
        *)
            echo "$TARGET_HOST"
            ;;
    esac
}

# Execute command locally or via SSH
run_cmd() {
    local cmd="$1"
    if $LOCAL_MODE; then
        eval "$cmd"
    else
        local host=$(resolve_host)
        ssh -o ConnectTimeout=10 -o BatchMode=yes "$host" "$cmd"
    fi
}

# Test connectivity to target host
test_connection() {
    if $LOCAL_MODE; then
        return 0
    fi
    
    local host=$(resolve_host)
    log_debug "Testing connection to $host..."
    
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$host" "echo ok" > /dev/null 2>&1; then
        log_error "Cannot connect to $host"
        return 1
    fi
    
    log_debug "Connection successful"
    return 0
}

#------------------------------------------------------------------------------
# Service Check Functions
#------------------------------------------------------------------------------
check_service() {
    local service="$1"
    local check_cmd="${SERVICES[${service}_check]}"
    local desc="${SERVICES[${service}_desc]}"
    
    log_debug "Checking $desc..."
    
    if run_cmd "$check_cmd" 2>/dev/null; then
        log_info "âœ“ $desc is running"
        return 0
    else
        log_warn "âœ— $desc is NOT running"
        return 1
    fi
}

verify_service() {
    local service="$1"
    local verify_cmd="${SERVICES[${service}_verify]}"
    local desc="${SERVICES[${service}_desc]}"
    
    log_debug "Verifying $desc is responding..."
    
    if run_cmd "$verify_cmd" 2>/dev/null; then
        log_debug "  Service is responding correctly"
        return 0
    else
        log_debug "  Service not responding to verification check"
        return 1
    fi
}

#------------------------------------------------------------------------------
# Service Restart Functions
#------------------------------------------------------------------------------
stop_service() {
    local service="$1"
    local stop_cmd="${SERVICES[${service}_stop]}"
    local desc="${SERVICES[${service}_desc]}"
    
    log_info "Stopping $desc..."
    
    if $DRY_RUN; then
        log_dry_run "Would run: $stop_cmd"
        return 0
    fi
    
    run_cmd "$stop_cmd" 2>/dev/null || true
    sleep 2
    
    log_debug "Service stopped"
}

start_service() {
    local service="$1"
    local start_cmd="${SERVICES[${service}_start]}"
    local desc="${SERVICES[${service}_desc]}"
    
    log_info "Starting $desc..."
    
    if $DRY_RUN; then
        log_dry_run "Would run: $start_cmd"
        return 0
    fi
    
    run_cmd "$start_cmd" 2>/dev/null
    
    log_info "Waiting ${WAIT_TIME}s for service to initialize..."
    sleep "$WAIT_TIME"
}

restart_service() {
    local service="$1"
    local desc="${SERVICES[${service}_desc]}"
    local attempt=1
    
    log_info "Restarting $desc (max $MAX_RETRIES attempts)..."
    
    while [[ $attempt -le $MAX_RETRIES ]]; do
        log_info "Restart attempt $attempt of $MAX_RETRIES"
        
        # Stop the service first
        stop_service "$service"
        
        # Start the service
        start_service "$service"
        
        if $DRY_RUN; then
            log_dry_run "Would verify service is running"
            return 0
        fi
        
        # Verify it's running
        if check_service "$service" && verify_service "$service"; then
            log_success "âœ“ $desc restarted successfully!"
            return 0
        fi
        
        log_warn "Restart attempt $attempt failed"
        ((attempt++))
        
        if [[ $attempt -le $MAX_RETRIES ]]; then
            log_info "Waiting 5 seconds before next attempt..."
            sleep 5
        fi
    done
    
    log_error "âœ— Failed to restart $desc after $MAX_RETRIES attempts"
    return 1
}

#------------------------------------------------------------------------------
# Main Service Handler
#------------------------------------------------------------------------------
handle_service() {
    local service="$1"
    local desc="${SERVICES[${service}_desc]}"
    local status=0
    
    log_info "----------------------------------------------"
    log_info "Checking: $desc"
    log_info "----------------------------------------------"
    
    # Check if service is running
    if check_service "$service"; then
        # Service is running, verify it's responding
        if verify_service "$service"; then
            log_success "$desc is healthy"
            return 0
        else
            log_warn "$desc is running but not responding"
            log_info "Attempting restart..."
        fi
    fi
    
    # Service needs restart
    if ! restart_service "$service"; then
        return 1
    fi
    
    return 0
}

#------------------------------------------------------------------------------
# Report Generation
#------------------------------------------------------------------------------
generate_report() {
    local services_checked=("$@")
    
    log_info ""
    log_info "=============================================="
    log_info "SERVICE STATUS REPORT"
    log_info "=============================================="
    
    for service in "${services_checked[@]}"; do
        local desc="${SERVICES[${service}_desc]}"
        if check_service "$service" > /dev/null 2>&1; then
            log_info "âœ“ $desc: RUNNING"
        else
            log_error "âœ— $desc: DOWN"
        fi
    done
    
    log_info "=============================================="
}

#------------------------------------------------------------------------------
# Main Execution
#------------------------------------------------------------------------------
main() {
    parse_args "$@"
    setup_logging
    
    log_info "=============================================="
    log_info "$SCRIPT_NAME v$SCRIPT_VERSION"
    log_info "=============================================="
    
    # Validate host
    if ! $LOCAL_MODE && [[ -z "$TARGET_HOST" ]]; then
        log_error "No target host specified. Use --host or --local"
        exit 2
    fi
    
    if $LOCAL_MODE; then
        log_info "Running in local mode"
    else
        log_info "Target host: $(resolve_host)"
    fi
    
    $DRY_RUN && log_info "Mode: DRY RUN (no changes will be made)"
    
    # Test connection
    if ! test_connection; then
        exit 3
    fi
    
    # Determine which services to check
    local services_to_check=()
    case "$TARGET_SERVICE" in
        all)
            services_to_check=("ollama" "clawdbot")
            ;;
        ollama)
            services_to_check=("ollama")
            ;;
        clawdbot|gateway)
            services_to_check=("clawdbot")
            ;;
        *)
            log_error "Unknown service: $TARGET_SERVICE"
            log_error "Valid services: ollama, clawdbot, all"
            exit 2
            ;;
    esac
    
    log_info "Services to check: ${services_to_check[*]}"
    
    # Check/restart each service
    local overall_status=0
    for service in "${services_to_check[@]}"; do
        if ! handle_service "$service"; then
            overall_status=1
        fi
    done
    
    # Generate final report
    if ! $DRY_RUN; then
        generate_report "${services_to_check[@]}"
    fi
    
    log_info "Log saved to: $LOG_FILE"
    
    exit $overall_status
}

# Run main function
main "$@"
