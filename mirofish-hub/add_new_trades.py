import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Add the 2 new trades from Rusty's personal wallet (March 26)
new_trades = [
    ('Arkansas Razorbacks vs. Arizona Wildcats', 'Under', 0.51, 13.7, 6.97, 'lost', -6.97, 'NCAA Tournament - Under bet. LOST.', '2026-03-26T12:00:00'),
    ('Nebraska Cornhuskers vs. Iowa Hawkeyes', 'Nebraska Cornhuskers', 0.54, 14.8, 7.97, 'lost', -7.97, 'NCAA Tournament - Nebraska bet. LOST.', '2026-03-26T12:00:00'),
]

for t in new_trades:
    # Check if already exists
    cur.execute('SELECT id FROM my_trades WHERE market_title = ?', (t[0],))
    if not cur.fetchone():
        cur.execute('''
            INSERT INTO my_trades (market_title, side, entry_price, shares, cost, outcome, pnl, notes, created_at, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (t[0], t[1], t[2], t[3], t[4], t[5], t[6], t[7], t[8], datetime.now().isoformat()))
        print(f"Added: {t[0]}")
    else:
        print(f"Already exists: {t[0]}")

conn.commit()

# Show all trades now
print('\n' + '='*70)
print('ALL TRADES - UPDATED')
print('='*70)

cur.execute('''
    SELECT id, market_title, side, entry_price, cost, outcome, pnl
    FROM my_trades
    WHERE outcome != 'cancelled'
    ORDER BY created_at
''')

wins = 0
losses = 0
total_pnl = 0
total_cost = 0

for row in cur.fetchall():
    status = 'WON' if row[5] == 'won' else 'LOST' if row[5] == 'lost' else 'PENDING'
    pnl = row[6] if row[6] else 0
    cost = row[4] if row[4] else 0
    print(f"#{row[0]}: {row[1][:45]}")
    print(f"    {row[2]} @ ${row[3]:.2f} | Cost: ${cost:.2f} | {status} | P&L: ${pnl:.2f}")
    
    if row[5] == 'won':
        wins += 1
        total_pnl += pnl
        total_cost += cost
    elif row[5] == 'lost':
        losses += 1
        total_pnl += pnl
        total_cost += cost

print('\n' + '='*70)
print('SUMMARY')
print('='*70)
print(f"Record: {wins}W / {losses}L")
print(f"Win Rate: {wins/(wins+losses)*100:.1f}%" if wins+losses > 0 else "N/A")
print(f"Total Invested: ${total_cost:.2f}")
print(f"Total P&L: ${total_pnl:.2f}")
print(f"ROI: {(total_pnl/total_cost)*100:.1f}%" if total_cost > 0 else "N/A")

conn.close()
