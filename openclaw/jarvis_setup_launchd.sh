#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/clawd}"
RUNNER="$PROJECT_ROOT/openclaw/jarvis_task_runner.sh"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
PYTHON_BIN="${PYTHON_BIN:-/usr/local/bin/python3.13}"

mkdir -p "$LAUNCH_DIR"

write_plist() {
  local label="$1"
  local mode="$2"
  local body="$3"
  local file="$LAUNCH_DIR/${label}.plist"
  cat > "$file" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${RUNNER}</string>
    <string>${mode}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${PROJECT_ROOT}</string>
  <key>RunAtLoad</key>
  <false/>
${body}
  <key>StandardOutPath</key>
  <string>${PROJECT_ROOT}/openclaw/audits/task-runs/${mode}.launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${PROJECT_ROOT}/openclaw/audits/task-runs/${mode}.launchd.err.log</string>
</dict>
</plist>
PLIST
}

write_server_plist() {
  local label="com.openclaw.server"
  local file="$LAUNCH_DIR/${label}.plist"
  cat > "$file" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>-m</string>
    <string>openclaw.main</string>
    <string>--mode=server</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${PROJECT_ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${PROJECT_ROOT}/openclaw/audits/task-runs/server.launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${PROJECT_ROOT}/openclaw/audits/task-runs/server.launchd.err.log</string>
</dict>
</plist>
PLIST
}

write_plist "com.openclaw.proactive" "proactive" "  <key>StartInterval</key>
  <integer>21600</integer>"

write_plist "com.openclaw.eval" "eval" "  <key>StartInterval</key>
  <integer>43200</integer>"

write_plist "com.openclaw.morningpulse" "morning-pulse" "  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>3</integer>
  </dict>"

write_plist "com.openclaw.meta" "meta" "  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key>
    <integer>1</integer>
    <key>Hour</key>
    <integer>2</integer>
    <key>Minute</key>
    <integer>7</integer>
  </dict>"

write_server_plist

for label in com.openclaw.proactive com.openclaw.eval com.openclaw.morningpulse com.openclaw.meta; do
  launchctl bootout "gui/$(id -u)" "$LAUNCH_DIR/${label}.plist" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$LAUNCH_DIR/${label}.plist"
done

pkill -f 'python3.13 -m openclaw.main --mode=server' 2>/dev/null || true
launchctl bootout "gui/$(id -u)" "$LAUNCH_DIR/com.openclaw.server.plist" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$LAUNCH_DIR/com.openclaw.server.plist"

launchctl print "gui/$(id -u)/com.openclaw.proactive" >/dev/null
launchctl print "gui/$(id -u)/com.openclaw.server" >/dev/null
echo "Jarvis launchd tasks installed."
