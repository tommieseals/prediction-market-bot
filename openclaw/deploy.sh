#!/usr/bin/env bash
# OpenClaw Anomaly - Deploy RTX -> Jarvis
# Usage: bash openclaw/deploy.sh
#
# Syncs Python, shell helpers, genome files, restarts dashboard, verifies Jarvis-first readiness.

set -e

JARVIS="administrator@100.89.75.126"
REMOTE_DIR="~/clawd/openclaw"
LOCAL_DIR="C:/Users/User/clawd/openclaw"

echo "=== OpenClaw Deploy: RTX -> Jarvis ==="

# 1. Run tests locally first
echo "[1/7] Running tests locally..."
cd "C:/Users/User/clawd"
python -m pytest openclaw/tests/ -q --tb=short || { echo "TESTS FAILED - aborting deploy"; exit 1; }

# 2. Verify Jarvis-first merge readiness locally
echo "[2/7] Verifying Jarvis-first merge readiness..."
python -m openclaw.jarvis_merge_check || { echo "MERGE READINESS FAILED - aborting deploy"; exit 1; }

# 3. Sync Python files
echo "[3/7] Syncing Python files..."
for f in $(find "$LOCAL_DIR" -maxdepth 1 -name "*.py" -printf "%f\n" 2>/dev/null || ls "$LOCAL_DIR"/*.py 2>/dev/null | xargs -n1 basename); do
  scp -q "$LOCAL_DIR/$f" "$JARVIS:$REMOTE_DIR/$f"
done

# 4. Sync shell helpers
echo "[4/7] Syncing shell helpers..."
for f in $(find "$LOCAL_DIR" -maxdepth 1 -name "*.sh" -printf "%f\n" 2>/dev/null || ls "$LOCAL_DIR"/*.sh 2>/dev/null | xargs -n1 basename); do
  scp -q "$LOCAL_DIR/$f" "$JARVIS:$REMOTE_DIR/$f"
done

# 5. Sync genome modules
echo "[5/7] Syncing genome modules..."
for f in $(ls "$LOCAL_DIR/genome/"*.md 2>/dev/null | xargs -n1 basename); do
  scp -q "$LOCAL_DIR/genome/$f" "$JARVIS:$REMOTE_DIR/genome/$f"
done

# 6. Sync test files
echo "[6/7] Syncing tests..."
for f in $(ls "$LOCAL_DIR/tests/"*.py 2>/dev/null | xargs -n1 basename); do
  scp -q "$LOCAL_DIR/tests/$f" "$JARVIS:$REMOTE_DIR/tests/$f"
done

# 7. Restart dashboard + verify
echo "[7/7] Restarting dashboard on Jarvis..."
ssh "$JARVIS" "
  chmod +x $REMOTE_DIR/*.sh 2>/dev/null || true
  pkill -f 'openclaw.main --mode=server' 2>/dev/null || true
  sleep 1
  cd ~/clawd && nohup /usr/local/bin/python3.13 -m openclaw.main --mode=server >> ~/logs/oge-dashboard.log 2>&1 &
  sleep 3
  /usr/local/bin/python3.13 -c 'import requests, json; r=requests.get(\"http://localhost:5201/api/status\",timeout=5); data=r.json(); print(json.dumps({\"status\": r.status_code, \"generation\": data.get(\"generation\"), \"routing_summary\": data.get(\"routing_summary\", {})}, indent=2))' 2>&1
  cd ~/clawd && /usr/local/bin/python3.13 -m openclaw.jarvis_merge_check 2>&1
  cd ~/clawd && /usr/local/bin/python3.13 -m pytest openclaw/tests/ -q --tb=short 2>&1 | tail -3
"

echo ""
echo "=== Deploy complete ==="
