import requests

# Search events for sports today
print("=== SEARCHING EVENTS FOR SPORTS ===")
r = requests.get('https://gamma-api.polymarket.com/events?active=true&closed=false&limit=300', timeout=30)
events = r.json()

# Look for basketball/college sports
keywords = ['Nebraska', 'Iowa', 'Hawkeyes', 'Cornhuskers', 'NCAA', 'College', 'Basketball', 'NIT']

found = []
for event in events:
    title = event.get('title', '')
    desc = event.get('description', '')
    
    if any(kw.lower() in title.lower() or kw.lower() in desc.lower() for kw in keywords):
        found.append(event)
        print(f"\nEvent: {title}")
        print(f"End: {event.get('endDate', 'N/A')}")
        
        for m in event.get('markets', []):
            q = m.get('question', '')
            prices = m.get('outcomePrices', '')
            tokens = m.get('clobTokenIds', '')
            active = m.get('active')
            closed = m.get('closed')
            print(f"  Market: {q}")
            print(f"  Prices: {prices}")
            print(f"  Active: {active}, Closed: {closed}")
            print(f"  Tokens: {tokens}")

if not found:
    print("No Nebraska/Iowa events found. Checking all sports...")
    
    # Check for any sports events ending today
    for event in events:
        title = event.get('title', '')
        end = event.get('endDate', '')[:10] if event.get('endDate') else ''
        tags = event.get('tags', [])
        
        if end == '2026-03-26' or end == '2026-03-27':
            print(f"\nEvent ending soon: {title}")
            print(f"End: {end}")
            print(f"Tags: {tags}")
            for m in event.get('markets', [])[:2]:
                print(f"  Market: {m.get('question', '')[:60]}")
                print(f"  Prices: {m.get('outcomePrices')}")
