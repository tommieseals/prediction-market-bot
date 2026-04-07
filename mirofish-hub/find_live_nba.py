import requests
import sqlite3

print("Looking for LIVE NBA games with active orderbooks...")

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Get recent NBA positions
cur.execute("""
    SELECT DISTINCT token_id, market_title, side, end_date
    FROM whale_positions 
    WHERE (market_title LIKE '%vs.%' OR market_title LIKE '%vs %')
    AND end_date >= date('now')
    AND token_id != ''
    ORDER BY detected_at DESC
    LIMIT 30
""")
rows = cur.fetchall()

print(f"Found {len(rows)} positions with future end dates")

active_markets = []
for token_id, title, side, end_date in rows:
    try:
        r = requests.get(f"https://clob.polymarket.com/book?token_id={token_id}", timeout=15)
        book = r.json()
        asks = book.get('asks', [])
        bids = book.get('bids', [])
        
        if asks and bids:
            best_ask = float(asks[0]['price'])
            best_bid = float(bids[0]['price'])
            spread = best_ask - best_bid
            
            # Active market = reasonable spread
            if spread < 0.5 and best_ask < 0.95 and best_bid > 0.05:
                print(f"\n[ACTIVE] {title} ({side})")
                print(f"  End: {end_date}")
                print(f"  Ask: ${best_ask:.3f}  Bid: ${best_bid:.3f}  Spread: {spread:.3f}")
                print(f"  Token: {token_id[:50]}...")
                active_markets.append({
                    'title': title,
                    'token_id': token_id,
                    'side': side,
                    'ask': best_ask,
                    'bid': best_bid,
                    'end_date': end_date
                })
                
                if len(active_markets) >= 5:
                    break
    except Exception as e:
        continue

print(f"\n{'='*60}")
print(f"Found {len(active_markets)} ACTIVE markets ready for trading")
