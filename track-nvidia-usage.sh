#!/bin/bash
# NVIDIA API Usage Tracker
# Tracks daily API calls (50/day limit)

STATE_FILE="$HOME/dta/gateway/nvidia-usage-state.json"
TODAY=$(date +%Y-%m-%d)

# Initialize state file if missing
if [ ! -f "$STATE_FILE" ]; then
    echo '{"date": "'$TODAY'", "count": 0, "history": []}' > "$STATE_FILE"
fi

# Read current state
STORED_DATE=$(jq -r '.date' "$STATE_FILE")
STORED_COUNT=$(jq -r '.count' "$STATE_FILE")

# Reset if new day
if [ "$STORED_DATE" != "$TODAY" ]; then
    # Archive yesterday's count
    jq --arg date "$STORED_DATE" --argjson count "$STORED_COUNT" \
       '.history += [{"date": $date, "count": $count}] | .history |= .[-30:]' \
       "$STATE_FILE" > "$STATE_FILE.tmp"
    mv "$STATE_FILE.tmp" "$STATE_FILE"
    
    # Reset for new day
    jq --arg today "$TODAY" '.date = $today | .count = 0' "$STATE_FILE" > "$STATE_FILE.tmp"
    mv "$STATE_FILE.tmp" "$STATE_FILE"
    STORED_COUNT=0
fi

case "$1" in
    increment)
        NEW_COUNT=$((STORED_COUNT + 1))
        jq --argjson count "$NEW_COUNT" '.count = $count' "$STATE_FILE" > "$STATE_FILE.tmp"
        mv "$STATE_FILE.tmp" "$STATE_FILE"
        echo "Incremented: $NEW_COUNT/50 calls today"
        
        # Warn if approaching limit
        if [ "$NEW_COUNT" -ge 45 ]; then
            echo "⚠️ WARNING: Approaching daily limit ($NEW_COUNT/50)"
        elif [ "$NEW_COUNT" -ge 40 ]; then
            echo "⚠️ NOTICE: $NEW_COUNT/50 calls used today"
        fi
        ;;
        
    status)
        echo "NVIDIA API Usage - $TODAY"
        echo "Calls today: $STORED_COUNT/50"
        
        REMAINING=$((50 - STORED_COUNT))
        echo "Remaining: $REMAINING"
        
        if [ "$STORED_COUNT" -ge 45 ]; then
            echo "Status: ⚠️ CRITICAL - Approaching limit!"
        elif [ "$STORED_COUNT" -ge 40 ]; then
            echo "Status: ⚠️ WARNING - Use conservatively"
        else
            echo "Status: ✅ OK"
        fi
        
        # Show last 7 days
        echo ""
        echo "Last 7 days:"
        jq -r '.history[-7:] | .[] | "\(.date): \(.count) calls"' "$STATE_FILE"
        ;;
        
    reset)
        jq --arg today "$TODAY" '.date = $today | .count = 0' "$STATE_FILE" > "$STATE_FILE.tmp"
        mv "$STATE_FILE.tmp" "$STATE_FILE"
        echo "Reset counter for $TODAY"
        ;;
        
    *)
        echo "Usage: $0 {increment|status|reset}"
        echo ""
        echo "Commands:"
        echo "  increment  - Add 1 to today's count"
        echo "  status     - Show current usage"
        echo "  reset      - Reset today's counter"
        exit 1
        ;;
esac
