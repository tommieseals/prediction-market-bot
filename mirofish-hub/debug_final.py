#!/usr/bin/env python3
"""Final debug - trace exactly why positions aren't being added"""
import sqlite3
from datetime import datetime

# Import the actual functions
from whale_hunter_connector import (
    fetch_and_score_whales, rank_traders, detect_new_positions,
    MIN_ELITE_SCORE, MAX_INSIDER_FLAGS, TOP_LEADERBOARD, _init_db
)
from polymarket_api import PolymarketAPI

print("=" * 60)
print("FINAL DEBUG - Why positions aren't being added")
print("=" * 60)

_init_db()

api = PolymarketAPI(rate_limit=0.5)

# Step 1: Fetch and score (just 5 for speed)
print("\n[1] Fetching/scoring 5 whales...")
whales = fetch_and_score_whales(api, top_n=5)
print(f"    Got {len(whales)} whale profiles")

if whales:
    print(f"    First whale: {whales[0].display_name}")
    print(f"    Address: {whales[0].address}")
    print(f"    Elite score: {whales[0].elite_score}")

# Step 2: Rank
print("\n[2] Ranking traders...")
ranked = rank_traders(whales, min_trades=5, min_elite_score=MIN_ELITE_SCORE,
                      max_insider_flags=MAX_INSIDER_FLAGS)
print(f"    {len(ranked)} qualified as elite")

for w in ranked[:3]:
    print(f"    - {w.display_name}: score={w.elite_score:.1f}, addr={w.address[:15]}...")

# Step 3: Detect positions
print("\n[3] Detecting new positions...")
new_positions = detect_new_positions(api, ranked)
print(f"    Detected {len(new_positions)} new positions")

api.close()

# Step 4: Check DB
print("\n[4] Checking database...")
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()
cur.execute("SELECT MAX(detected_at) FROM whale_positions")
latest = cur.fetchone()[0]
print(f"    Latest position: {latest}")

cur.execute("SELECT COUNT(*) FROM whale_positions WHERE detected_at > datetime('now', '-5 minutes')")
recent = cur.fetchone()[0]
print(f"    Added in last 5 min: {recent}")

conn.close()

print("\n" + "=" * 60)
if recent > 0:
    print("SUCCESS - Positions are being added!")
else:
    print("FAILURE - No positions added")
print("=" * 60)
