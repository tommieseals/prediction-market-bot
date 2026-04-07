import sqlite3
import requests

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Get Nuggets vs Suns tokens
cur.execute("""
    SELECT token_id, side, size_usd, entry_price
    FROM whale_positions 
    WHERE market_title = 'Nuggets vs. Suns'
    AND end_date LIKE '2026-03-25%'
""")
rows = cur.fetchall()

print(f"Nuggets vs. Suns positions ({len(rows)} total):\n")

yes_token = None
no_token = None

for token, side, size, entry in rows:
    print(f"  {side}: ${size:,.0f} @ ${entry:.3f}")
    print(f"    Token: {token[:50]}...")
    if side == 'YES':
        yes_token = token
    else:
        no_token = token

# Check BOTH tokens on CLOB
print("\n" + "="*50)
print("CLOB Order Book Check:\n")

for label, token in [("YES", yes_token), ("NO", no_token)]:
    if token:
        r = requests.get(f"https://clob.polymarket.com/book?token_id={token}", timeout=15)
        book = r.json()
        asks = book.get('asks', [])
        bids = book.get('bids', [])
        
        print(f"{label} token:")
        print(f"  Asks: {len(asks)}, Bids: {len(bids)}")
        if asks:
            for a in asks[:3]:
                print(f"    ASK: ${a['price']} x {float(a['size']):,.0f}")
        if bids:
            for b in bids[:3]:
                print(f"    BID: ${b['price']} x {float(b['size']):,.0f}")
        print()

# Also fetch fresh data from Data API
print("="*50)
print("Fresh check from Data API...\n")

# Find a whale with this position
cur.execute("""
    SELECT DISTINCT address FROM whale_positions 
    WHERE market_title = 'Nuggets vs. Suns' LIMIT 1
""")
addr = cur.fetchone()[0]

r = requests.get(f"https://data-api.polymarket.com/positions?user={addr}", timeout=30)
positions = r.json()

for pos in positions:
    if 'nuggets' in pos.get('title', '').lower() and 'suns' in pos.get('title', '').lower():
        print(f"Live position: {pos.get('title')}")
        print(f"  Token: {pos.get('asset', '')[:50]}...")
        print(f"  Current price: ${pos.get('curPrice', 'N/A')}")
        print(f"  End date: {pos.get('endDate')}")
        print(f"  Redeemable: {pos.get('redeemable')}")
