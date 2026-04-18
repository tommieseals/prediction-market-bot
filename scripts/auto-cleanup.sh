#!/bin/bash
#==============================================================================
# AUTO-CLEANUP.SH - Automated Disk Cleanup Script
#==============================================================================
# Purpose: Cleans logs and temp files when disk usage exceeds threshold
# Target:  Mac Mini (100.88.105.106) / Mac Pro (100.86.80.74) via SSH
# Usage:   ./auto-cleanup.sh [OPTIONS]
#
# Options:
#   --dry-run     Show what would be deleted without actually deleting
#   --force       Skip confirmation prompts
#   --threshold N Set disk usage threshold (default: 80)
#   --host HOST   Target host (mac-mini, mac-pro, or IP address)
#   --local       Run locally instead of via SSH
#   --verbose     Show detailed output
#   --help        Show this help message
#
# Exit Codes:
#   0 - Success (cleanup performed or not needed)
#   1 - Error during cleanup
#   2 - Invalid arguments
#==============================================================================

set -euo pipefail

#------------------------------------------------------------------------------
# Configuration
#------------------------------------------------------------------------------
SCRIPT_NAME="auto-cleanup"
SCRIPT_VERSION="1.0.0"
LOG_DIR="${LOG_DIR:-/tmp/clawd-remediation}"
LOG_FILE="${LOG_DIR}/${SCRIPT_NAME}-$(date +%Y%m%d).log"
THRESHOLD=80
DRY_RUN=false
FORCE=false
VERBOSE=false
LOCAL_MODE=false
TARGET_HOST=""

# Default hosts (from TOOLS.md)
MAC_MINI="100.88.105.106"
MAC_PRO="100.86.80.74"

#------------------------------------------------------------------------------
# Cleanup Targets - Paths that are safe to clean
# Each entry: "path:max_age_days:description"
#------------------------------------------------------------------------------
CLEANUP_TARGETS=(
    "/tmp/*:7:Temp files older than 7 days"
    "/var/log/*.log.*:30:Rotated log files older than 30 days"
    "/var/log/*/*.log.*:30:Nested rotated logs older than 30 days"
    "~/.cache/*:14:User cache older than 14 days"
    "~/Library/Caches/*:14:macOS app caches older than 14 days"
    "~/Library/Logs/*:30:Application logs older than 30 days"
    "/private/var/folders/*/*/com.apple.Safari/fsCachedData/*:7:Safari cache"
    "~/.ollama/models/.tmp/*:1:Ollama temp model files"
)

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
log_debug()   { $VERBOSE && log "DEBUG" "$@" || true; }
log_dry_run() { log "DRY-RUN" "$@"; }

#------------------------------------------------------------------------------
# Helper Functions
#------------------------------------------------------------------------------
show_help() {
    head -30 "$0" | grep -E "^#" | sed 's/^#//' | sed 's/^!//'
    exit 0
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --threshold)
                THRESHOLD="$2"
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

#------------------------------------------------------------------------------
# Disk Check Functions
#------------------------------------------------------------------------------
get_disk_usage() {
    # Returns disk usage percentage for root filesystem
    # More portable version that works on both macOS and Linux
    run_cmd "df / | awk 'NR==2 {print \$5}' | tr -d '%'"
}

check_disk_threshold() {
    local usage=$(get_disk_usage)
    
    # Validate we got a number
    if [[ -z "$usage" || ! "$usage" =~ ^[0-9]+$ ]]; then
        log_error "Failed to get disk usage from target (got: '$usage')"
        exit 1
    fi
    
    log_info "Current disk usage: ${usage}% (threshold: ${THRESHOLD}%)"
    
    if [[ $usage -lt $THRESHOLD ]]; then
        log_info "Disk usage below threshold. No cleanup needed."
        return 1
    fi
    
    log_warn "Disk usage exceeds threshold! Cleanup required."
    return 0
}

#------------------------------------------------------------------------------
# Cleanup Functions
#------------------------------------------------------------------------------
calculate_space_to_free() {
    local target_path="$1"
    local max_age="$2"
    
    # Expand ~ to home directory
    local expanded_path=$(run_cmd "echo $target_path")
    
    # Calculate size of files that would be deleted
    local cmd="find $expanded_path -type f -mtime +$max_age -exec du -ch {} + 2>/dev/null | tail -1 | cut -f1 || echo '0'"
    run_cmd "$cmd" 2>/dev/null || echo "0"
}

cleanup_path() {
    local target_path="$1"
    local max_age="$2"
    local description="$3"
    
    log_info "Processing: $description"
    log_debug "  Path: $target_path, Max age: $max_age days"
    
    # Expand ~ to home directory
    local expanded_path=$(run_cmd "echo $target_path")
    
    # Count files that would be deleted
    local count_cmd="find $expanded_path -type f -mtime +$max_age 2>/dev/null | wc -l | tr -d ' '"
    local file_count=$(run_cmd "$count_cmd" 2>/dev/null || echo "0")
    
    if [[ "$file_count" == "0" || -z "$file_count" ]]; then
        log_debug "  No matching files found"
        return 0
    fi
    
    # Calculate space
    local space=$(calculate_space_to_free "$target_path" "$max_age")
    
    log_info "  Found $file_count files ($space) to clean"
    
    if $DRY_RUN; then
        log_dry_run "Would delete $file_count files from $expanded_path (older than $max_age days)"
        # List first 10 files in verbose mode
        if $VERBOSE; then
            local list_cmd="find $expanded_path -type f -mtime +$max_age 2>/dev/null | head -10"
            run_cmd "$list_cmd" 2>/dev/null | while read -r file; do
                log_dry_run "  Would delete: $file"
            done
        fi
    else
        # Actually delete files
        local delete_cmd="find $expanded_path -type f -mtime +$max_age -delete 2>/dev/null; echo \$?"
        local result=$(run_cmd "$delete_cmd")
        
        if [[ "$result" == "0" ]]; then
            log_info "  âœ“ Cleaned $file_count files ($space freed)"
        else
            log_warn "  âš  Some files could not be deleted (permission denied?)"
        fi
    fi
}

run_cleanup() {
    log_info "Starting cleanup process..."
    
    local before_usage=$(get_disk_usage)
    
    for target in "${CLEANUP_TARGETS[@]}"; do
        IFS=':' read -r path max_age description <<< "$target"
        cleanup_path "$path" "$max_age" "$description"
    done
    
    # Additional cleanup: empty trash (macOS)
    if $DRY_RUN; then
        log_dry_run "Would empty Trash"
    else
        local trash_cmd="rm -rf ~/.Trash/* 2>/dev/null || true"
        run_cmd "$trash_cmd"
        log_info "Emptied Trash"
    fi
    
    # Show results
    if ! $DRY_RUN; then
        local after_usage=$(get_disk_usage)
        local freed=$((before_usage - after_usage))
        log_info "Cleanup complete!"
        log_info "  Before: ${before_usage}%"
        log_info "  After:  ${after_usage}%"
        log_info "  Freed:  ${freed}% disk space"
    else
        log_dry_run "Dry run complete. No files were deleted."
    fi
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
    
    # Check if cleanup is needed
    if ! $FORCE; then
        if ! check_disk_threshold; then
            exit 0
        fi
    else
        log_info "Force mode: skipping threshold check"
    fi
    
    # Run cleanup
    run_cleanup
    
    log_info "=============================================="
    log_info "Log saved to: $LOG_FILE"
}

# Run main function
main "$@"
