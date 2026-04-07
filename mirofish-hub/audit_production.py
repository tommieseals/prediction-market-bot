#!/usr/bin/env python3
"""Full production readiness audit — run before going live."""

import sqlite3
import requests
import os
import py_compile
import psutil
from datetime import datetime, timedelta

DB = "data/whale_hunter.db"
API = "http://localhost:8081"
NOW = datetime.now()
ISSUES = []

def check(label, ok, detail=""):
    status = "OK" if ok else "FAIL"
    if not ok:
        ISSUES.append(f"{label}: {detail}")
    print(f"  {status:6s} {label}" + (f" — {detail}" if detail else ""))
    return ok


print("=" * 70)
print("FULL PRODUCTION READINESS AUDIT")
print(f"Timestamp: {NOW.isoformat()}")
print("=" * 70)

conn = sqlite3.connect(DB, timeout=10)

# 1. API
print("\n[1] API HEALTH")
try:
    r = requests.get(f"{API}/health", timeout=5)
    check("API responding", r.status_code == 200)
except requests.RequestException:  # H12 FIX
    check("API responding", False, "API is DOWN")

# 2. Endpoints
print("\n[2] ALL ENDPOINTS")
endpoints = ["/health", "/api/stats", "/api/consensus", "/api/category/performance",
             "/api/hot-whales", "/api/portfolio/heat", "/api/consensus/history",
             "/api/my-trades", "/api/calibration", "/api/leaderboard"]
for ep in endpoints:
    try:
        r = requests.get(f"{API}{ep}", timeout=5)
        check(ep, r.status_code == 200, f"status={r.status_code}" if r.status_code != 200 else "")
    except requests.RequestException:  # H12 FIX
        check(ep, False, "connection failed")

# 3. Data freshness
print("\n[3] DATA FRESHNESS")
freshness = {
    "Latest position": conn.execute("SELECT MAX(detected_at) FROM whale_positions").fetchone()[0],
    "Latest whale": conn.execute("SELECT MAX(last_updated) FROM tracked_whales").fetchone()[0],
    "Latest pick": conn.execute("SELECT MAX(created_at) FROM consensus_picks").fetchone()[0],
    "Latest resolution": conn.execute("SELECT MAX(resolved_at) FROM whale_positions WHERE resolved_at IS NOT NULL").fetchone()[0],
}
for label, ts in freshness.items():
    if ts:
        try:
            age_h = (NOW - datetime.fromisoformat(ts.replace("Z", ""))).total_seconds() / 3600
            check(label, age_h < 12, f"{ts[:19]} ({age_h:.1f}h ago)")
        except (ValueError, TypeError):  # H12 FIX: Date parsing errors
            check(label, False, f"unparseable: {ts}")
    else:
        check(label, False, "NULL")

# 4. Database tables
print("\n[4] DATABASE TABLES")
for t in ["tracked_whales", "whale_positions", "consensus_picks", "trade_signals",
          "token_side_cache", "mirofish_results", "my_trades"]:
    try:
        c = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        check(t, c > 0 or t in ("trade_signals", "my_trades"), f"{c:,} rows")
    except sqlite3.OperationalError:  # H12 FIX: DB table errors
        check(t, False, "TABLE MISSING")

# 5. Position outcomes
print("\n[5] POSITION OUTCOMES")
outcomes = {}
for row in conn.execute("SELECT outcome, COUNT(*) FROM whale_positions GROUP BY outcome"):
    outcomes[row[0]] = row[1]
    print(f"  {row[0]:10s}: {row[1]:>8,}")
total_resolved = outcomes.get("won", 0) + outcomes.get("lost", 0)
wr = outcomes.get("won", 0) / max(total_resolved, 1) * 100
print(f"  Win rate: {wr:.1f}% ({total_resolved:,} resolved)")

# 6. Stale data
print("\n[6] STALE DATA")
stale = conn.execute("""SELECT COUNT(*) FROM whale_positions
    WHERE outcome = 'pending' AND end_date IS NOT NULL AND end_date != ''
    AND datetime(end_date) < datetime('now', '-2 hours')""").fetchone()[0]
check("Stale pending positions", stale < 50, f"{stale} positions past end_date by 2+ hours")

# 7. Consensus page
print("\n[7] CONSENSUS PAGE")
try:
    r = requests.get(f"{API}/api/consensus", timeout=10)
    picks = r.json().get("picks", [])
    green = sum(1 for p in picks if p.get("confidence_tier") == "GREEN")
    sports = sum(1 for p in picks if p.get("category") in ("sports", "soccer", "esports"))
    check("Consensus picks loading", len(picks) > 0, f"{len(picks)} picks ({green} GREEN, {sports} sports)")

    # Check for stale picks on the page
    stale_on_page = 0
    for p in picks:
        ed = p.get("end_date", "")
        if ed:
            try:
                end = datetime.fromisoformat(ed.replace("Z", ""))
                if end < NOW - timedelta(hours=2):
                    stale_on_page += 1
            except ValueError:  # H12 FIX: Date parsing
                pass
    check("No stale picks on page", stale_on_page == 0, f"{stale_on_page} stale" if stale_on_page else "clean")
except Exception as e:
    check("Consensus API", False, str(e))

# 8. Track record
print("\n[8] TRACK RECORD")
try:
    r = requests.get(f"{API}/api/consensus/history", timeout=10)
    s = r.json().get("summary", {})
    won = s.get("won", 0)
    lost = s.get("lost", 0)
    pnl = s.get("total_pnl", 0)
    check("Picks resolving", won + lost > 0, f"{won}W/{lost}L, ${pnl:.0f} P&L")
except requests.RequestException:  # H12 FIX
    check("History API", False, "failed")

# 9. My trades
print("\n[9] MY TRADES")
try:
    r = requests.get(f"{API}/api/my-trades", timeout=5)
    s = r.json().get("summary", {})
    check("My trades working", True, f"{s.get('total',0)} trades, ${s.get('total_pnl',0):.2f} P&L")
except requests.RequestException:  # H12 FIX
    check("My trades", False, "endpoint broken")

# 10. MiroFish backend
print("\n[10] MIROFISH")
try:
    r = requests.get("http://localhost:5001/health", timeout=5)
    check("MiroFish backend", r.status_code == 200)
except requests.RequestException:  # H12 FIX
    check("MiroFish backend", False, "NOT RUNNING")

try:
    r = requests.get("http://localhost:11434/api/tags", timeout=5)
    models = [m.get("name", "?") for m in r.json().get("models", [])]
    has_qwen = any("qwen" in m for m in models)
    check("Ollama + qwen3:4b", has_qwen, f"{len(models)} models loaded")
except requests.RequestException:  # H12 FIX
    check("Ollama", False, "NOT RUNNING")

mr = conn.execute("SELECT COUNT(*) FROM mirofish_results").fetchone()[0]
real = conn.execute("SELECT COUNT(*) FROM mirofish_results WHERE swarm_prob != 50.0").fetchone()[0]
check("MiroFish results in DB", mr > 0, f"{mr} total, {real} with real probabilities")

# 11. File integrity
print("\n[11] FILE INTEGRITY")
files = ["whale_api.py", "consensus_swarm_connector.py", "whale_hunter_connector.py",
         "mirofish_client.py", "whale_scorer.py", "polymarket_api.py",
         "whale_outcome_tracker.py", "consensus_results_tracker.py",
         "auto_researcher.py", "watchdog.py"]
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        check(f, True)
    except py_compile.PyCompileError:
        check(f, False, "SYNTAX ERROR")
    except FileNotFoundError:
        check(f, False, "NOT FOUND")

# 12. Background processes
print("\n[12] PROCESSES")
api_up = mf_up = False
for p in psutil.process_iter(["pid", "cmdline"]):
    try:
        cmd = " ".join(p.info["cmdline"] or [])
        if "whale_api" in cmd:
            api_up = True
        if "run.py" in cmd and ("mirofish" in cmd.lower() or "5001" in cmd):
            mf_up = True
    except (psutil.NoSuchProcess, psutil.AccessDenied):  # H12 FIX: Process iteration errors
        pass
check("Whale API process", api_up)
check("MiroFish process", mf_up)

# 13. Timezone fix
print("\n[13] TIMEZONE FIX")
today = NOW.strftime("%Y-%m-%d")
today_pending = conn.execute(
    f"SELECT COUNT(*) FROM whale_positions WHERE end_date LIKE '{today}%' AND outcome = 'pending'"
).fetchone()[0]
check("Today's markets visible", today_pending > 0 or NOW.hour < 10,
      f"{today_pending} positions ending today")

# 14. Token coverage
print("\n[14] TOKEN COVERAGE")
cp_total = conn.execute("SELECT COUNT(*) FROM consensus_picks").fetchone()[0]
cp_token = conn.execute(
    "SELECT COUNT(*) FROM consensus_picks WHERE token_id IS NOT NULL AND token_id != ''"
).fetchone()[0]
pct = cp_token * 100 // max(cp_total, 1)
check("Consensus picks with token_id", pct >= 90, f"{cp_token}/{cp_total} ({pct}%)")

conn.close()

# ━━━ SUMMARY ━━━
print("\n" + "=" * 70)
if ISSUES:
    print(f"ISSUES FOUND: {len(ISSUES)}")
    for i, issue in enumerate(ISSUES, 1):
        print(f"  {i}. {issue}")
else:
    print("ALL CHECKS PASSED — PRODUCTION READY")
print("=" * 70)
