import requests

# Check what Polymarket says about the Bucks/Mavericks markets
print("=== GAMMA API: Current Bucks/Mavericks Markets ===\n")

resp = requests.get(
    "https://gamma-api.polymarket.com/events",
    params={"tag": "nba", "limit": 20}
)

if resp.ok:
    events = resp.json()
    for e in events:
        title = e.get("title", "")
        if "Bucks" in title or "Mavericks" in title:
            print(f"Event: {title}")
            print(f"  End Date: {e.get('endDate')}")
            print(f"  Closed: {e.get('closed')}")
            print(f"  Active: {e.get('active')}")
            print()
else:
    print(f"API Error: {resp.status_code}")

# Check specific condition from our DB
print("\n=== DB CONDITION CHECK ===\n")
import sqlite3
conn = sqlite3.connect('C:/Users/USER/clawd/mirofish-hub/data/whale_hunter.db')
cur = conn.cursor()

cur.execute("""
    SELECT market_title, condition_id, end_date, token_id, detected_at
    FROM whale_positions 
    WHERE market_title LIKE '%Bucks%' AND market_title LIKE '%Mavericks%'
    LIMIT 5
""")

for row in cur.fetchall():
    print(f"Title: {row[0]}")
    print(f"  Condition: {row[1][:30]}...")
    print(f"  DB end_date: {row[2]}")
    print(f"  Detected: {row[4]}")
    
    # Look up this condition on Gamma
    if row[1]:
        r2 = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"condition_id": row[1]},
            timeout=10
        )
        if r2.ok and r2.json():
            m = r2.json()[0] if isinstance(r2.json(), list) else r2.json()
            print(f"  GAMMA endDate: {m.get('endDate')}")
            print(f"  GAMMA closed: {m.get('closed')}")
    print()

conn.close()
