#!/usr/bin/env python3
"""
AUDIT PART 2: Deep Dive Analysis
"""

import sqlite3
from datetime import datetime, timedelta
import os

print("=" * 70)
print("AUDIT PART 2: DEEP DIVE ANALYSIS")
print("=" * 70)

conn = sqlite3.connect('data/whale_hunter.db', timeout=30)
cur = conn.cursor()

# ================================================================
# CONSENSUS PICKS DETAILED ANALYSIS
# ================================================================
print("\n--- CONSENSUS PICKS: PENDING WITHOUT EXPIRATION TIMER ---")
cur.execute("""
    SELECT market_title, whale_count, confidence, end_date, created_at
    FROM consensus_picks 
    WHERE outcome = 'pending'
    ORDER BY end_date ASC NULLS LAST
    LIMIT 20
""")

now = datetime.now()
print(f"Current time: {now}")
print()

for r in cur.fetchall():
    title = r[0][:50] if r[0] else "NO TITLE"
    whales = r[1] or 0
    conf = r[2] or 0
    end_date = r[3]
    created = r[4]
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00').replace('+00:00', ''))
            time_left = end_dt - now
            if time_left.total_seconds() < 0:
                timer = "EXPIRED"
            elif time_left.total_seconds() < 3600:
                timer = f"{int(time_left.total_seconds()/60)} min"
            elif time_left.total_seconds() < 86400:
                timer = f"{time_left.total_seconds()/3600:.1f} hrs"
            else:
                timer = f"{time_left.days} days"
        except (ValueError, TypeError):  # H12 FIX: Date parsing
            timer = "PARSE ERROR"
    else:
        timer = "NO END DATE!"
    
    print(f"  [{timer:12}] {title} | {whales} whales | {conf}% conf")

# ================================================================
# TELEGRAM ALERT AUDIT - Check what was actually sent
# ================================================================
print("\n" + "=" * 70)
print("TELEGRAM ALERT TIMING: Positions detected near/after end_date")
print("=" * 70)

cur.execute("""
    SELECT market_title, detected_at, end_date, side, 
           julianday(detected_at) - julianday(end_date) as days_diff
    FROM whale_positions 
    WHERE end_date IS NOT NULL
    AND detected_at IS NOT NULL
    ORDER BY days_diff DESC
    LIMIT 10
""")

print("Positions with latest detection relative to end_date:")
for r in cur.fetchall():
    title = r[0][:40] if r[0] else "N/A"
    detected = r[1]
    end = r[2]
    days_diff = r[4] or 0
    
    if days_diff > 0:
        status = "DETECTED AFTER CLOSED!"
    elif days_diff > -0.042:  # Within 1 hour of close
        status = "VERY CLOSE TO CLOSE"
    else:
        status = "OK"
    
    print(f"  [{status:22}] {title} | Detected: {detected[:16] if detected else 'N/A'} | End: {end[:16] if end else 'N/A'}")

# ================================================================
# WIN RATE ACCURACY CHECK
# ================================================================
print("\n" + "=" * 70)
print("CONSENSUS PICKS WIN RATE DETAILED BREAKDOWN")
print("=" * 70)

cur.execute("""
    SELECT 
        outcome,
        COUNT(*) as count,
        AVG(confidence) as avg_confidence,
        AVG(whale_count) as avg_whales
    FROM consensus_picks
    WHERE outcome IS NOT NULL
    GROUP BY outcome
""")

for r in cur.fetchall():
    print(f"  {r[0]:10} | Count: {r[1]:3} | Avg Conf: {r[2] or 0:.1f}% | Avg Whales: {r[3] or 0:.1f}")

# Calculate actual accuracy
cur.execute("SELECT COUNT(*) FROM consensus_picks WHERE outcome = 'won'")
won = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM consensus_picks WHERE outcome = 'lost'")
lost = cur.fetchone()[0]

if won + lost > 0:
    accuracy = won / (won + lost) * 100
    print(f"\n  ACTUAL WIN RATE: {accuracy:.1f}% ({won}W / {lost}L)")
else:
    print("\n  [ISSUE] No resolved picks to calculate accuracy!")

# ================================================================
# MIROFISH VALIDATION STATUS
# ================================================================
print("\n" + "=" * 70)
print("MIROFISH VALIDATION STATUS")
print("=" * 70)

# Check mirofish_results schema
cur.execute("PRAGMA table_info(mirofish_results)")
cols = [r[1] for r in cur.fetchall()]
print(f"mirofish_results columns: {cols}")

# Try to get some data
try:
    cur.execute("SELECT * FROM mirofish_results LIMIT 3")
    results = cur.fetchall()
    print(f"Sample results: {len(results)} rows")
    for r in results:
        print(f"  {r}")
except Exception as e:
    print(f"  [ERROR] {e}")

# Check if consensus picks have been validated by MiroFish
if 'validated_by_mirofish' in cols or 'mirofish_validated' in cols:
    print("\n  Found MiroFish validation column")
else:
    print("\n  [ISSUE] No MiroFish validation column in consensus_picks")

# ================================================================
# DATA STALENESS CHECK
# ================================================================
print("\n" + "=" * 70)
print("DATA STALENESS CHECK")
print("=" * 70)

# Whale positions age
cur.execute("SELECT MAX(detected_at), MIN(detected_at) FROM whale_positions WHERE outcome = 'pending'")
r = cur.fetchone()
print(f"  Pending positions: newest={r[0]}, oldest={r[1]}")

# Last whale hunter scan
cur.execute("SELECT MAX(last_updated) FROM tracked_whales")
r = cur.fetchone()
print(f"  Last whale update: {r[0]}")

conn.close()

# ================================================================
# FILE SYSTEM CHECKS
# ================================================================
print("\n" + "=" * 70)
print("FILE SYSTEM / SERVICE CHECKS")
print("=" * 70)

# Check if key files exist
files_to_check = [
    'whale_hunter_connector.py',
    'orchestrator.py',
    'consensus_swarm.py',
    'whale_api.py',
    'polymarket_api.py'
]

for f in files_to_check:
    exists = os.path.exists(f)
    status = "OK" if exists else "MISSING"
    print(f"  [{status:7}] {f}")

print("\n" + "=" * 70)
print("AUDIT PART 2 COMPLETE")
print("=" * 70)
