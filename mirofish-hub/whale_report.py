#!/usr/bin/env python3
"""Generate whale report for Rusty"""
import sqlite3
import json
from collections import defaultdict

db_path = 'data/whale_hunter.db'
conn = sqlite3.connect(db_path, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get tracked whales
cur.execute("SELECT * FROM tracked_whales ORDER BY elite_score DESC LIMIT 20")
tracked = cur.fetchall()

print("=" * 70)
print("[WHALE] WHALE HUNTER REPORT")
print("=" * 70)

# Top whales by elite score
print("\n[STATS] TOP WHALES BY ELITE SCORE")
print("-" * 70)
print(f"{'Whale':<25} {'PnL':>12} {'Score':>7} {'Positions':>10}")
print("-" * 70)

whale_addrs = {}
for w in tracked:
    name = (w['display_name'] or w['address'][:15])[:25]
    pnl = w['pnl'] or 0
    score = w['elite_score'] or 0
    whale_addrs[w['address']] = {'name': name, 'score': score, 'pnl': pnl}
    
    # Count positions
    cur.execute("SELECT COUNT(*) FROM whale_positions WHERE address = ? AND outcome = 'pending'", (w['address'],))
    pos_count = cur.fetchone()[0]
    
    print(f"{name:<25} ${pnl:>11,.0f} {score:>7} {pos_count:>10}")

# Get active positions (pending outcome)
print("\n\n[TARGET] ACTIVE WHALE POSITIONS (Pending)")
print("-" * 70)

cur.execute("""
    SELECT wp.*, tw.display_name, tw.elite_score 
    FROM whale_positions wp
    LEFT JOIN tracked_whales tw ON wp.address = tw.address
    WHERE wp.outcome = 'pending'
    ORDER BY tw.elite_score DESC, wp.size_usd DESC
""")

positions = cur.fetchall()
print(f"{'Whale':<18} {'Score':>5} {'Side':>4} {'Entry':>6} {'Now':>6} {'Size':>10} {'Market':<30}")
print("-" * 70)

for p in positions[:25]:
    name = (p['display_name'] or p['address'][:12])[:18]
    score = p['elite_score'] or 0
    side = p['side']
    entry = p['entry_price']
    current = p['current_price']
    size = p['size_usd']
    market = p['market_title'][:30]
    
    # Highlight good opportunities (whale score 50+ and favorable odds)
    flag = ""
    if score >= 55 and side == "YES" and current < 0.5:
        flag = " [HOT] UNDERDOG"
    elif score >= 55 and side == "NO" and current > 0.5:
        flag = " [HOT] FADE"
    
    print(f"{name:<18} {score:>5} {side:>4} ${entry:>5.2f} ${current:>5.2f} ${size:>9,.0f} {market}{flag}")

# Summary of best opportunities
print("\n\n🎰 BEST OPPORTUNITIES (Score 50+ & Unlikely Odds)")
print("-" * 70)

cur.execute("""
    SELECT wp.*, tw.display_name, tw.elite_score 
    FROM whale_positions wp
    LEFT JOIN tracked_whales tw ON wp.address = tw.address
    WHERE wp.outcome = 'pending' 
      AND tw.elite_score >= 50
    ORDER BY tw.elite_score DESC, wp.size_usd DESC
""")

best = cur.fetchall()
for p in best:
    score = p['elite_score'] or 0
    side = p['side']
    current = p['current_price']
    
    # Only show unlikely bets (underdog YES or favorite NO)
    is_underdog = (side == "YES" and current < 0.45) or (side == "NO" and current > 0.55)
    
    if is_underdog:
        name = (p['display_name'] or p['address'][:12])[:20]
        entry = p['entry_price']
        size = p['size_usd']
        market = p['market_title'][:50]
        pnl = p['unrealized_pnl'] or 0
        
        implied_prob = current if side == "YES" else (1 - current)
        potential = (size / current) - size if side == "YES" else (size / (1-current)) - size
        
        print(f"\n[WHALE] {name} (Score: {score})")
        print(f"   Market: {market}")
        print(f"   Position: {side} @ ${entry:.3f} → Now ${current:.3f}")
        print(f"   Size: ${size:,.0f} | Unrealized P&L: ${pnl:+,.0f}")
        print(f"   Implied Prob: {implied_prob:.0%} | Potential Win: ${potential:,.0f}")

conn.close()

print("\n" + "=" * 70)
print("[MONEY] YOUR CAPITAL: $77.36 USDC")
print("[WARN]  REPORT ONLY - No trades executed")
print("=" * 70)
