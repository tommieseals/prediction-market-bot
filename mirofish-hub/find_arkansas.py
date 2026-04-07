import sqlite3
import requests

# Check database for Arkansas picks
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Check consensus_picks with correct columns
cur.execute("SELECT * FROM consensus_picks WHERE market_title LIKE '%Arkansas%' OR market_title LIKE '%arkansas%'")
rows = cur.fetchall()
print("=== From consensus_picks ===")
for r in rows:
    print(r)

conn.close()

# Also search Gamma API more thoroughly
print("\n=== Searching Gamma API ===")
r = requests.get('https://gamma-api.polymarket.com/markets?closed=false&limit=500')
markets = r.json()
arkansas = [m for m in markets if 'arkansas' in str(m).lower()]
print(f"Found {len(arkansas)} Arkansas markets")
for m in arkansas[:5]:
    print(f"Title: {m.get('question')}")
    print(f"Condition ID: {m.get('conditionId')}")
    print(f"Tokens: {m.get('clobTokenIds')}")
    print(f"Outcome Prices: {m.get('outcomePrices')}")
    print("---")
