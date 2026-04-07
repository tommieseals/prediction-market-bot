import requests
import json

# Try events endpoint
print("Searching events...")
r = requests.get('https://gamma-api.polymarket.com/events?closed=false&active=true&limit=200', timeout=60)
events = r.json()
print(f'Total events: {len(events)}')

# Look for NBA daily games
for e in events:
    title = e.get('title', '').lower()
    if 'thunder' in title or 'celtics' in title or 'okc' in title or 'boston' in title:
        print(f"\nEvent: {e.get('title')}")
        for m in e.get('markets', []):
            q = m.get('question', '')
            print(f"  Market: {q}")
            print(f"  Tokens: {m.get('clobTokenIds')}")
            print(f"  Outcomes: {m.get('outcomes')}")
            print(f"  Prices: {m.get('outcomePrices')}")

# Also try CLOB API for daily sports
print("\n\nSearching CLOB for daily games...")
try:
    # This might have the daily sports markets
    r2 = requests.get('https://clob.polymarket.com/markets?next_cursor=LTE=', timeout=30)
    clob_markets = r2.json()
    print(f"CLOB response type: {type(clob_markets)}")
    if isinstance(clob_markets, dict) and 'data' in clob_markets:
        for m in clob_markets['data'][:20]:
            q = m.get('question', '')
            if 'thunder' in q.lower() or 'celtics' in q.lower():
                print(f"\nFound: {q}")
                print(f"  Token: {m.get('tokens')}")
except Exception as e:
    print(f"CLOB error: {e}")
