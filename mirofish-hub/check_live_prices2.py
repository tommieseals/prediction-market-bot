import requests
import json

print("=== CHECKING LIVE POLYMARKET PRICES ===\n")

# Try direct search
url = 'https://gamma-api.polymarket.com/markets?_limit=5&active=true&closed=false'

try:
    r = requests.get(url, timeout=10)
    data = r.json()
    print(f"Got {len(data)} markets\n")
    
    # Print first market structure to understand format
    if data:
        m = data[0]
        print("Sample market structure:")
        print(f"  question: {m.get('question')}")
        print(f"  outcomes: {m.get('outcomes')}")
        print(f"  outcomePrices: {m.get('outcomePrices')}")
        print(f"  type of outcomePrices: {type(m.get('outcomePrices'))}")
        print()
        
except Exception as e:
    print(f"Error: {e}")

# Search specifically for basketball
print("\nSearching for NBA games...")
url2 = 'https://gamma-api.polymarket.com/markets?_limit=10&active=true&closed=false&tag=Sports'
try:
    r = requests.get(url2, timeout=10)
    data = r.json()
    for m in data:
        q = m.get('question', '')
        if 'vs' in q.lower() and ('raptors' in q.lower() or 'lakers' in q.lower() or 'pistons' in q.lower()):
            print(f"\n{q}")
            prices = m.get('outcomePrices')
            outcomes = m.get('outcomes')
            if prices and outcomes:
                # Handle if prices is a string representation of list
                if isinstance(prices, str):
                    prices = json.loads(prices)
                if isinstance(outcomes, str):
                    outcomes = json.loads(outcomes)
                for i, o in enumerate(outcomes):
                    if i < len(prices):
                        print(f"  {o}: ${float(prices[i]):.2f}")
except Exception as e:
    print(f"Error: {e}")
