#!/usr/bin/env python
import sqlite3
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Get the most recent position with whale username
cur.execute('''
SELECT 
    w.display_name,
    w.elite_score,
    w.pnl,
    p.market_title,
    p.side,
    p.entry_price,
    p.size_usd,
    p.detected_at,
    p.end_date
FROM whale_positions p
LEFT JOIN tracked_whales w ON p.address = w.address
ORDER BY p.detected_at DESC
LIMIT 10
''')

print('=== 10 MOST RECENT WHALE POSITIONS ===\n')
for row in cur.fetchall():
    username, elite_score, pnl, market, side, price, size, detected, end_date = row
    print(f"WHALE: {username or 'Unknown'} (Elite: {elite_score or 'N/A'}, PnL: ${pnl or 0:,.0f})")
    print(f"   📊 {market}")
    print(f"   {side} @ ${price or 0:.3f} | Size: ${size or 0:,.0f}")
    print(f"   Detected: {detected}")
    print(f"   End Date: {end_date or 'N/A'}")
    print()
