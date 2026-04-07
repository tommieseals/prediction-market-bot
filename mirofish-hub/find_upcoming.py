import sqlite3
import requests
from datetime import datetime

print(f"Current: {datetime.now()}")
print("Finding UPCOMING games (not resolved)...\n")

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Get ALL positions from last 24h and check which are still tradeable
cur.execute("""
    SELECT DISTINCT token_id, market_title, side, end_date, size_usd
    FROM whale_positions 
    WHERE detected_at > datetime('now', '-24 hours')
    AND (market_title LIKE '%vs.%' OR market_title LIKE '%vs %')
    ORDER BY size_usd DESC
    LIMIT 50
""")

rows = cur.fetchall()
print(f"Checking {len(rows)} recent positions...\n")

tradeable = []
for token, title, side, end_date, size in rows:
    try:
        r = requests.get(f"https://clob.polymarket.com/book?token_id={token}", timeout=10)
        book = r.json()
        asks = book.get('asks', [])
        bids = book.get('bids', [])
        
        if asks and bids:
            best_ask = float(asks[0]['price'])
            best_bid = float(bids[0]['price'])
            
            # Tradeable = has liquidity at reasonable prices
            if best_bid > 0.10 and best_ask < 0.90:
                tradeable.append({
                    'title': title,
                    'token': token,
                    'side': side,
                    'ask': best_ask,
                    'bid': best_bid,
                    'size': size,
                    'end_date': end_date
                })
                print(f"[TRADEABLE] {title}")
                print(f"  {side} @ Ask ${best_ask:.2f} / Bid ${best_bid:.2f}")
                print(f"  Size: ${size:,.0f} | End: {end_date}")
                print(f"  Token: {token[:40]}...")
                print()
                
                if len(tradeable) >= 5:
                    break
    except Exception as e:
        continue

print("="*50)
print(f"Found {len(tradeable)} TRADEABLE markets")

if not tradeable:
    print("\nNo tradeable sports markets found!")
    print("Possible reasons:")
    print("  1. All games in DB are already resolved")
    print("  2. Need to scan for new whale positions")
    print("  3. Markets haven't opened yet for tonight's games")
