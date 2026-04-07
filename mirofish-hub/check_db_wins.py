#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('C:/Users/USER/clawd/mirofish-hub/data/whale_hunter.db')
cur = conn.cursor()

print('=== ALL WON POSITIONS IN DATABASE ===')
cur.execute("""
    SELECT wp.id, tw.display_name, wp.market_title, wp.detected_at, wp.actual_pnl
    FROM whale_positions wp
    LEFT JOIN tracked_whales tw ON wp.address = tw.address
    WHERE wp.outcome = 'won'
    ORDER BY wp.detected_at DESC
""")
for row in cur.fetchall():
    whale = row[1] or 'Unknown'
    market = (row[2] or '')[:40]
    date = (row[3] or '')[:10]
    pnl = row[4] or 0
    print(f'ID {row[0]:3d}: {whale:15s} | {market:40s} | {date} | ${pnl:,.0f}')

print()
cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'won'")
print(f'Total won in DB: {cur.fetchone()[0]}')

cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'lost'")
print(f'Total lost in DB: {cur.fetchone()[0]}')

cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'pending' OR outcome IS NULL")
print(f'Total pending in DB: {cur.fetchone()[0]}')

print('\n=== EXPORT LIMIT ISSUE ===')
cur.execute("SELECT MIN(id), MAX(id) FROM whale_positions")
minmax = cur.fetchone()
print(f'Position ID range: {minmax[0]} to {minmax[1]}')

cur.execute("SELECT id FROM whale_positions WHERE outcome = 'won' ORDER BY id")
won_ids = [r[0] for r in cur.fetchall()]
print(f'Won position IDs: {won_ids}')

conn.close()
