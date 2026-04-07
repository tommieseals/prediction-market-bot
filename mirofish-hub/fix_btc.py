import sqlite3
conn = sqlite3.connect('data/whale_hunter.db', timeout=30)
cur = conn.cursor()

# Fix BTC - set back to pending since market not resolved yet
cur.execute("UPDATE my_trades SET outcome = 'pending', pnl = NULL WHERE market_title LIKE '%Bitcoin%70,000%'")
print(f"BTC updated to PENDING: {cur.rowcount}")

conn.commit()

# Show final state
print()
print("=== FINAL VERIFIED STATE ===")
cur.execute("SELECT market_title, side, outcome, pnl FROM my_trades ORDER BY created_at DESC")
for row in cur.fetchall():
    title = row[0][:45] if row[0] else "N/A"
    pnl = f"+${row[3]:.2f}" if row[3] and row[3] > 0 else (f"-${abs(row[3]):.2f}" if row[3] and row[3] < 0 else "pending")
    print(f"{row[2]:9} | {title} | {row[1]} | {pnl}")

# Summary
cur.execute("SELECT SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END), SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END), SUM(pnl) FROM my_trades")
row = cur.fetchone()
print()
print(f"Record: {row[0] or 0}W - {row[1] or 0}L")
print(f"Net P&L: ${row[2] or 0:.2f}")

conn.close()
