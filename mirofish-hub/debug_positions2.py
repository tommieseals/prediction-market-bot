#!/usr/bin/env python3
"""Debug position detection - check if API positions are already in DB"""
import sqlite3
from datetime import datetime, timedelta
from polymarket_api import PolymarketAPI

print("=" * 60)
print("POSITION DETECTION DEBUG v3")
print("=" * 60)

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Get a known active whale
cur.execute("""
    SELECT address, display_name, elite_score 
    FROM tracked_whales 
    WHERE elite_score >= 60 
    ORDER BY elite_score DESC 
    LIMIT 1
""")
addr, name, score = cur.fetchone()
print(f"\nTest whale: {name}")

api = PolymarketAPI()

# Get current positions
raw = api.get_positions(addr)
print(f"\nAPI returned {len(raw)} positions")

# Check each against DB
new_count = 0
already_tracked = 0

print("\nChecking each position...")
for p in raw[:10]:  # Check first 10
    cid = p.get('conditionId')
    title = p.get('title', '?')[:40]
    
    # Check if in DB
    cur.execute(
        "SELECT id FROM whale_positions WHERE address = ? AND condition_id = ?",
        (addr, cid)
    )
    exists = cur.fetchone()
    
    if exists:
        already_tracked += 1
        status = "TRACKED"
    else:
        new_count += 1
        status = "NEW!"
        
    print(f"  [{status}] {title}...")

print(f"\nSummary: {already_tracked} tracked, {new_count} new")

# Check closed positions
print("\n" + "-" * 60)
print("Checking CLOSED positions...")
cutoff_ts = int((datetime.now() - timedelta(hours=48)).timestamp())
closed = api.get_closed_positions(addr, start=cutoff_ts, limit=10, max_total=10)
print(f"API returned {len(closed)} closed positions")

closed_new = 0
closed_tracked = 0
for p in closed[:10]:
    cid = p.get('conditionId')
    title = p.get('title', '?')[:40]
    
    cur.execute(
        "SELECT id FROM whale_positions WHERE address = ? AND condition_id = ?",
        (addr, cid)
    )
    exists = cur.fetchone()
    
    if exists:
        closed_tracked += 1
        status = "TRACKED"
    else:
        closed_new += 1
        status = "NEW!"
        
    print(f"  [{status}] {title}...")

print(f"\nClosed summary: {closed_tracked} tracked, {closed_new} new")

api.close()
conn.close()

print("\n" + "=" * 60)
if new_count == 0 and closed_new == 0:
    print("RESULT: All positions already tracked - no new trades!")
else:
    print(f"RESULT: Found {new_count + closed_new} NEW positions to add!")
print("=" * 60)
