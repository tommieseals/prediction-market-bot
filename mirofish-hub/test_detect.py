#!/usr/bin/env python3
"""Test position detection"""
import sys
sys.path.insert(0, '.')

from polymarket_api import PolymarketAPI
import sqlite3

api = PolymarketAPI()

# Check a few known whales
test_whales = ['denizz', 'betwick', 'anoin123']

print("=== CHECKING WHALE POSITIONS ===")
for whale in test_whales:
    try:
        # Get open positions
        positions = api.get_open_positions(whale)
        count = len(positions) if positions else 0
        print(f"{whale}: {count} open positions")
        
        if positions and count > 0:
            for p in positions[:2]:
                market = p.get('title', p.get('market', '?'))[:40]
                side = p.get('outcome', p.get('side', '?'))
                print(f"  - {market} ({side})")
    except Exception as e:
        print(f"{whale}: ERROR - {e}")

# Check what's in the DB
print("\n=== DATABASE STATUS ===")
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

cur.execute("SELECT MAX(detected_at) FROM whale_positions")
print(f"Latest position: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM whale_positions WHERE detected_at > datetime('now', '-2 hours')")
print(f"Last 2 hours: {cur.fetchone()[0]} positions")

cur.execute("SELECT COUNT(DISTINCT address) FROM whale_positions WHERE detected_at > datetime('now', '-24 hours')")
print(f"Unique whales today: {cur.fetchone()[0]}")

print("\n=== DONE ===")
