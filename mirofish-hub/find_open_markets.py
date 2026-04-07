import requests
import json
from datetime import datetime

print(f"=== FINDING ACTUALLY OPEN MARKETS ===")
print(f"Current time: {datetime.now()}\n")

# Get active sports markets
url = 'https://gamma-api.polymarket.com/markets?_limit=50&active=true&closed=false'
try:
    r = requests.get(url, timeout=15)
    data = r.json()
    
    sports_keywords = ['vs', 'game', 'match', 'winner', 'spread', 'o/u', 'over/under']
    
    print(f"Found {len(data)} active markets. Filtering for sports...\n")
    
    count = 0
    for m in data:
        question = m.get('question', '')
        
        # Look for sports-like markets
        is_sports = any(kw in question.lower() for kw in sports_keywords)
        
        if is_sports or 'vs' in question:
            prices_raw = m.get('outcomePrices', '[]')
            outcomes_raw = m.get('outcomes', '[]')
            volume = m.get('volumeNum', 0)
            
            if isinstance(prices_raw, str):
                prices = json.loads(prices_raw)
            else:
                prices = prices_raw
            if isinstance(outcomes_raw, str):
                outcomes = json.loads(outcomes_raw)
            else:
                outcomes = outcomes_raw
            
            # Only show if has real prices
            if prices and float(prices[0]) > 0:
                print(f"OPEN: {question}")
                print(f"  Volume: ${volume:,.0f}")
                for i, o in enumerate(outcomes):
                    if i < len(prices):
                        p = float(prices[i])
                        print(f"  {o}: ${p:.2f}")
                print()
                count += 1
                
                if count >= 10:
                    break
    
    if count == 0:
        print("No sports markets currently open with active prices.")
        print("\nTop active markets by volume:")
        sorted_markets = sorted(data, key=lambda x: x.get('volumeNum', 0), reverse=True)[:5]
        for m in sorted_markets:
            print(f"  - {m.get('question', 'N/A')[:60]} (${m.get('volumeNum', 0):,.0f})")
                
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
