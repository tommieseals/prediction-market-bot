#!/usr/bin/env bash
# OpenClaw Anomaly — Deploy RTX -> Jarvis
# Usage: bash openclaw/deploy.sh
#
# Syncs all Python + genome files, restarts dashboard, verifies.

set -e

JARVIS="administrator@100.89.75.126"
REMOTE_DIR="~/clawd/openclaw"
LOCAL_DIR="C:/Users/User/clawd/openclaw"

echo "=== OpenClaw Deploy: RTX -> Jarvis ==="

# 1. Run tests locally first
echo "[1/5] Running tests locally..."
cd "C:/Users/User/clawd"
python -m pytest openclaw/tests/ -q --tb=short || { echo "TESTS FAILED — aborting deploy"; exit 1; }

# 2. Sync Python files
echo "[2/5] Syncing Python files..."
for f in $(find "$LOCAL_DIR" -maxdepth 1 -name "*.py" -printf "%f\n" 2>/dev/null || ls "$LOCAL_DIR"/*.py 2>/dev/null | xargs -n1 basename); do
  scp -q "$LOCAL_DIR/$f" "$JARVIS:$REMOTE_DIR/$f"
done

# 3. Sync genome modules
echo "[3/5] Syncing genome modules..."
for f in $(ls "$LOCAL_DIR/genome/"*.md 2>/dev/null | xargs -n1 basename); do
  scp -q "$LOCAL_DIR/genome/$f" "$JARVIS:$REMOTE_DIR/genome/$f"
done

# 4. Sync test files
echo "[4/5] Syncing tests..."
for f in $(ls "$LOCAL_DIR/tests/"*.py 2>/dev/null | xargs -n1 basename); do
  scp -q "$LOCAL_DIR/tests/$f" "$JARVIS:$REMOTE_DIR/tests/$f"
done

# 5. Restart dashboard + verify
echo "[5/5] Restarting dashboard on Jarvis..."
ssh "$JARVIS" "
  pkill -f 'openclaw.main --mode=server' 2>/dev/null || true
  sleep 1
  cd ~/clawd && nohup /usr/local/bin/python3.13 -m openclaw.main --mode=server >> ~/logs/oge-dashboard.log 2>&1 &
  sleep 3
  /usr/local/bin/python3.13 -c 'import requests; r=requests.get(\"http://localhost:5201/api/status\",timeout=5); print(f\"Dashboard: {r.status_code} — Gen {r.json()[\"generation\"]}\")' 2>&1
  cd ~/clawd && /usr/local/bin/python3.13 -m pytest openclaw/tests/ -q --tb=short 2>&1 | tail -3
"

echo ""
echo "=== Deploy complete ==="
