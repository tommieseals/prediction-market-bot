#!/usr/bin/env python3
"""Debug - trace through detect_new_positions"""
import sqlite3
from datetime import datetime, timedelta
from polymarket_api import PolymarketAPI
from whale_scorer import extract_positions, score_trader

print("=" * 60)
print("POSITION DETECTION DEBUG v5 - Full Trace")
print("=" * 60)

MIN_ELITE_SCORE = 20

# Get whale profiles from DB (how whale hunter does it)
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Simulate what rank_traders returns
cur.execute("""
    SELECT address, display_name, elite_score, pnl
    FROM tracked_whales 
    WHERE elite_score >= ?
    ORDER BY elite_score DESC 
    LIMIT 20
""", (MIN_ELITE_SCORE,))

class FakeWhale:
    def __init__(self, row):
        self.address = row[0]
        self.display_name = row[1]
        self.elite_score = row[2]
        self.pnl = row[3] or 0

whales = [FakeWhale(r) for r in cur.fetchall()]
print(f"\n{len(whales)} elite whales (score >= {MIN_ELITE_SCORE})")

# Initialize API
api = PolymarketAPI()
side_cache = {}

# Process each whale like detect_new_positions does
total_new = 0
total_skipped_underwater = 0

for whale in whales[:5]:  # Test first 5
    print(f"\n{'─' * 50}")
    print(f"Checking: {whale.display_name} (score={whale.elite_score:.1f})")
    
    # Get positions
    try:
        raw_positions = api.get_positions(whale.address)
        positions = extract_positions(whale.address, raw_positions, side_cache=side_cache)
        print(f"  Positions from API: {len(positions)}")
    except Exception as e:
        print(f"  ERROR: {e}")
        continue
    
    whale_new = 0
    whale_skipped = 0
    
    for pos in positions:
        if not pos.condition_id:
            continue
        
        # Skip underwater positions (disposition effect filter)
        if pos.size_usd > 0 and pos.unrealized_pnl < -pos.size_usd * 0.3:
            whale_skipped += 1
            continue
        
        # Check if already tracked
        cur.execute(
            "SELECT id FROM whale_positions WHERE address = ? AND condition_id = ?",
            (whale.address, pos.condition_id)
        )
        if cur.fetchone():
            continue
        
        # NEW position!
        whale_new += 1
        if whale_new <= 3:
            print(f"  NEW: {pos.market_title[:40]}...")
    
    print(f"  Result: {whale_new} new, {whale_skipped} skipped (underwater)")
    total_new += whale_new
    total_skipped_underwater += whale_skipped

api.close()
conn.close()

print("\n" + "=" * 60)
print(f"TOTAL: {total_new} new positions, {total_skipped_underwater} skipped (underwater)")
if total_new > 0:
    print("==> BUG: These positions should be in DB but aren't!")
print("=" * 60)
