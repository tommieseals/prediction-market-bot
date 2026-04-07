import requests
import sqlite3

# Check IP first
r = requests.get('https://api.ipify.org', timeout=10)
print(f"Current IP: {r.text}")

# Try to get live sports markets directly from Data API
print("\nFetching live positions from a whale...")

# Try multiple whales
test_addrs = [
    "0x66fbe4344c1a9f6029a4e40ffd5ca7848e189f72",
    "0xb27bc932bf8110d8f78e55da7d5f0497a18b5b82",
]

for addr in test_addrs:
    r = requests.get(
        f"https://data-api.polymarket.com/positions?user={addr}",
        timeout=30
    )
    positions = r.json()
    
    # Find active NBA/NHL positions
    for pos in positions:
        title = pos.get('title', '')
        cur_price = float(pos.get('curPrice', 0.5))
        token = pos.get('asset', '')
        end_date = pos.get('endDate', '')
        
        # Look for sports with reasonable prices
        if ('vs' in title.lower() or 'spread' in title.lower() or 'o/u' in title.lower()):
            if 0.1 < cur_price < 0.9 and '2026-03-2' in str(end_date):
                print(f"\n[CANDIDATE] {title}")
                print(f"  Price: ${cur_price:.3f}")
                print(f"  End: {end_date}")
                print(f"  Token: {token[:50]}...")
                
                # Check CLOB
                r2 = requests.get(f"https://clob.polymarket.com/book?token_id={token}", timeout=15)
                book = r2.json()
                asks = book.get('asks', [])
                bids = book.get('bids', [])
                
                if asks and bids:
                    best_ask = float(asks[0]['price'])
                    best_bid = float(bids[0]['price'])
                    if 0.1 < best_bid and best_ask < 0.9:
                        print(f"  CLOB: Ask ${best_ask:.3f} / Bid ${best_bid:.3f}")
                        print(f"  [TRADEABLE!]")
                        break
    else:
        continue
    break
