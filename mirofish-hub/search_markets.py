import requests

# Direct Gamma API search
print("Searching Polymarket for active sports markets...\n")

# Get events
resp = requests.get(
    'https://gamma-api.polymarket.com/events?active=true&limit=50',
    timeout=30
)
events = resp.json()

print(f"Found {len(events)} active events\n")

for e in events[:15]:
    title = e.get('title', 'N/A')[:60]
    slug = e.get('slug', '')
    markets = e.get('markets', [])
    
    # Check if any market has orderbook
    tradeable = any(m.get('enableOrderBook') for m in markets)
    
    if tradeable:
        print(f"[TRADEABLE] {title}")
        for m in markets[:2]:
            if m.get('enableOrderBook'):
                tokens = m.get('clobTokenIds', [])
                q = m.get('question', '')[:40]
                print(f"  -> {q}")
                if tokens:
                    print(f"     YES: {tokens[0][:30]}...")
    else:
        print(f"[no book] {title}")
    print()
