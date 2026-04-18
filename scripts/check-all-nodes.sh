#!/bin/bash
# check-all-nodes.sh - Efficient all-node health check (single SSH multiplexed)
# Batches commands to reduce connection overhead

echo "=== Infrastructure Health Check $(date) ==="
echo ""

# Mac Mini - batch all checks in one SSH call
echo "ðŸ“ MAC MINI (100.88.105.106)"
ssh -o ConnectTimeout=10 tommie@100.88.105.106 '
  # RAM
  FREE_PCT=$(memory_pressure 2>/dev/null | grep "System-wide memory free percentage" | awk "{print \$NF}" | tr -d "%")
  if [ -z "$FREE_PCT" ]; then FREE_PCT="??"; fi
  RAM_USED=$((100 - FREE_PCT))
  
  # Disk
  DISK=$(df -h / | tail -1 | awk "{print \$5}" | tr -d "%")
  
  # Load
  LOAD=$(uptime | awk -F"load averages?: " "{print \$2}" | awk "{print \$1}" | tr -d ",")
  
  # Services
  OLLAMA=$(pgrep -x ollama >/dev/null && echo "âœ…" || echo "âŒ")
  CLAWDBOT=$(pgrep -f clawdbot-gateway >/dev/null && echo "âœ…" || echo "âŒ")
  
  echo "  RAM: ${RAM_USED}% used | Disk: ${DISK}% | Load: ${LOAD}"
  echo "  Services: Ollama $OLLAMA | Clawdbot $CLAWDBOT"
' 2>/dev/null || echo "  âŒ UNREACHABLE"

echo ""

# Mac Pro - batch all checks in one SSH call
echo "ðŸ“ MAC PRO (100.86.80.74)"
ssh -o ConnectTimeout=10 administrator@100.86.80.74 '
  # RAM (Mac Pro has different memory_pressure output sometimes)
  FREE_PCT=$(memory_pressure 2>/dev/null | grep "System-wide memory free percentage" | awk "{print \$NF}" | tr -d "%")
  if [ -z "$FREE_PCT" ]; then FREE_PCT="??"; fi
  RAM_USED=$((100 - FREE_PCT))
  
  # Disk
  DISK=$(df -h / | tail -1 | awk "{print \$5}" | tr -d "%")
  
  # Load
  LOAD=$(uptime | awk -F"load averages?: " "{print \$2}" | awk "{print \$1}" | tr -d ",")
  
  # Services
  OLLAMA=$(pgrep -x ollama >/dev/null && echo "âœ…" || echo "âŒ")
  OPENCLAW=$(pgrep -f openclaw >/dev/null && echo "âœ…" || echo "âŒ")
  
  echo "  RAM: ${RAM_USED}% used | Disk: ${DISK}% | Load: ${LOAD}"
  echo "  Services: Ollama $OLLAMA | OpenClaw $OPENCLAW"
' 2>/dev/null || echo "  âŒ UNREACHABLE"

echo ""
echo "ðŸ“ DELL (local - 100.119.87.108)"
echo "  (Check via PowerShell separately on Windows)"
echo ""
echo "=== Check Complete ==="
