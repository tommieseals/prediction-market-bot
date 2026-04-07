import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/whale_hunter.db', timeout=30)
cur = conn.cursor()

trades = [
    {
        'market_title': 'Will the price of Bitcoin be above $70,000 on March 26?',
        'condition_id': '0x5ebf0e6b2bd070e527124bb70f9162288f325ea68dc645b7c777ca0da9a1ccee',
        'side': 'Yes',
        'entry_price': 0.755,
        'shares': 19.86,
        'cost': 15.04,
        'notes': 'Crypto play - BTC at $71k, 1.4% buffer above threshold'
    },
    {
        'market_title': 'Will the price of Ethereum be above $2,100 on March 26?',
        'condition_id': '0x1620faf803551d45a828b63536125851aee9e069acda72fe08f4b2ebd2761b13',
        'side': 'Yes',
        'entry_price': 0.855,
        'shares': 17.54,
        'cost': 15.26,
        'notes': 'Crypto play - ETH at $2166, 3.1% buffer above threshold'
    }
]

for t in trades:
    cur.execute('SELECT id FROM my_trades WHERE condition_id = ? AND side = ?', 
                (t['condition_id'], t['side']))
    if cur.fetchone():
        print(f"Already logged: {t['market_title'][:40]}")
        continue
    
    cur.execute('''
        INSERT INTO my_trades (market_title, condition_id, side, entry_price, 
                               shares, cost, outcome, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    ''', (t['market_title'], t['condition_id'], t['side'], t['entry_price'],
          t['shares'], t['cost'], t['notes'], datetime.now().isoformat()))
    print(f"Logged: {t['market_title'][:40]}")

conn.commit()

# Show all pending trades
print("\n=== ALL PENDING TRADES ===")
cur.execute("SELECT id, market_title, side, entry_price, shares, cost FROM my_trades WHERE outcome = 'pending' ORDER BY id")
for r in cur.fetchall():
    print(f"#{r[0]} | {r[1][:45]} | {r[2]} @ {r[3]:.2f} | {r[4]:.1f} shares | ${r[5]:.2f}")

conn.close()
