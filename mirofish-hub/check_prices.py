import sqlite3

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

cur.execute("""
    SELECT market_title, current_price, outcome, entry_price
    FROM whale_positions 
    WHERE market_title LIKE '%Guerrieri%' 
       OR market_title LIKE '%Korda%Landaluce%'
       OR market_title LIKE '%Vacherot%Fils%'
    LIMIT 15
""")

print("Market | Current Price | Outcome | Entry Price")
print("-" * 70)
for row in cur.fetchall():
    market = row[0][:40] if row[0] else "N/A"
    current = row[1]
    outcome = row[2]
    entry = row[3]
    print(f"{market} | {current} | {outcome} | {entry}")

conn.close()
