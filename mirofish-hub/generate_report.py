#!/usr/bin/env python3
"""Generate wins/losses report for desktop."""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('C:/Users/USER/clawd/mirofish-hub/data/whale_hunter.db')
cur = conn.cursor()

output = []
output.append('=' * 80)
output.append('WHALE TRACKER - WINS & LOSSES REPORT')
output.append(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
output.append('=' * 80)

# Summary stats
cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'won'")
won = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'lost'")
lost = cur.fetchone()[0]
cur.execute("SELECT SUM(actual_pnl) FROM whale_positions WHERE outcome IN ('won', 'lost')")
total_pnl = cur.fetchone()[0] or 0

output.append('')
output.append('SUMMARY')
output.append('-' * 40)
output.append(f'Total Resolved: {won + lost}')
output.append(f'Wins: {won}')
output.append(f'Losses: {lost}')
output.append(f'Win Rate: {won/(won+lost)*100:.1f}%')
output.append(f'Total P&L: ${total_pnl:,.2f}')
output.append('')

# WINS
output.append('=' * 80)
output.append(f'WINS ({won} total)')
output.append('=' * 80)

cur.execute("""
    SELECT 
        tw.display_name as whale,
        wp.market_title,
        wp.side,
        wp.entry_price,
        wp.size_usd,
        wp.actual_pnl,
        wp.detected_at
    FROM whale_positions wp
    LEFT JOIN tracked_whales tw ON wp.address = tw.address
    WHERE wp.outcome = 'won'
    ORDER BY wp.actual_pnl DESC
""")

for i, row in enumerate(cur.fetchall(), 1):
    whale, market, side, price, size, pnl, detected = row
    output.append('')
    output.append(f'WIN #{i}')
    output.append(f'  Whale: {whale}')
    output.append(f'  Market: {market}')
    output.append(f'  Position: {side} @ ${price:.4f}')
    output.append(f'  Size: ${size:,.2f}')
    output.append(f'  P&L: +${pnl:,.2f}')
    output.append(f'  Date: {detected}')

# LOSSES
output.append('')
output.append('=' * 80)
output.append(f'LOSSES ({lost} total)')
output.append('=' * 80)

cur.execute("""
    SELECT 
        tw.display_name as whale,
        wp.market_title,
        wp.side,
        wp.entry_price,
        wp.size_usd,
        wp.actual_pnl,
        wp.detected_at
    FROM whale_positions wp
    LEFT JOIN tracked_whales tw ON wp.address = tw.address
    WHERE wp.outcome = 'lost'
    ORDER BY wp.actual_pnl ASC
""")

for i, row in enumerate(cur.fetchall(), 1):
    whale, market, side, price, size, pnl, detected = row
    pnl = pnl or 0
    output.append('')
    output.append(f'LOSS #{i}')
    output.append(f'  Whale: {whale}')
    output.append(f'  Market: {market}')
    output.append(f'  Position: {side} @ ${price:.4f}')
    output.append(f'  Size: ${size:,.2f}')
    output.append(f'  P&L: -${abs(pnl):,.2f}')
    output.append(f'  Date: {detected}')

conn.close()

# Write to desktop
desktop_path = 'C:/Users/User/Desktop/whale_wins_losses.txt'
with open(desktop_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print(f'Saved to Desktop: whale_wins_losses.txt')
print(f'Total entries: {won} wins, {lost} losses')
