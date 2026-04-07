import requests
import json
from datetime import datetime

print(f"=== SCANNING FOR OPEN SPORTS BETS ===")
print(f"Time: {datetime.now()}\n")

# Try different endpoints
endpoints = [
    'https://gamma-api.polymarket.com/markets?_limit=200&active=true&closed=false',
    'https://gamma-api.polymarket.com/events?_limit=50&active=true&closed=false',
]

all_markets = []

for url in endpoints:
    try:
        r = requests.get(url, timeout=15)
        data = r.json()
        if isinstance(data, list):
            all_markets.extend(data)
    except:
        pass

print(f"Total items fetched: {len(all_markets)}\n")

# Look for sports/games
sports = []
for item in all_markets:
    q = item.get('question', '') or item.get('title', '')
    q_lower = q.lower()
    
    # Sports indicators
    if any(x in q_lower for x in ['nba', 'nfl', 'mlb', 'nhl', 'vs.', 'spread', 'winner', 
                                   'lakers', 'celtics', 'yankees', 'dodgers', 'chiefs',
                                   'tennis', 'golf', 'ufc', 'boxing', 'f1', 'formula']):
        prices_raw = item.get('outcomePrices', '[]')
        if isinstance(prices_raw, str):
            prices = json.loads(prices_raw) if prices_raw else []
        else:
            prices = prices_raw or []
            
        if prices and len(prices) > 0 and float(prices[0]) > 0:
            sports.append({
                'question': q,
                'prices': prices,
                'outcomes': json.loads(item.get('outcomes', '[]')) if isinstance(item.get('outcomes'), str) else item.get('outcomes', []),
                'volume': item.get('volumeNum', 0),
                'conditionId': item.get('conditionId', '')
            })

if sports:
    print(f"Found {len(sports)} open sports markets:\n")
    for s in sorted(sports, key=lambda x: x['volume'], reverse=True)[:10]:
        print(f"{s['question']}")
        print(f"  Volume: ${s['volume']:,.0f}")
        for i, o in enumerate(s['outcomes']):
            if i < len(s['prices']):
                print(f"  {o}: ${float(s['prices'][i]):.2f}")
        print()
else:
    print("No open sports markets found right now.")
    print("\nThis could mean:")
    print("  - Games are between sessions (no active betting)")
    print("  - Sports markets closed for the day")
    print("  - Need to wait for new markets to open")
