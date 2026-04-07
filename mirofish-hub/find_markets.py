import requests

# CLOB API - paginate
print('=== SEARCHING CLOB API FOR NBA ===')
all_markets = []
next_cursor = None

for _ in range(10):  # 10 pages
    url = 'https://clob.polymarket.com/markets?limit=500'
    if next_cursor:
        url += f'&next_cursor={next_cursor}'
    
    resp = requests.get(url, timeout=30)
    data = resp.json()
    
    markets = data.get('data', [])
    all_markets.extend(markets)
    next_cursor = data.get('next_cursor')
    
    if not next_cursor:
        break

print(f"Total markets: {len(all_markets)}")

# Find NBA
nba_keywords = ['nba', 'thunder', 'celtics', 'cavaliers', 'heat', 'lakers', 'warriors', 'bulls', 'knicks', 'bucks']
nba_markets = []

for m in all_markets:
    q = (m.get('question', '') or '').lower()
    if any(kw in q for kw in nba_keywords):
        if not m.get('closed'):
            nba_markets.append(m)

print(f"Open NBA-related markets: {len(nba_markets)}")

# Print them
for m in nba_markets[:30]:
    print(f"\n{m.get('question')[:80]}")
    print(f"  Active: {m.get('active')}, Accepting: {m.get('accepting_orders')}")
    tokens = m.get('tokens', [])
    for t in tokens[:2]:
        print(f"  {t.get('outcome')}: @ {t.get('price')}")
