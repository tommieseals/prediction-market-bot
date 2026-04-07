import requests

# Try CLOB API directly
print("Searching CLOB for active markets...\n")

# Get from clob-api
resp = requests.get(
    'https://clob.polymarket.com/markets?limit=20',
    timeout=30
)

if resp.status_code == 200:
    data = resp.json()
    if isinstance(data, list):
        markets = data
    else:
        markets = data.get('markets', data.get('data', []))
    
    print(f"Found {len(markets)} markets\n")
    
    for m in markets[:15]:
        if isinstance(m, dict):
            q = m.get('question', m.get('title', str(m)[:60]))[:60]
            token = m.get('condition_id', m.get('token_id', 'N/A'))
            active = m.get('active', m.get('enable_order_book', 'N/A'))
            print(f"{q}")
            print(f"  Active: {active}")
            print(f"  Token: {str(token)[:40]}...")
            print()
else:
    print(f"Error: {resp.status_code}")
    print(resp.text[:500])
