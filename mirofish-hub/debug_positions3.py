#!/usr/bin/env python3
"""Debug - show exact condition_ids"""
import sqlite3
from datetime import datetime, timedelta
from polymarket_api import PolymarketAPI
from whale_scorer import extract_positions

print("=" * 60)
print("POSITION DETECTION DEBUG v4 - Condition ID Check")
print("=" * 60)

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Get whale
cur.execute("""
    SELECT address, display_name, elite_score 
    FROM tracked_whales 
    WHERE elite_score >= 60 
    ORDER BY elite_score DESC 
    LIMIT 1
""")
addr, name, score = cur.fetchone()
print(f"\nWhale: {name}")

api = PolymarketAPI()
side_cache = {}

# Get and extract positions
raw = api.get_positions(addr)
positions = extract_positions(addr, raw, side_cache=side_cache)

print(f"\nExtracted {len(positions)} positions")
print("\nNEW positions (not in DB):")

new_count = 0
for pos in positions:
    if not pos.condition_id:
        continue
        
    # Check DB
    cur.execute(
        "SELECT id FROM whale_positions WHERE address = ? AND condition_id = ?",
        (addr, pos.condition_id)
    )
    exists = cur.fetchone()
    
    if not exists:
        new_count += 1
        print(f"\n  [{new_count}] NEW POSITION FOUND:")
        print(f"      Market: {pos.market_title[:50]}")
        print(f"      Condition ID: {pos.condition_id}")
        print(f"      Token ID: {pos.token_id}")
        print(f"      Side: {pos.side}")
        print(f"      Size: {pos.size:.2f} @ ${pos.entry_price:.4f}")
        print(f"      Size USD: ${pos.size_usd:.2f}")

if new_count == 0:
    print("  (none)")
else:
    print(f"\n==> {new_count} positions should be added but AREN'T!")
    print("==> This is a BUG in detect_new_positions()!")

api.close()
conn.close()
