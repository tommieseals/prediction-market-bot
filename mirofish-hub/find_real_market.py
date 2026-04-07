import requests

print("Searching for Thunder vs Celtics on Polymarket...")

# Try markets endpoint with text search
try:
    # Get all open markets
    r = requests.get('https://gamma-api.polymarket.com/markets?closed=false&limit=1000', timeout=60)
    markets = r.json()
    print(f"Total open markets: {len(markets)}")
    
    # Search for NBA game
    for m in markets:
        q = m.get('question', '').lower()
        if ('thunder' in q or 'okc' in q) and ('celtic' in q or 'boston' in q):
            print(f"\n=== FOUND ===")
            print(f"Question: {m.get('question')}")
            print(f"Condition: {m.get('conditionId')}")
            print(f"Tokens: {m.get('clobTokenIds')}")
            print(f"Outcomes: {m.get('outcomes')}")
            print(f"Prices: {m.get('outcomePrices')}")
            print(f"End Date: {m.get('endDateIso')}")
            print(f"Active: {m.get('active')}")
    
    # Also search events
    print("\n\nSearching events...")
    r2 = requests.get('https://gamma-api.polymarket.com/events?closed=false&limit=500', timeout=60)
    events = r2.json()
    
    for e in events:
        title = e.get('title', '').lower()
        desc = e.get('description', '').lower()
        if 'thunder' in title or 'thunder' in desc or 'celtics' in title or 'celtics' in desc:
            print(f"\nEvent: {e.get('title')}")
            print(f"ID: {e.get('id')}")
            markets_in_event = e.get('markets', [])
            for em in markets_in_event[:5]:
                print(f"  - {em.get('question')}")
                print(f"    Tokens: {em.get('clobTokenIds')}")
                print(f"    Prices: {em.get('outcomePrices')}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
