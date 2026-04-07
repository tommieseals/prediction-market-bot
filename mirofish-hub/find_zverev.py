import sqlite3
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print("=== Searching database for Cerundolo/Zverev ===")
cur.execute("""SELECT id, market_title, condition_id, token_id, side, avg_entry_price 
               FROM consensus_picks 
               WHERE market_title LIKE '%Cerundolo%' OR market_title LIKE '%Zverev%'
               ORDER BY created_at DESC LIMIT 10""")
for row in cur.fetchall():
    print(f"ID: {row[0]}")
    print(f"Title: {row[1]}")
    print(f"CID: {row[2]}")
    print(f"Token: {row[3]}")
    print(f"Side: {row[4]} @ {row[5]}")
    print("---")

conn.close()
