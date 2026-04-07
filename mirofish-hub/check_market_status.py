import requests
import sqlite3

# Get the condition_id from our DB
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()
cur.execute("""
    SELECT DISTINCT condition_id, end_date 
    FROM whale_positions 
    WHERE market_title = 'Thunder vs. Celtics'
    LIMIT 1
""")
row = cur.fetchone()
condition_id = row[0]
end_date = row[1]
print(f"Condition ID: {condition_id}")
print(f"End date from DB: {end_date}")

# Check market on Gamma API
print("\nChecking Gamma API...")
try:
    r = requests.get(f'https://gamma-api.polymarket.com/markets?conditionId={condition_id}', timeout=30)
    markets = r.json()
    if markets:
        m = markets[0]
        print(f"Question: {m.get('question')}")
        print(f"Closed: {m.get('closed')}")
        print(f"Active: {m.get('active')}")
        print(f"End Date: {m.get('endDateIso')}")
        print(f"Current Prices: {m.get('outcomePrices')}")
        print(f"Outcomes: {m.get('outcomes')}")
        print(f"Resolution: {m.get('resolutionSource')}")
    else:
        print("Market not found on Gamma!")
except Exception as e:
    print(f"Error: {e}")

# Also check the CLOB book depth
yes_token = "107873275012767872940089881195560536670209084976663788557868940051552278053349"
print(f"\nCLOB order book for YES token:")
try:
    r = requests.get(f'https://clob.polymarket.com/book?token_id={yes_token}', timeout=30)
    book = r.json()
    print(f"Asks (sell orders): {len(book.get('asks', []))} orders")
    print(f"Bids (buy orders): {len(book.get('bids', []))} orders")
    for ask in book.get('asks', [])[:3]:
        print(f"  ASK: ${ask['price']} - size: {ask['size']}")
    for bid in book.get('bids', [])[:3]:
        print(f"  BID: ${bid['price']} - size: {bid['size']}")
except Exception as e:
    print(f"Error: {e}")
