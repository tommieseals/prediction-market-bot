#!/usr/bin/env python3
"""Debug - compare addresses between API and DB"""
import sqlite3
from polymarket_api import PolymarketAPI

print("=" * 60)
print("ADDRESS COMPARISON DEBUG")
print("=" * 60)

api = PolymarketAPI(rate_limit=0.5)

# Get leaderboard addresses
print("\n[1] LEADERBOARD ADDRESSES (from API)")
leaders = api.get_leaderboard(limit=5)
api_addrs = []
for e in leaders:
    addr = e.get("proxyWallet") or e.get("address", "")
    name = e.get("userName") or e.get("username") or addr[:10]
    api_addrs.append(addr)
    print(f"  {name}: {addr}")

api.close()

# Get DB addresses for same whales
print("\n[2] DB ADDRESSES (tracked_whales)")
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

for addr in api_addrs:
    cur.execute("SELECT display_name, address FROM tracked_whales WHERE address = ?", (addr,))
    row = cur.fetchone()
    if row:
        print(f"  FOUND: {row[0]} = {row[1]}")
    else:
        print(f"  NOT FOUND: {addr[:30]}...")
        # Try to find similar
        cur.execute("SELECT display_name, address FROM tracked_whales WHERE address LIKE ?", (f"%{addr[:20]}%",))
        similar = cur.fetchall()
        if similar:
            print(f"    Similar: {similar[0]}")

# Check address format
print("\n[3] ADDRESS FORMAT CHECK")
api_sample = api_addrs[0] if api_addrs else ""
cur.execute("SELECT address FROM tracked_whales LIMIT 1")
db_sample = cur.fetchone()[0] if cur.fetchone() else ""
print(f"  API sample: {api_sample}")
print(f"  DB sample:  {db_sample}")
print(f"  Same format: {api_sample == db_sample}")

conn.close()
