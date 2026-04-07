import requests

print("Searching for Thunder vs Celtics on Polymarket...")

# Search via event slug or direct API
# Try the events endpoint now that VPN is on
r = requests.get(
    "https://gamma-api.polymarket.com/events?closed=false&active=true&limit=500",
    timeout=60
)
events = r.json()

thunder_events = []
for e in events:
    title = str(e.get('title', '')).lower()
    desc = str(e.get('description', '')).lower()
    if 'thunder' in title or 'celtics' in title or 'okc' in title or 'boston' in title:
        thunder_events.append(e)

print(f"Found {len(thunder_events)} matching events")

for e in thunder_events[:5]:
    print(f"\nEvent: {e.get('title')}")
    for m in e.get('markets', [])[:3]:
        print(f"  Market: {m.get('question')}")
        print(f"  Tokens: {m.get('clobTokenIds')}")
        print(f"  Prices: {m.get('outcomePrices')}")

# Also try searching markets directly
print("\n" + "="*60)
print("Searching markets endpoint...")
r2 = requests.get(
    "https://gamma-api.polymarket.com/markets?closed=false&limit=1000",
    timeout=60
)
markets = r2.json()

for m in markets:
    q = str(m.get('question', '')).lower()
    if ('thunder' in q and 'celtic' in q) or ('okc' in q and 'boston' in q):
        print(f"\nFound: {m.get('question')}")
        print(f"  Condition: {m.get('conditionId')}")
        print(f"  Tokens: {m.get('clobTokenIds')}")
        print(f"  Prices: {m.get('outcomePrices')}")
        print(f"  End: {m.get('endDateIso')}")

# Try polymarket.com API for sports
print("\n" + "="*60)
print("Trying CLOB markets endpoint...")
r3 = requests.get(
    "https://clob.polymarket.com/markets",
    timeout=30
)
clob_data = r3.json()
if isinstance(clob_data, dict):
    clob_markets = clob_data.get('data', clob_data.get('markets', []))
else:
    clob_markets = clob_data if isinstance(clob_data, list) else []

print(f"CLOB returned {len(clob_markets) if clob_markets else 0} markets")
