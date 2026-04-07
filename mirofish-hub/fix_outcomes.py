import sqlite3

conn = sqlite3.connect('data/whale_hunter.db', timeout=30)
cur = conn.cursor()

print("=== FIXING INCORRECT OUTCOMES ===\n")

# Thunder O/U - Combined was 228, line was 218.5 - OVER won, we bet UNDER = LOST
cur.execute("""UPDATE my_trades SET outcome = 'lost', pnl = -cost 
               WHERE market_title LIKE '%Thunder%218.5%'""")
print(f"Thunder O/U: Updated to LOST (228 > 218.5, Over won) - {cur.rowcount} row")

# Heat vs Cavaliers - Heat won 120-103, we bet Cavaliers = LOST  
cur.execute("""UPDATE my_trades SET outcome = 'lost', pnl = -cost 
               WHERE market_title LIKE '%Heat%Cavaliers%'""")
print(f"Heat/Cavs: Updated to LOST (Heat won 120-103) - {cur.rowcount} row")

conn.commit()

# Show corrected trades
print("\n=== CORRECTED TRADES ===")
cur.execute("SELECT market_title, side, outcome, pnl, cost FROM my_trades ORDER BY created_at DESC")
for row in cur.fetchall():
    title = row[0][:50] if row[0] else "N/A"
    pnl = row[3] if row[3] else 0
    pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}" if pnl < 0 else "pending"
    print(f"{row[2]:8} | {title} | {row[1]} | {pnl_str}")

# Correct summary
print("\n=== ACTUAL RECORD ===")
cur.execute("SELECT outcome, COUNT(*), SUM(pnl) FROM my_trades WHERE outcome IN ('won', 'lost') GROUP BY outcome")
for row in cur.fetchall():
    print(f"{row[0]}: {row[1]} trades, P&L: ${row[2]:.2f}")

cur.execute("SELECT SUM(pnl) FROM my_trades WHERE outcome IN ('won', 'lost')")
total = cur.fetchone()[0] or 0
print(f"\nNet P&L: ${total:.2f}")

conn.close()
