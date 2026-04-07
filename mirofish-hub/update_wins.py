import sqlite3

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Update BTC trade - WON (shares = payout at $1, cost = what we paid)
# pnl = payout - cost = shares * 1 - cost
cur.execute("""UPDATE my_trades SET outcome = 'won', pnl = shares - cost 
               WHERE market_title LIKE '%Bitcoin%70,000%' AND outcome = 'pending'""")
print(f"BTC updated: {cur.rowcount}")

# Update Thunder O/U - WON (we bet Under)
cur.execute("""UPDATE my_trades SET outcome = 'won', pnl = shares - cost 
               WHERE market_title LIKE '%Thunder%218.5%' AND outcome = 'pending'""")
print(f"Thunder updated: {cur.rowcount}")

# Update Cavaliers - WON
cur.execute("""UPDATE my_trades SET outcome = 'won', pnl = shares - cost 
               WHERE market_title LIKE '%Heat%Cavaliers%' AND outcome = 'pending'""")
print(f"Cavs updated: {cur.rowcount}")

conn.commit()

# Show all trades
print()
print("=== All Trades (Updated) ===")
cur.execute("SELECT market_title, side, entry_price, shares, cost, outcome, pnl FROM my_trades ORDER BY created_at DESC")
for row in cur.fetchall():
    title = row[0][:50] if row[0] else "N/A"
    pnl_str = f"+${row[6]:.2f}" if row[6] and row[6] > 0 else (f"-${abs(row[6]):.2f}" if row[6] else "N/A")
    print(f"{row[5]:8} | {title} | {row[1]} | pnl: {pnl_str}")

# Summary
print()
cur.execute("SELECT COUNT(*), SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END), SUM(pnl) FROM my_trades WHERE outcome IN ('won', 'lost')")
row = cur.fetchone()
total, wins, total_pnl = row
print(f"=== Summary ===")
print(f"Resolved: {total} | Won: {wins} | Total P&L: ${total_pnl:.2f}")

conn.close()
