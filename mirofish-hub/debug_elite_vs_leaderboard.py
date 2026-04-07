#!/usr/bin/env python3
"""Debug - compare elite whales vs leaderboard whales"""
import sqlite3
from polymarket_api import PolymarketAPI

print("=" * 60)
print("ELITE vs LEADERBOARD COMPARISON")
print("=" * 60)

# Top elite whales from DB
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

cur.execute("""
    SELECT address, display_name, elite_score 
    FROM tracked_whales 
    WHERE elite_score >= 60 
    ORDER BY elite_score DESC 
    LIMIT 10
""")
elite_whales = cur.fetchall()

print("\n[1] TOP ELITE WHALES (by elite_score from DB):")
elite_addrs = set()
for addr, name, score in elite_whales:
    elite_addrs.add(addr)
    print(f"  {name[:25]:25s} score={score:.1f}")

# Leaderboard whales from API
api = PolymarketAPI(rate_limit=0.5)
leaders = api.get_leaderboard(limit=50)
api.close()

print("\n[2] TOP LEADERBOARD WHALES (by PnL from API):")
leader_addrs = set()
for e in leaders[:10]:
    addr = e.get("proxyWallet") or e.get("address", "")
    name = e.get("userName") or e.get("username") or addr[:10]
    pnl = float(e.get("pnl", 0) or 0)
    leader_addrs.add(addr)
    print(f"  {name[:25]:25s} PnL=${pnl:>12,.0f}")

# Check overlap
print("\n[3] OVERLAP ANALYSIS:")
all_leader_addrs = {e.get("proxyWallet") or e.get("address", "") for e in leaders}
overlap = elite_addrs.intersection(all_leader_addrs)
print(f"  Elite whales: {len(elite_addrs)}")
print(f"  Leaderboard whales: {len(all_leader_addrs)}")
print(f"  Overlap: {len(overlap)}")

if len(overlap) < len(elite_addrs):
    missing = elite_addrs - all_leader_addrs
    print(f"\n[4] ELITE WHALES NOT IN TOP 50 LEADERBOARD:")
    for addr in list(missing)[:5]:
        cur.execute("SELECT display_name, elite_score FROM tracked_whales WHERE address = ?", (addr,))
        row = cur.fetchone()
        if row:
            print(f"  {row[0]}: score={row[1]:.1f}")

conn.close()

print("\n" + "=" * 60)
print("CONCLUSION:")
if len(overlap) < 5:
    print("  TOP ELITE WHALES ARE NOT IN LEADERBOARD!")
    print("  => whale_hunter only scans leaderboard")
    print("  => elite whales with new positions are NEVER scanned")
else:
    print("  Good overlap - elite whales are being scanned")
print("=" * 60)
