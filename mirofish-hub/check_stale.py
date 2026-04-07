import sqlite3
import requests

# Check if these "consensus picks" are actually resolved
markets = [
    "Sebastian Korda vs Martin Landaluce",
    "Valentin Vacherot vs Arthur Fils", 
    "Andrea Guerrieri vs Stefano Travaglia"
]

print("=== CHECKING CONSENSUS PICK STALENESS ===\n")

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

for market in markets:
    cur.execute("""
        SELECT market_title, side, current_price, outcome, end_date, detected_at 
        FROM whale_positions 
        WHERE market_title LIKE ? 
        ORDER BY detected_at DESC LIMIT 3
    """, (f'%{market}%',))
    
    rows = cur.fetchall()
    print(f"--- {market} ---")
    for row in rows:
        print(f"  Side: {row[1]}, Price: {row[2]}, Outcome: {row[3]}, End: {row[4]}")
        if row[2] is not None and (row[2] >= 0.99 or row[2] <= 0.01):
            print(f"  ** RESOLVED! Price at {row[2]} but outcome={row[3]} **")
    print()

conn.close()

# Now check via Gamma API if these are actually resolved
print("=== CHECKING GAMMA API FOR LIVE STATUS ===\n")
try:
    # Get the condition IDs we're tracking
    conn = sqlite3.connect('data/whale_hunter.db')
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT condition_id, market_title 
        FROM whale_positions 
        WHERE market_title LIKE '%Korda%' OR market_title LIKE '%Vacherot%' OR market_title LIKE '%Guerrieri%'
        LIMIT 5
    """)
    for cid, mkt in cur.fetchall():
        print(f"Condition: {cid[:20]}... Market: {mkt[:50]}")
        # Check if resolved on Gamma
        try:
            r = requests.get(f"https://gamma-api.polymarket.com/markets?condition_id={cid}", timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data:
                    m = data[0]
                    print(f"  closed={m.get('closed')}, resolved={m.get('resolved')}, outcome={m.get('outcome')}")
        except Exception as e:
            print(f"  API error: {e}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
