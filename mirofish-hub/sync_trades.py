"""Sync all Polymarket trades to my_trades table"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Our actual Polymarket activity (from API)
trades = [
    {
        'id': 1,
        'market_title': 'Lakers vs. Pistons',
        'side': 'Pistons (NO)',
        'entry_price': 0.49,
        'cost': 12.25,
        'shares': 25.0,
        'outcome': 'won',
        'pnl': 12.75,  # Redeemed $25
        'created_at': '2026-03-23T15:00:00',
        'notes': 'First real trade. Pistons won 113-110. Redeemed!'
    },
    {
        'id': 3,
        'market_title': 'Thunder vs. Celtics: O/U 218.5',
        'side': 'Under',
        'entry_price': 0.47,
        'cost': 20.21,
        'shares': 43.01,
        'outcome': 'lost',
        'pnl': -20.21,
        'created_at': '2026-03-25T15:41:00',
        'notes': 'Whale consensus: GamblingIsAllYouNeed + RN1 on UNDER. Game went OVER.'
    },
    {
        'id': 4,
        'market_title': 'Heat vs. Cavaliers',
        'side': 'Cavaliers',
        'entry_price': 0.58,
        'cost': 20.17,
        'shares': 34.78,
        'outcome': 'lost',
        'pnl': -20.17,
        'created_at': '2026-03-25T15:41:00',
        'notes': 'Whale consensus: swisstony, GamblingIsAllYouNeed on Cavs. Heat won.'
    },
    {
        'id': 5,
        'market_title': 'Will the price of Bitcoin be above $70,000 on March 26?',
        'side': 'Yes',
        'entry_price': 0.757,
        'cost': 15.04,
        'shares': 19.69,
        'outcome': 'lost',
        'pnl': -15.04,
        'created_at': '2026-03-25T16:10:00',
        'notes': 'Crypto play - BTC was $71k at entry. Dropped to $66k. LOST.'
    },
    {
        'id': 6,
        'market_title': 'Will the price of Ethereum be above $2,100 on March 26?',
        'side': 'Yes',
        'entry_price': 0.87,
        'cost': 15.26,
        'shares': 17.48,
        'outcome': 'lost',
        'pnl': -15.26,
        'created_at': '2026-03-25T16:10:00',
        'notes': 'Crypto play - ETH was $2,166 at entry. Dropped to $1,986. LOST.'
    }
]

# Update each trade
for t in trades:
    cur.execute("""
        UPDATE my_trades 
        SET outcome = ?, pnl = ?, notes = ?, resolved_at = ?
        WHERE id = ?
    """, (t['outcome'], t['pnl'], t['notes'], datetime.now().isoformat(), t['id']))

conn.commit()

# Show final state
print("=" * 70)
print("📊 ALL POLYMARKET TRADES (SYNCED)")
print("=" * 70)

cur.execute("""
    SELECT id, market_title, side, entry_price, cost, shares, outcome, pnl, notes
    FROM my_trades
    WHERE outcome != 'cancelled'
    ORDER BY created_at
""")

total_cost = 0
total_pnl = 0
wins = 0
losses = 0

for row in cur.fetchall():
    status = "✅ WON" if row[6] == 'won' else "❌ LOST" if row[6] == 'lost' else "⏳ PENDING"
    pnl_str = f"+${row[7]:.2f}" if row[7] > 0 else f"-${abs(row[7]):.2f}" if row[7] else "$0.00"
    
    print(f"\n#{row[0]}: {row[1]}")
    print(f"   Side: {row[2]} @ ${row[3]:.2f} | Cost: ${row[4]:.2f} | Shares: {row[5]:.2f}")
    print(f"   Status: {status} | P&L: {pnl_str}")
    print(f"   Notes: {row[8]}")
    
    if row[6] in ('won', 'lost'):
        total_cost += row[4]
        total_pnl += row[7] if row[7] else 0
        if row[6] == 'won':
            wins += 1
        else:
            losses += 1

print("\n" + "=" * 70)
print("📈 SUMMARY")
print("=" * 70)
print(f"Record: {wins}W / {losses}L")
print(f"Win Rate: {wins/(wins+losses)*100:.1f}%" if wins+losses > 0 else "N/A")
print(f"Total Invested: ${total_cost:.2f}")
print(f"Total P&L: ${total_pnl:.2f}")
print(f"ROI: {(total_pnl/total_cost)*100:.1f}%" if total_cost > 0 else "N/A")

conn.close()
