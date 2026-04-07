import requests
import sqlite3

# Check current market price
condition = '0x9f8ff09142e006b13e263d07b6c8813e89327ba79bd73f7f3cee6a2ef88903c4'
resp = requests.get(f'https://clob.polymarket.com/markets/{condition}', timeout=15)
market = resp.json()

print('=== HAWKS vs PISTONS ===')
print(f"Status: Active={market.get('active')}, Accepting={market.get('accepting_orders')}")
print()

for t in market.get('tokens', []):
    price = float(t['price'])
    print(f"{t['outcome']}: {price:.1%} implied probability")

# Get whale details
conn = sqlite3.connect('data/whale_hunter.db', timeout=30)
cur = conn.cursor()

print()
print('=== WHALES BACKING HAWKS ===')
cur.execute('''
    SELECT w.display_name, w.elite_score, w.pnl, w.tracked_accuracy, w.num_trades,
           p.side, p.entry_price
    FROM whale_positions p
    JOIN tracked_whales w ON p.address = w.address
    WHERE p.market_title LIKE '%Hawks%Pistons%'
    AND p.outcome = 'pending'
    AND p.side = 'YES'
    ORDER BY w.elite_score DESC
''')

total_acc = 0
count = 0
for r in cur.fetchall():
    acc = r[3] if r[3] else 0
    pnl = r[2] if r[2] else 0
    total_acc += acc
    count += 1
    print(f"{r[0][:20]:20} | Score: {r[1]:.1f} | PnL: ${pnl:,.0f} | Accuracy: {acc:.0%} | {r[4]} trades")

if count > 0:
    print(f"\nAverage whale accuracy: {total_acc/count:.0%}")

conn.close()
