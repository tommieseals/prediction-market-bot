"""
Quick market scan - get open markets and cross-reference with whale DB
"""
import requests
import json
import sqlite3
from datetime import datetime

print(f"=== QUICK MARKET SCAN ===")
print(f"Time: {datetime.now()}\n")

# Step 1: Get ALL open markets in one call
url = 'https://gamma-api.polymarket.com/markets?_limit=500&active=true&closed=false'
r = requests.get(url, timeout=30)
markets = r.json()
print(f"Got {len(markets)} open markets from Polymarket\n")

# Build lookup by condition_id
open_markets = {}
for m in markets:
    cid = m.get('conditionId')
    if cid:
        prices_raw = m.get('outcomePrices', '[]')
        if isinstance(prices_raw, str):
            prices = json.loads(prices_raw)
        else:
            prices = prices_raw
        
        if prices and len(prices) > 0:
            try:
                yes_price = float(prices[0])
                if yes_price > 0:
                    open_markets[cid] = {
                        'question': m.get('question', ''),
                        'yes': yes_price,
                        'no': float(prices[1]) if len(prices) > 1 else 1 - yes_price,
                        'volume': m.get('volumeNum', 0),
                        'slug': m.get('slug', '')
                    }
            except:
                pass

print(f"Indexed {len(open_markets)} markets with valid prices\n")

# Step 2: Check our whale DB for positions matching open markets
conn = sqlite3.connect(r'C:\Users\USER\clawd\mirofish-hub\data\whale_hunter.db')
cur = conn.cursor()

cur.execute("""
    SELECT condition_id, market_title, side, COUNT(*) as whale_count,
           AVG(entry_price) as avg_entry, SUM(size_usd) as total_size
    FROM whale_positions
    WHERE detected_at > datetime('now', '-7 days')
    AND outcome = 'pending'
    GROUP BY condition_id, side
    HAVING whale_count >= 2
    ORDER BY whale_count DESC
""")

print("=== OPEN MARKETS WITH WHALE POSITIONS ===\n")
found_any = False
for row in cur.fetchall():
    cid, title, side, whales, avg_entry, total_size = row
    
    if cid in open_markets:
        found_any = True
        m = open_markets[cid]
        current = m['yes'] if side == 'YES' else m['no']
        
        # Calculate if there's still edge
        if side == 'YES':
            edge = (current - avg_entry) / avg_entry * 100 if avg_entry > 0 else 0
        else:
            edge = (avg_entry - current) / avg_entry * 100 if avg_entry > 0 else 0
        
        status = "MOVED AGAINST" if edge < -5 else "STILL GOOD" if edge > 5 else "FLAT"
        
        print(f"{title[:55]}")
        print(f"  {whales} whales on {side} | Entry: ${avg_entry:.2f} -> Now: ${current:.2f}")
        print(f"  Total size: ${total_size:,.0f} | Status: {status}")
        print(f"  Link: https://polymarket.com/event/{m['slug']}")
        print()

if not found_any:
    print("No open markets found with recent whale positions.")
    print("The whale-tracked sports markets may have already closed.")

# Step 3: Show top volume markets as alternatives
print("\n=== TOP 10 OPEN MARKETS BY VOLUME ===\n")
sorted_markets = sorted(open_markets.items(), key=lambda x: x[1]['volume'], reverse=True)[:10]
for cid, m in sorted_markets:
    print(f"{m['question'][:55]}")
    print(f"  YES: ${m['yes']:.2f} | Volume: ${m['volume']:,.0f}")
    print()

conn.close()
