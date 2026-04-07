#!/usr/bin/env python3
"""Debug position detection"""
import sqlite3
import json
from datetime import datetime, timedelta
from polymarket_api import PolymarketAPI

print("=" * 60)
print("POSITION DETECTION DEBUG v2")
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
print(f"\nTest whale: {name} (score={score:.1f})")
print(f"Address: {addr}")

api = PolymarketAPI()

# Check raw positions endpoint
print("\n[1] RAW get_positions() RESPONSE:")
try:
    raw = api.get_positions(addr)
    print(f"  Count: {len(raw) if raw else 0}")
    if raw and len(raw) > 0:
        print(f"  Sample keys: {list(raw[0].keys())[:10]}")
        # Show first position
        p = raw[0]
        print(f"  First position:")
        for k in ['title', 'outcome', 'size', 'avgPrice', 'initialValue', 'currentValue']:
            if k in p:
                print(f"    {k}: {p[k]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Check closed positions
print("\n[2] RAW get_closed_positions() RESPONSE:")
try:
    cutoff_ts = int((datetime.now() - timedelta(hours=48)).timestamp())
    closed = api.get_closed_positions(addr, start=cutoff_ts, limit=10, max_total=10)
    print(f"  Count: {len(closed) if closed else 0}")
    if closed and len(closed) > 0:
        print(f"  Sample keys: {list(closed[0].keys())[:10]}")
        # Show first
        p = closed[0]
        print(f"  First closed:")
        for k in ['title', 'outcome', 'realizedPnl', 'avgPrice', 'closedTime']:
            if k in p:
                print(f"    {k}: {p[k]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Check what's already tracked for this whale
print("\n[3] ALREADY TRACKED IN DB:")
cur.execute("""
    SELECT COUNT(*) FROM whale_positions WHERE address = ?
""", (addr,))
total = cur.fetchone()[0]
print(f"  Total positions tracked: {total}")

cur.execute("""
    SELECT COUNT(DISTINCT condition_id) FROM whale_positions WHERE address = ?
""", (addr,))
unique = cur.fetchone()[0]
print(f"  Unique markets: {unique}")

cur.execute("""
    SELECT condition_id, market_title, detected_at 
    FROM whale_positions 
    WHERE address = ? 
    ORDER BY detected_at DESC 
    LIMIT 3
""", (addr,))
recent = cur.fetchall()
print(f"  Most recent:")
for cid, title, det in recent:
    print(f"    {det[:19]} | {title[:40] if title else cid[:20]}")

api.close()
conn.close()
print("\n" + "=" * 60)
