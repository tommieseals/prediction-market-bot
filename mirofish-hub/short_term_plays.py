#!/usr/bin/env python3
"""Find short-term whale plays"""
import sqlite3

conn = sqlite3.connect('data/whale_hunter.db', timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
    SELECT wp.*, tw.display_name, tw.elite_score, tw.pnl
    FROM whale_positions wp
    LEFT JOIN tracked_whales tw ON wp.address = tw.address
    WHERE wp.outcome = 'pending' 
      AND tw.elite_score >= 50
    ORDER BY tw.elite_score DESC, wp.size_usd DESC
""")

positions = cur.fetchall()

# Keywords for filtering
long_term = ['finals', 'championship', 'world cup', 'election', 'president', '2027', '2028', 'gta vi']

print('='*70)
print('[TARGET] SHORT-TERM WHALE PLAYS (Next Few Days)')
print('='*70)

count = 0
for p in positions:
    market = p['market_title'].lower()
    
    # Skip long-term
    if any(kw in market for kw in long_term):
        continue
    
    # Skip resolved (price near 0 or 1)
    current = p['current_price']
    if current >= 0.98 or current <= 0.02:
        continue
    
    score = p['elite_score'] or 0
    name = (p['display_name'] or p['address'][:12])[:18]
    side = p['side']
    entry = p['entry_price']
    size = p['size_usd']
    pnl = p['unrealized_pnl'] or 0
    market_title = p['market_title'][:55]
    
    # Flag underdogs
    flag = ''
    if side == 'YES' and current < 0.45:
        flag = ' [HOT]'
    elif side == 'NO' and current > 0.55:
        flag = ' [HOT]'
    
    print(f"\n[WHALE] {name} (Score: {score:.1f})")
    print(f"   {market_title}")
    print(f"   {side} @ ${entry:.2f} → ${current:.2f} | Size: ${size:,.0f} | P&L: ${pnl:+,.0f}{flag}")
    
    count += 1
    if count >= 20:
        break

conn.close()
print(f"\n{'='*70}")
print(f"Found {count} short-term plays from elite whales (Score 50+)")
print(f"Your capital: $77.36 USDC")
print('='*70)
