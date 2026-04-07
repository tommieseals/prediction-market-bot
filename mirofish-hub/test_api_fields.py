import requests
import json
import sqlite3

# Get a whale address with positions from our DB
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()
cur.execute("""
    SELECT DISTINCT address FROM whale_positions 
    ORDER BY detected_at DESC LIMIT 5
""")
addresses = [r[0] for r in cur.fetchall()]
print(f"Testing addresses from DB: {addresses}")

for whale_addr in addresses:
    print(f"\n{'='*60}")
    print(f"Fetching positions for {whale_addr[:20]}...")
    r = requests.get(
        f"https://data-api.polymarket.com/positions?user={whale_addr}",
        timeout=30
    )
    positions = r.json()

    print(f"Got {len(positions)} positions")
    if positions:
        print("\n=== SAMPLE POSITION (first one) ===")
        pos = positions[0]
        print(json.dumps(pos, indent=2)[:2000])
        
        print("\n=== ALL KEYS ===")
        print(sorted(pos.keys()))
        
        print("\n=== KEY FIELDS ===")
        print(f"  conditionId: {pos.get('conditionId', 'NOT FOUND')}")
        print(f"  asset: {pos.get('asset', 'NOT FOUND')}")
        print(f"  title: {pos.get('title', 'NOT FOUND')[:50]}")
        break
