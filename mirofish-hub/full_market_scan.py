"""
Full market scan - find ALL open markets with whale activity or edge
"""
import requests
import json
import sqlite3
from datetime import datetime

print(f"=== FULL MARKET SCAN ===")
print(f"Time: {datetime.now()}\n")

# Get ALL active markets
url = 'https://gamma-api.polymarket.com/markets?_limit=500&active=true&closed=false'
try:
    r = requests.get(url, timeout=30)
    markets = r.json()
    print(f"Fetched {len(markets)} active markets\n")
except Exception as e:
    print(f"Error fetching markets: {e}")
    markets = []

# Also get events for more coverage
try:
    r2 = requests.get('https://gamma-api.polymarket.com/events?_limit=100&active=true&closed=false', timeout=30)
    events = r2.json()
    print(f"Fetched {len(events)} active events\n")
except:
    events = []

# Connect to our whale DB to check for whale positions
conn = sqlite3.connect(r'C:\Users\USER\clawd\mirofish-hub\data\whale_hunter.db')
cur = conn.cursor()

# Get all condition IDs with whale activity
cur.execute("""
    SELECT DISTINCT condition_id, market_title, side, COUNT(*) as whale_count,
           AVG(entry_price) as avg_price
    FROM whale_positions
    WHERE detected_at > datetime('now', '-7 days')
    GROUP BY condition_id, side
    HAVING whale_count >= 2
""")
whale_markets = {row[0]: {'title': row[1], 'side': row[2], 'whales': row[3], 'price': row[4]} 
                 for row in cur.fetchall()}

print(f"Found {len(whale_markets)} markets with 2+ whale activity in last 7 days\n")

# Check which whale markets are still OPEN
open_with_whales = []
for cond_id, info in whale_markets.items():
    # Look up market status
    try:
        r = requests.get(f'https://gamma-api.polymarket.com/markets?conditionId={cond_id}', timeout=10)
        data = r.json()
        if data and not data[0].get('closed', True):
            prices_raw = data[0].get('outcomePrices', '[]')
            if isinstance(prices_raw, str):
                prices = json.loads(prices_raw)
            else:
                prices = prices_raw
            
            if prices and float(prices[0]) > 0:
                yes_price = float(prices[0])
                no_price = float(prices[1]) if len(prices) > 1 else 1 - yes_price
                
                # Calculate edge based on whale position
                if info['side'] == 'YES':
                    current = yes_price
                else:
                    current = no_price
                    
                open_with_whales.append({
                    'title': info['title'],
                    'side': info['side'],
                    'whales': info['whales'],
                    'whale_entry': info['price'],
                    'current_price': current,
                    'yes_price': yes_price,
                    'condition_id': cond_id
                })
    except:
        continue

print(f"=== OPEN MARKETS WITH WHALE ACTIVITY ===\n")
if open_with_whales:
    # Sort by whale count
    for m in sorted(open_with_whales, key=lambda x: x['whales'], reverse=True)[:15]:
        print(f"{m['title'][:60]}")
        print(f"  {m['whales']} whales on {m['side']} @ {m['whale_entry']:.2f}")
        print(f"  Current YES: ${m['yes_price']:.2f}")
        print()
else:
    print("No open markets with recent whale activity found.")

# Also show top volume markets for context
print(f"\n=== TOP VOLUME OPEN MARKETS ===\n")
sorted_by_vol = sorted(markets, key=lambda x: x.get('volumeNum', 0), reverse=True)[:10]
for m in sorted_by_vol:
    q = m.get('question', 'N/A')
    vol = m.get('volumeNum', 0)
    prices_raw = m.get('outcomePrices', '[]')
    if isinstance(prices_raw, str):
        prices = json.loads(prices_raw)
    else:
        prices = prices_raw
    
    yes_price = float(prices[0]) if prices else 0
    print(f"{q[:60]}")
    print(f"  Volume: ${vol:,.0f} | YES: ${yes_price:.2f}")
    print()

conn.close()
