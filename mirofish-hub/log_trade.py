#!/usr/bin/env python3
"""Log our trades to the my_trades table for dashboard tracking"""

import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Log today's trades to my_trades
trades = [
    {
        'market_title': 'Thunder vs. Celtics: O/U 218.5',
        'condition_id': '0x46c72d5cb92972c2d20d24f6ba68065a10545853557d0474cc73a88a718428f4',
        'token_id': '59862632585511436198857766530429981952248716030567258213873926483088936736967',
        'side': 'Under',
        'entry_price': 0.465,
        'shares': 43.01,
        'cost': 20.21,
        'outcome': 'pending',
        'notes': 'Whale consensus: GamblingIsAllYouNeed (77.4) + RN1 (75.2) on UNDER'
    },
    {
        'market_title': 'Heat vs. Cavaliers',
        'condition_id': '0xc75831d24fabad4f6ff9dc932a177b5a611d769a704b4ee446eb57add7a8fd51',
        'token_id': '34326703115443615628960033141108165169035598058847574486267724099478822539',
        'side': 'Cavaliers',
        'entry_price': 0.575,
        'shares': 34.78,
        'cost': 20.17,
        'outcome': 'pending',
        'notes': 'Whale consensus: swisstony (79.7), GamblingIsAllYouNeed (77.4) on Cavs'
    }
]

for t in trades:
    # Check if already logged (by condition_id and side)
    cur.execute('SELECT id FROM my_trades WHERE condition_id = ? AND side = ?', 
                (t['condition_id'], t['side']))
    if cur.fetchone():
        print(f"Trade already logged: {t['market_title']} - {t['side']}")
        continue
    
    cur.execute('''
        INSERT INTO my_trades (market_title, condition_id, token_id, side, entry_price, 
                               shares, cost, outcome, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (t['market_title'], t['condition_id'], t['token_id'], t['side'], t['entry_price'],
          t['shares'], t['cost'], t['outcome'], t['notes'], datetime.now().isoformat()))
    print(f"Logged: {t['market_title']} - {t['side']}")

conn.commit()

# Show all trades
print('\n=== MY TRADES ===')
cur.execute('''SELECT id, market_title, side, entry_price, shares, cost, outcome, created_at 
               FROM my_trades ORDER BY id DESC''')
for r in cur.fetchall():
    print(f"#{r[0]} | {r[1][:35]:35} | {r[2]:10} | @{r[3]:.2f} | {r[4]:.1f} shares | ${r[5]:.2f} | {r[6]}")

conn.close()
print('\nDone!')
