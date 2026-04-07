#!/usr/bin/env python3
"""
COMPREHENSIVE SYSTEM AUDIT
Generated: 2026-03-25
Purpose: Document ALL issues - no fixes, just findings
"""

import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path

ISSUES = []

def log_issue(category, severity, description, details=None):
    """Log an issue found during audit"""
    issue = {
        'category': category,
        'severity': severity,  # CRITICAL, HIGH, MEDIUM, LOW
        'description': description,
        'details': details
    }
    ISSUES.append(issue)
    print(f"  [{severity}] {description}")
    if details:
        print(f"    Details: {details}")

print("=" * 70)
print("COMPREHENSIVE SYSTEM AUDIT - MIROFISH/WHALE TRACKER")
print(f"Started: {datetime.now().isoformat()}")
print("=" * 70)

# ================================================================
# SECTION 1: MIROFISH ORCHESTRATOR
# ================================================================
print("\n" + "=" * 70)
print("SECTION 1: MIROFISH ORCHESTRATOR STATUS")
print("=" * 70)

# Check if orchestrator database exists
orch_db_path = Path("data/orchestrator.db")
if not orch_db_path.exists():
    log_issue("MIROFISH", "CRITICAL", "Orchestrator database does not exist", str(orch_db_path))
else:
    try:
        conn = sqlite3.connect(str(orch_db_path), timeout=10)
        cur = conn.cursor()
        
        # Check tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"  Orchestrator DB tables: {tables}")
        
        # Check last run
        if 'runs' in tables:
            cur.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1")
            last_run = cur.fetchone()
            if last_run:
                print(f"  Last run: {last_run}")
            else:
                log_issue("MIROFISH", "CRITICAL", "No runs recorded in orchestrator.db")
        else:
            log_issue("MIROFISH", "CRITICAL", "No 'runs' table in orchestrator.db")
        
        conn.close()
    except Exception as e:
        log_issue("MIROFISH", "CRITICAL", f"Cannot read orchestrator.db: {e}")

# Check MiroFish results in whale_hunter.db
print("\n--- MiroFish Results Data ---")
try:
    conn = sqlite3.connect("data/whale_hunter.db", timeout=30)
    cur = conn.cursor()
    
    # Total count
    cur.execute("SELECT COUNT(*) FROM mirofish_results")
    total = cur.fetchone()[0]
    print(f"  Total mirofish_results: {total}")
    
    # Last 7 days
    cur.execute("""SELECT COUNT(*) FROM mirofish_results 
                   WHERE created_at > datetime('now', '-7 days')""")
    recent = cur.fetchone()[0]
    print(f"  Results in last 7 days: {recent}")
    
    if recent == 0:
        log_issue("MIROFISH", "CRITICAL", "No MiroFish results in the last 7 days - system not running")
    
    # Last entry
    cur.execute("SELECT created_at FROM mirofish_results ORDER BY id DESC LIMIT 1")
    last = cur.fetchone()
    if last:
        print(f"  Last result timestamp: {last[0]}")
    
    conn.close()
except Exception as e:
    log_issue("MIROFISH", "CRITICAL", f"Cannot query mirofish_results: {e}")

# ================================================================
# SECTION 2: CONSENSUS PICKS - STALE DATA
# ================================================================
print("\n" + "=" * 70)
print("SECTION 2: CONSENSUS PICKS DATA QUALITY")
print("=" * 70)

try:
    conn = sqlite3.connect("data/whale_hunter.db", timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Check consensus_picks table
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='consensus_picks'")
    if not cur.fetchone():
        log_issue("CONSENSUS", "HIGH", "consensus_picks table does not exist")
    else:
        # Total picks
        cur.execute("SELECT COUNT(*) FROM consensus_picks")
        total_picks = cur.fetchone()[0]
        print(f"  Total consensus picks: {total_picks}")
        
        # STALE PICKS - end_date passed but still pending
        cur.execute("""
            SELECT COUNT(*) FROM consensus_picks 
            WHERE end_date < datetime('now') 
            AND (outcome IS NULL OR outcome = 'pending')
        """)
        stale = cur.fetchone()[0]
        print(f"  Stale picks (expired but not resolved): {stale}")
        
        if stale > 0:
            log_issue("CONSENSUS", "HIGH", f"{stale} consensus picks are stale (expired but not resolved)")
            
            # Show some examples
            cur.execute("""
                SELECT market_title, end_date, outcome FROM consensus_picks 
                WHERE end_date < datetime('now') 
                AND (outcome IS NULL OR outcome = 'pending')
                LIMIT 5
            """)
            for row in cur.fetchall():
                print(f"    STALE: {row[0][:50]}... | Ended: {row[1]} | Status: {row[2]}")
        
        # WIN/LOSS TRACKING
        cur.execute("SELECT outcome, COUNT(*) FROM consensus_picks WHERE outcome IS NOT NULL GROUP BY outcome")
        outcomes = dict(cur.fetchall())
        print(f"  Outcome distribution: {outcomes}")
        
        won = outcomes.get('won', 0)
        lost = outcomes.get('lost', 0)
        if won + lost > 0:
            win_rate = won / (won + lost) * 100
            print(f"  Tracked win rate: {win_rate:.1f}% ({won}W/{lost}L)")
        else:
            log_issue("CONSENSUS", "HIGH", "No wins/losses tracked - cannot calculate accuracy")
        
        # Check for missing end_date
        cur.execute("SELECT COUNT(*) FROM consensus_picks WHERE end_date IS NULL")
        no_end = cur.fetchone()[0]
        if no_end > 0:
            log_issue("CONSENSUS", "MEDIUM", f"{no_end} consensus picks have no end_date")
    
    conn.close()
except Exception as e:
    log_issue("CONSENSUS", "CRITICAL", f"Cannot audit consensus_picks: {e}")

# ================================================================
# SECTION 3: WHALE POSITIONS DATA QUALITY
# ================================================================
print("\n" + "=" * 70)
print("SECTION 3: WHALE POSITIONS DATA QUALITY")
print("=" * 70)

try:
    conn = sqlite3.connect("data/whale_hunter.db", timeout=30)
    cur = conn.cursor()
    
    # Total positions
    cur.execute("SELECT COUNT(*) FROM whale_positions")
    total = cur.fetchone()[0]
    print(f"  Total whale positions: {total}")
    
    # Pending positions with expired end_date
    cur.execute("""
        SELECT COUNT(*) FROM whale_positions 
        WHERE end_date < datetime('now') 
        AND outcome = 'pending'
    """)
    stale = cur.fetchone()[0]
    print(f"  Stale positions (expired + pending): {stale}")
    
    if stale > 0:
        log_issue("WHALE_DATA", "HIGH", f"{stale} whale positions are stale (expired but pending)")
    
    # Positions with no end_date
    cur.execute("SELECT COUNT(*) FROM whale_positions WHERE end_date IS NULL AND outcome = 'pending'")
    no_end = cur.fetchone()[0]
    if no_end > 0:
        log_issue("WHALE_DATA", "MEDIUM", f"{no_end} pending positions have no end_date")
        print(f"  Positions missing end_date: {no_end}")
    
    # Recent data freshness
    cur.execute("SELECT MAX(detected_at) FROM whale_positions")
    last_detected = cur.fetchone()[0]
    print(f"  Most recent detection: {last_detected}")
    
    conn.close()
except Exception as e:
    log_issue("WHALE_DATA", "CRITICAL", f"Cannot audit whale_positions: {e}")

# ================================================================
# SECTION 4: TELEGRAM ALERT TIMING
# ================================================================
print("\n" + "=" * 70)
print("SECTION 4: TELEGRAM ALERT TIMING ISSUES")
print("=" * 70)

try:
    conn = sqlite3.connect("data/whale_hunter.db", timeout=30)
    cur = conn.cursor()
    
    # Check for positions where signal was generated after end_date
    cur.execute("""
        SELECT COUNT(*) FROM whale_positions 
        WHERE signal_generated = 1 
        AND end_date IS NOT NULL
        AND detected_at > end_date
    """)
    late_signals = cur.fetchone()[0]
    print(f"  Signals generated after market ended: {late_signals}")
    
    if late_signals > 0:
        log_issue("TELEGRAM", "HIGH", f"{late_signals} alerts were sent for already-closed markets")
        
        cur.execute("""
            SELECT market_title, detected_at, end_date FROM whale_positions 
            WHERE signal_generated = 1 
            AND end_date IS NOT NULL
            AND detected_at > end_date
            LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"    LATE: {row[0][:40]}... | Detected: {row[1]} | Ended: {row[2]}")
    
    # Check signal_generated usage
    cur.execute("SELECT signal_generated, COUNT(*) FROM whale_positions GROUP BY signal_generated")
    signal_dist = dict(cur.fetchall())
    print(f"  Signal distribution: {signal_dist}")
    
    conn.close()
except Exception as e:
    log_issue("TELEGRAM", "HIGH", f"Cannot audit telegram timing: {e}")

# ================================================================
# SECTION 5: MY_TRADES TRACKING
# ================================================================
print("\n" + "=" * 70)
print("SECTION 5: TRADE TRACKING (my_trades)")
print("=" * 70)

try:
    conn = sqlite3.connect("data/whale_hunter.db", timeout=30)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM my_trades")
    total = cur.fetchone()[0]
    print(f"  Total trades tracked: {total}")
    
    cur.execute("SELECT outcome, COUNT(*) FROM my_trades GROUP BY outcome")
    outcomes = dict(cur.fetchall())
    print(f"  Outcome breakdown: {outcomes}")
    
    # Unredeemed wins
    cur.execute("SELECT COUNT(*) FROM my_trades WHERE outcome = 'won' AND (redeemed = 0 OR redeemed IS NULL)")
    unredeemed = cur.fetchone()[0]
    if unredeemed > 0:
        log_issue("TRADES", "MEDIUM", f"{unredeemed} winning trades not redeemed")
        print(f"  Unredeemed wins: {unredeemed}")
    
    conn.close()
except Exception as e:
    log_issue("TRADES", "HIGH", f"Cannot audit my_trades: {e}")

# ================================================================
# SECTION 6: SCHEDULED TASKS
# ================================================================
print("\n" + "=" * 70)
print("SECTION 6: SCHEDULED TASKS STATUS")
print("=" * 70)

# Check Windows Task Scheduler
import subprocess
try:
    result = subprocess.run(
        ['schtasks', '/query', '/fo', 'csv', '/v'],
        capture_output=True, text=True, timeout=30
    )
    tasks = result.stdout
    
    relevant_tasks = []
    for line in tasks.split('\n'):
        if 'mirofish' in line.lower() or 'whale' in line.lower() or 'consensus' in line.lower() or 'polymarket' in line.lower():
            relevant_tasks.append(line)
    
    if relevant_tasks:
        print(f"  Found {len(relevant_tasks)} relevant scheduled tasks")
        for t in relevant_tasks[:5]:
            parts = t.split(',')
            if len(parts) > 1:
                print(f"    {parts[0][:50]}")
    else:
        log_issue("SCHEDULER", "HIGH", "No relevant scheduled tasks found in Windows Task Scheduler")
except Exception as e:
    log_issue("SCHEDULER", "MEDIUM", f"Cannot query Task Scheduler: {e}")

# ================================================================
# SUMMARY
# ================================================================
print("\n" + "=" * 70)
print("AUDIT SUMMARY")
print("=" * 70)

critical = len([i for i in ISSUES if i['severity'] == 'CRITICAL'])
high = len([i for i in ISSUES if i['severity'] == 'HIGH'])
medium = len([i for i in ISSUES if i['severity'] == 'MEDIUM'])
low = len([i for i in ISSUES if i['severity'] == 'LOW'])

print(f"""
Total Issues Found: {len(ISSUES)}
  - CRITICAL: {critical}
  - HIGH: {high}
  - MEDIUM: {medium}
  - LOW: {low}
""")

print("\nALL ISSUES:")
for i, issue in enumerate(ISSUES, 1):
    print(f"\n{i}. [{issue['severity']}] {issue['category']}")
    print(f"   {issue['description']}")
    if issue['details']:
        print(f"   Details: {issue['details']}")

print("\n" + "=" * 70)
print(f"AUDIT COMPLETE: {datetime.now().isoformat()}")
print("=" * 70)
