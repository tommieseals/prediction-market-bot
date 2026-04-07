#!/bin/bash
# =============================================================================
# Enhanced Clawd Infrastructure Health Monitor
# =============================================================================
# Monitors all 3 nodes: Dell (local), Mac Mini, Mac Pro
# Checks: RAM, Disk, Load, Services (ollama, clawdbot, docker)
# Returns exit code 1 if any threshold exceeded
# =============================================================================

set -o pipefail

# Configuration
THRESHOLD_RAM=85
THRESHOLD_DISK=80
THRESHOLD_LOAD=4

# Node definitions
declare -A NODES=(
    ["Dell"]="local"
    ["Mac-Mini"]="100.88.105.106"
    ["Mac-Pro"]="100.89.75.126"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Track alerts
ALERTS=()
EXIT_CODE=0

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

print_header() {
    echo -e "\n${BOLD}${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${BLUE}║        CLAWD INFRASTRUCTURE HEALTH MONITOR                   ║${NC}"
    echo -e "${BOLD}${BLUE}║        $(date '+%Y-%m-%d %H:%M:%S')                              ║${NC}"
    echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}\n"
}

status_icon() {
    local value=$1
    local threshold=$2
    if (( $(echo "$value >= $threshold" | bc -l 2>/dev/null || echo "0") )); then
        echo -e "${RED}✗${NC}"
    else
        echo -e "${GREEN}✓${NC}"
    fi
}

format_percent() {
    local value=$1
    local threshold=$2
    if (( $(echo "$value >= $threshold" | bc -l 2>/dev/null || echo "0") )); then
        echo -e "${RED}${value}%${NC}"
    elif (( $(echo "$value >= $threshold * 0.8" | bc -l 2>/dev/null || echo "0") )); then
        echo -e "${YELLOW}${value}%${NC}"
    else
        echo -e "${GREEN}${value}%${NC}"
    fi
}

format_load() {
    local value=$1
    if (( $(echo "$value >= $THRESHOLD_LOAD" | bc -l 2>/dev/null || echo "0") )); then
        echo -e "${RED}${value}${NC}"
    elif (( $(echo "$value >= $THRESHOLD_LOAD * 0.75" | bc -l 2>/dev/null || echo "0") )); then
        echo -e "${YELLOW}${value}${NC}"
    else
        echo -e "${GREEN}${value}${NC}"
    fi
}

service_status() {
    local running=$1
    if [[ "$running" == "true" || "$running" == "1" ]]; then
        echo -e "${GREEN}●${NC}"
    else
        echo -e "${RED}○${NC}"
    fi
}

# -----------------------------------------------------------------------------
# Windows/Dell Local Checks
# -----------------------------------------------------------------------------

check_dell_local() {
    [[ "$QUIET" != "true" ]] && echo -e "${BOLD}Checking Dell (local)...${NC}"
    
    local ram_pct disk_pct load_avg
    local ollama_running=false clawdbot_running=false docker_running=false
    
    # RAM usage (PowerShell - NoProfile to avoid profile output leaking)
    ram_pct=$(powershell.exe -NoProfile -Command "
        \$os = Get-CimInstance Win32_OperatingSystem
        [math]::Round((\$os.TotalVisibleMemorySize - \$os.FreePhysicalMemory) / \$os.TotalVisibleMemorySize * 100, 1)
    " 2>/dev/null | tr -d '\r' | tail -1)
    
    # Disk usage (PowerShell - C: drive)
    disk_pct=$(powershell.exe -NoProfile -Command "
        \$disk = Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\"
        [math]::Round((\$disk.Size - \$disk.FreeSpace) / \$disk.Size * 100, 1)
    " 2>/dev/null | tr -d '\r' | tail -1)
    
    # CPU Load (approximate via queue length)
    load_avg=$(powershell.exe -NoProfile -Command "
        \$load = (Get-Counter '\System\Processor Queue Length' -ErrorAction SilentlyContinue).CounterSamples[0].CookedValue
        if (\$load) { [math]::Round(\$load, 2) } else { '0.0' }
    " 2>/dev/null | tr -d '\r' | tail -1)
    [[ -z "$load_avg" ]] && load_avg="0.0"
    
    # Service checks (PowerShell)
    ollama_running=$(powershell.exe -NoProfile -Command "
        if (Get-Process ollama -ErrorAction SilentlyContinue) { 'true' } else { 'false' }
    " 2>/dev/null | tr -d '\r' | tail -1)
    
    clawdbot_running=$(powershell.exe -NoProfile -Command "
        if (Get-Process -Name '*clawdbot*' -ErrorAction SilentlyContinue) { 'true' } 
        elseif (Get-Process node -ErrorAction SilentlyContinue | Where-Object { \$_.CommandLine -like '*clawdbot*' }) { 'true' }
        else { 'false' }
    " 2>/dev/null | tr -d '\r' | tail -1)
    
    docker_running=$(powershell.exe -NoProfile -Command "
        if (Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue) { 'true' }
        elseif (Get-Process dockerd -ErrorAction SilentlyContinue) { 'true' }
        else { 'false' }
    " 2>/dev/null | tr -d '\r' | tail -1)
    
    # Store results
    DELL_RAM="$ram_pct"
    DELL_DISK="$disk_pct"
    DELL_LOAD="$load_avg"
    DELL_OLLAMA="$ollama_running"
    DELL_CLAWDBOT="$clawdbot_running"
    DELL_DOCKER="$docker_running"
    
    # Check thresholds
    if (( $(echo "${ram_pct:-0} >= $THRESHOLD_RAM" | bc -l 2>/dev/null || echo 0) )); then
        ALERTS+=("Dell RAM: ${ram_pct}% (threshold: ${THRESHOLD_RAM}%)")
        EXIT_CODE=1
    fi
    if (( $(echo "${disk_pct:-0} >= $THRESHOLD_DISK" | bc -l 2>/dev/null || echo 0) )); then
        ALERTS+=("Dell Disk: ${disk_pct}% (threshold: ${THRESHOLD_DISK}%)")
        EXIT_CODE=1
    fi
    if (( $(echo "${load_avg:-0} >= $THRESHOLD_LOAD" | bc -l 2>/dev/null || echo 0) )); then
        ALERTS+=("Dell Load: ${load_avg} (threshold: ${THRESHOLD_LOAD})")
        EXIT_CODE=1
    fi
}

# -----------------------------------------------------------------------------
# Mac Remote Checks (Single SSH Session)
# -----------------------------------------------------------------------------

check_mac_remote() {
    local name=$1
    local host=$2
    
    [[ "$QUIET" != "true" ]] && echo -e "${BOLD}Checking ${name} (${host})...${NC}"
    
    # Combined command to get all metrics in one SSH session
    local result
    result=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$host" bash << 'REMOTE_SCRIPT' 2>/dev/null
# RAM usage
ram_total=$(sysctl -n hw.memsize 2>/dev/null)
if [[ -n "$ram_total" ]]; then
    # Get page size and VM stats
    page_size=$(sysctl -n hw.pagesize)
    vm_stat_output=$(vm_stat)
    pages_free=$(echo "$vm_stat_output" | grep "Pages free" | awk '{print $3}' | tr -d '.')
    pages_inactive=$(echo "$vm_stat_output" | grep "Pages inactive" | awk '{print $3}' | tr -d '.')
    pages_speculative=$(echo "$vm_stat_output" | grep "Pages speculative" | awk '{print $3}' | tr -d '.')
    
    free_bytes=$(( (pages_free + pages_inactive + pages_speculative) * page_size ))
    used_bytes=$(( ram_total - free_bytes ))
    ram_pct=$(echo "scale=1; $used_bytes * 100 / $ram_total" | bc)
else
    ram_pct="N/A"
fi

# Disk usage (root volume)
disk_pct=$(df -h / | tail -1 | awk '{print $5}' | tr -d '%')

# Load average (1 min)
load_avg=$(sysctl -n vm.loadavg | awk '{print $2}')

# Services
ollama_running=$(pgrep -x ollama >/dev/null 2>&1 && echo "true" || echo "false")
clawdbot_running=$(pgrep -f "clawdbot" >/dev/null 2>&1 && echo "true" || echo "false")
docker_running=$(pgrep -x Docker >/dev/null 2>&1 || pgrep -x dockerd >/dev/null 2>&1 && echo "true" || echo "false")

# Output as parseable format
echo "RAM:${ram_pct}"
echo "DISK:${disk_pct}"
echo "LOAD:${load_avg}"
echo "OLLAMA:${ollama_running}"
echo "CLAWDBOT:${clawdbot_running}"
echo "DOCKER:${docker_running}"
REMOTE_SCRIPT
)
    
    if [[ -z "$result" ]]; then
        [[ "$QUIET" != "true" ]] && echo -e "${RED}  Failed to connect to ${name}${NC}"
        eval "${name//-/_}_RAM='N/A'"
        eval "${name//-/_}_DISK='N/A'"
        eval "${name//-/_}_LOAD='N/A'"
        eval "${name//-/_}_OLLAMA='false'"
        eval "${name//-/_}_CLAWDBOT='false'"
        eval "${name//-/_}_DOCKER='false'"
        ALERTS+=("${name}: Connection failed")
        EXIT_CODE=1
        return
    fi
    
    # Parse results
    local ram_pct disk_pct load_avg ollama_running clawdbot_running docker_running
    ram_pct=$(echo "$result" | grep "^RAM:" | cut -d: -f2)
    disk_pct=$(echo "$result" | grep "^DISK:" | cut -d: -f2)
    load_avg=$(echo "$result" | grep "^LOAD:" | cut -d: -f2)
    ollama_running=$(echo "$result" | grep "^OLLAMA:" | cut -d: -f2)
    clawdbot_running=$(echo "$result" | grep "^CLAWDBOT:" | cut -d: -f2)
    docker_running=$(echo "$result" | grep "^DOCKER:" | cut -d: -f2)
    
    # Store based on node name
    local var_prefix="${name//-/_}"
    eval "${var_prefix}_RAM='$ram_pct'"
    eval "${var_prefix}_DISK='$disk_pct'"
    eval "${var_prefix}_LOAD='$load_avg'"
    eval "${var_prefix}_OLLAMA='$ollama_running'"
    eval "${var_prefix}_CLAWDBOT='$clawdbot_running'"
    eval "${var_prefix}_DOCKER='$docker_running'"
    
    # Check thresholds
    if [[ "$ram_pct" != "N/A" ]] && (( $(echo "$ram_pct >= $THRESHOLD_RAM" | bc -l 2>/dev/null || echo 0) )); then
        ALERTS+=("${name} RAM: ${ram_pct}% (threshold: ${THRESHOLD_RAM}%)")
        EXIT_CODE=1
    fi
    if [[ "$disk_pct" != "N/A" ]] && (( $(echo "$disk_pct >= $THRESHOLD_DISK" | bc -l 2>/dev/null || echo 0) )); then
        ALERTS+=("${name} Disk: ${disk_pct}% (threshold: ${THRESHOLD_DISK}%)")
        EXIT_CODE=1
    fi
    if [[ "$load_avg" != "N/A" ]] && (( $(echo "$load_avg >= $THRESHOLD_LOAD" | bc -l 2>/dev/null || echo 0) )); then
        ALERTS+=("${name} Load: ${load_avg} (threshold: ${THRESHOLD_LOAD})")
        EXIT_CODE=1
    fi
}

# -----------------------------------------------------------------------------
# NVIDIA API Usage Check
# -----------------------------------------------------------------------------

check_nvidia_usage() {
    [[ "$QUIET" != "true" ]] && echo -e "${BOLD}Checking NVIDIA API usage...${NC}"
    
    local gateway_dir="$HOME/dta/gateway"
    local log_file="${gateway_dir}/nvidia_usage.log"
    local usage_file="${gateway_dir}/.nvidia_daily_usage"
    
    NVIDIA_USED="N/A"
    NVIDIA_LIMIT="50"
    NVIDIA_REMAINING="N/A"
    
    # Try to find usage from log or tracking file
    if [[ -f "$usage_file" ]]; then
        local today=$(date +%Y-%m-%d)
        local usage_line=$(grep "^${today}:" "$usage_file" 2>/dev/null | tail -1)
        if [[ -n "$usage_line" ]]; then
            NVIDIA_USED=$(echo "$usage_line" | cut -d: -f2)
            NVIDIA_REMAINING=$((NVIDIA_LIMIT - NVIDIA_USED))
        fi
    fi
    
    # Alternative: check logs for today's API calls
    if [[ "$NVIDIA_USED" == "N/A" ]] && [[ -d "$gateway_dir" ]]; then
        local today=$(date +%Y-%m-%d)
        # Count NVIDIA API calls in logs
        local count=$(grep -l "$today" "${gateway_dir}"/*.log 2>/dev/null | xargs grep -c "nvidia\|llama\|kimi\|qwen_coder" 2>/dev/null | awk -F: '{sum+=$2} END {print sum}')
        if [[ -n "$count" && "$count" != "0" ]]; then
            NVIDIA_USED="~${count}"
            NVIDIA_REMAINING="~$((NVIDIA_LIMIT - count))"
        fi
    fi
    
    # If still N/A, check via script if available
    if [[ "$NVIDIA_USED" == "N/A" ]] && [[ -x "${gateway_dir}/llm-usage" ]]; then
        local usage_output=$("${gateway_dir}/llm-usage" 2>/dev/null)
        if [[ -n "$usage_output" ]]; then
            NVIDIA_USED=$(echo "$usage_output" | grep -i "nvidia\|used" | grep -oE '[0-9]+' | head -1)
            [[ -n "$NVIDIA_USED" ]] && NVIDIA_REMAINING=$((NVIDIA_LIMIT - NVIDIA_USED))
        fi
    fi
}

# -----------------------------------------------------------------------------
# Print Summary Table
# -----------------------------------------------------------------------------

print_summary() {
    echo -e "\n${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}                     HEALTH SUMMARY                             ${NC}"
    echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}\n"
    
    # Table header
    printf "%-12s │ %8s │ %8s │ %8s │ %7s │ %8s │ %7s\n" \
        "Node" "RAM" "Disk" "Load" "Ollama" "Clawdbot" "Docker"
    echo "─────────────┼──────────┼──────────┼──────────┼─────────┼──────────┼────────"
    
    # Dell
    printf "%-12s │ " "Dell"
    printf "%s │ " "$(format_percent "${DELL_RAM:-N/A}" $THRESHOLD_RAM)"
    printf "%s │ " "$(format_percent "${DELL_DISK:-N/A}" $THRESHOLD_DISK)"
    printf "%s │ " "$(format_load "${DELL_LOAD:-0}")"
    printf "   %s   │ " "$(service_status "${DELL_OLLAMA:-false}")"
    printf "    %s    │ " "$(service_status "${DELL_CLAWDBOT:-false}")"
    printf "   %s\n" "$(service_status "${DELL_DOCKER:-false}")"
    
    # Mac Mini
    printf "%-12s │ " "Mac-Mini"
    printf "%s │ " "$(format_percent "${Mac_Mini_RAM:-N/A}" $THRESHOLD_RAM)"
    printf "%s │ " "$(format_percent "${Mac_Mini_DISK:-N/A}" $THRESHOLD_DISK)"
    printf "%s │ " "$(format_load "${Mac_Mini_LOAD:-0}")"
    printf "   %s   │ " "$(service_status "${Mac_Mini_OLLAMA:-false}")"
    printf "    %s    │ " "$(service_status "${Mac_Mini_CLAWDBOT:-false}")"
    printf "   %s\n" "$(service_status "${Mac_Mini_DOCKER:-false}")"
    
    # Mac Pro
    printf "%-12s │ " "Mac-Pro"
    printf "%s │ " "$(format_percent "${Mac_Pro_RAM:-N/A}" $THRESHOLD_RAM)"
    printf "%s │ " "$(format_percent "${Mac_Pro_DISK:-N/A}" $THRESHOLD_DISK)"
    printf "%s │ " "$(format_load "${Mac_Pro_LOAD:-0}")"
    printf "   %s   │ " "$(service_status "${Mac_Pro_OLLAMA:-false}")"
    printf "    %s    │ " "$(service_status "${Mac_Pro_CLAWDBOT:-false}")"
    printf "   %s\n" "$(service_status "${Mac_Pro_DOCKER:-false}")"
    
    echo ""
    
    # NVIDIA API Usage
    echo -e "${BOLD}NVIDIA API Usage:${NC} ${NVIDIA_USED:-N/A}/${NVIDIA_LIMIT} calls today (${NVIDIA_REMAINING:-N/A} remaining)"
    
    # Thresholds reminder
    echo -e "\n${BOLD}Thresholds:${NC} RAM >${THRESHOLD_RAM}% │ Disk >${THRESHOLD_DISK}% │ Load >${THRESHOLD_LOAD}"
    echo -e "${BOLD}Legend:${NC} ${GREEN}●${NC} Running │ ${RED}○${NC} Stopped │ ${GREEN}✓${NC} OK │ ${YELLOW}⚠${NC} Warning │ ${RED}✗${NC} Critical"
    
    # Alerts section
    if [[ ${#ALERTS[@]} -gt 0 ]]; then
        echo -e "\n${BOLD}${RED}═══════════════════════════════════════════════════════════════${NC}"
        echo -e "${BOLD}${RED}                         ALERTS                                ${NC}"
        echo -e "${BOLD}${RED}═══════════════════════════════════════════════════════════════${NC}"
        for alert in "${ALERTS[@]}"; do
            echo -e "${RED}  ⚠ ${alert}${NC}"
        done
    else
        echo -e "\n${GREEN}✓ All systems healthy - no alerts${NC}"
    fi
    
    echo ""
}

# -----------------------------------------------------------------------------
# JSON Output (for programmatic use)
# -----------------------------------------------------------------------------

output_json() {
    # Helper to convert N/A to null for JSON
    json_num() {
        local val="$1"
        if [[ "$val" == "N/A" || -z "$val" ]]; then
            echo "null"
        else
            echo "$val"
        fi
    }
    
    cat << EOF
{
  "timestamp": "$(date -Iseconds)",
  "nodes": {
    "dell": {
      "ram_percent": $(json_num "$DELL_RAM"),
      "disk_percent": $(json_num "$DELL_DISK"),
      "load_avg": $(json_num "$DELL_LOAD"),
      "services": {
        "ollama": ${DELL_OLLAMA:-false},
        "clawdbot": ${DELL_CLAWDBOT:-false},
        "docker": ${DELL_DOCKER:-false}
      }
    },
    "mac_mini": {
      "ram_percent": $(json_num "$Mac_Mini_RAM"),
      "disk_percent": $(json_num "$Mac_Mini_DISK"),
      "load_avg": $(json_num "$Mac_Mini_LOAD"),
      "services": {
        "ollama": ${Mac_Mini_OLLAMA:-false},
        "clawdbot": ${Mac_Mini_CLAWDBOT:-false},
        "docker": ${Mac_Mini_DOCKER:-false}
      }
    },
    "mac_pro": {
      "ram_percent": $(json_num "$Mac_Pro_RAM"),
      "disk_percent": $(json_num "$Mac_Pro_DISK"),
      "load_avg": $(json_num "$Mac_Pro_LOAD"),
      "services": {
        "ollama": ${Mac_Pro_OLLAMA:-false},
        "clawdbot": ${Mac_Pro_CLAWDBOT:-false},
        "docker": ${Mac_Pro_DOCKER:-false}
      }
    }
  },
  "nvidia_api": {
    "used": "${NVIDIA_USED:-N/A}",
    "limit": ${NVIDIA_LIMIT},
    "remaining": "${NVIDIA_REMAINING:-N/A}"
  },
  "alerts": [$(printf '"%s",' "${ALERTS[@]}" | sed 's/,$//')],
  "healthy": $([ $EXIT_CODE -eq 0 ] && echo "true" || echo "false")
}
EOF
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

main() {
    local json_mode=false
    local quiet_mode=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --json|-j)
                json_mode=true
                shift
                ;;
            --quiet|-q)
                quiet_mode=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  -j, --json    Output in JSON format"
                echo "  -q, --quiet   Suppress progress messages"
                echo "  -h, --help    Show this help"
                echo ""
                echo "Exit codes:"
                echo "  0 = All healthy"
                echo "  1 = One or more thresholds exceeded"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # JSON mode implies quiet
    [[ "$json_mode" == "true" ]] && quiet_mode=true
    
    # Export for child functions
    [[ "$quiet_mode" == "true" ]] && QUIET="true" || QUIET="false"
    
    [[ "$quiet_mode" == "false" ]] && print_header
    
    # Run checks
    [[ "$quiet_mode" == "false" ]] && echo -e "${BOLD}Running health checks...${NC}\n"
    
    check_dell_local
    check_mac_remote "Mac-Mini" "tommie@100.88.105.106"
    check_mac_remote "Mac-Pro" "administrator@100.89.75.126"
    check_nvidia_usage
    
    # Output results
    if [[ "$json_mode" == "true" ]]; then
        output_json
    else
        print_summary
    fi
    
    exit $EXIT_CODE
}

main "$@"
