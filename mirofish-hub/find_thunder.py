import requests
import json

print("Searching Polymarket for Thunder vs Celtics...")
try:
    # Search events first
    resp = requests.get(
        "https://gamma-api.polymarket.com/events?closed=false&limit=100",
        timeout=30
    )
    events = resp.json()
    
    for e in events:
        title = e.get('title', '').lower()
        if 'thunder' in title or 'okc' in title:
            print(f"\nEvent: {e.get('title')}")
            for m in e.get('markets', []):
                q = m.get('question', '')
                if 'celtic' in q.lower() or 'thunder' in q.lower():
                    print(f"  Market: {q}")
                    print(f"  Condition: {m.get('conditionId')}")
                    print(f"  Tokens: {m.get('clobTokenIds')}")
                    print(f"  Outcomes: {m.get('outcomes')}")
                    print(f"  Prices: {m.get('outcomePrices')}")
    
    # Also try direct market search
    resp2 = requests.get(
        "https://gamma-api.polymarket.com/markets?closed=false&limit=300",
        timeout=30
    )
    markets = resp2.json()
    
    for m in markets:
        q = m.get('question', '').lower()
        if ('thunder' in q and 'celtic' in q) or ('okc' in q and 'boston' in q):
            if 'spread' not in q and 'o/u' not in q:
                print(f"\nDirect Match: {m.get('question')}")
                print(f"  Condition: {m.get('conditionId')}")
                print(f"  Tokens: {m.get('clobTokenIds')}")
                print(f"  Outcomes: {m.get('outcomes')}")
                print(f"  Prices: {m.get('outcomePrices')}")
                
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
