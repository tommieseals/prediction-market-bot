#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
if [[ -z "$MODE" ]]; then
  echo "Usage: bash openclaw/jarvis_task_runner.sh <proactive|morning-pulse|meta|eval|maintain>" >&2
  exit 1
fi

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/clawd}"
PYTHON_BIN="${PYTHON_BIN:-/usr/local/bin/python3.13}"
LOG_DIR="$PROJECT_ROOT/openclaw/audits/task-runs"

mkdir -p "$LOG_DIR"
cd "$PROJECT_ROOT"

timestamp="$(date +%Y%m%d_%H%M%S)"
log_file="$LOG_DIR/${MODE}-${timestamp}.log"

"$PYTHON_BIN" -m openclaw.main --mode="$MODE" 2>&1 | tee "$log_file"
