import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Update BTC trade (ID 5) - LOST
cur.execute("""
    UPDATE my_trades 
    SET outcome = 'lost', pnl = -cost, resolved_at = ?
    WHERE id = 5
""", (datetime.now().isoformat(),))

# Update ETH trade (ID 6) - LOST
cur.execute("""
    UPDATE my_trades 
    SET outcome = 'lost', pnl = -cost, resolved_at = ?
    WHERE id = 6
""", (datetime.now().isoformat(),))

conn.commit()

# Now show updated summary
print("=== UPDATED MY TRADES ===")
cur.execute("""
    SELECT id, market_title, side, entry_price, cost, outcome, pnl
    FROM my_trades
    ORDER BY id
""")
for row in cur.fetchall():
    pnl_str = f"+${row[6]:.2f}" if row[6] and row[6] > 0 else f"-${abs(row[6]):.2f}" if row[6] else "N/A"
    print(f"ID {row[0]}: {row[1][:40]}... | {row[2]} @ {row[3]} | ${row[4]:.2f} | {row[5]} | {pnl_str}")

# Summary
cur.execute("""
    SELECT 
        SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN outcome = 'lost' THEN 1 ELSE 0 END) as losses,
        SUM(CASE WHEN outcome = 'pending' THEN 1 ELSE 0 END) as pending,
        SUM(CASE WHEN outcome = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
        SUM(CASE WHEN outcome IN ('won', 'lost') THEN pnl ELSE 0 END) as total_pnl,
        SUM(cost) as total_invested
    FROM my_trades
""")
row = cur.fetchone()
print(f"\n=== SUMMARY ===")
print(f"Record: {row[0]}W / {row[1]}L / {row[2]} pending / {row[3]} cancelled")
print(f"Total P&L: ${row[4]:.2f}")
print(f"Total Invested: ${row[5]:.2f}")
if row[0] + row[1] > 0:
    wr = row[0] / (row[0] + row[1]) * 100
    print(f"Win Rate: {wr:.1f}%")

conn.close()
