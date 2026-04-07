import requests

# Search for Nebraska vs Iowa moneyline
r = requests.get('https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=200', timeout=30)
markets = r.json()

print("=== NEBRASKA vs IOWA MARKETS ===")
for m in markets:
    title = m.get('question', m.get('title', ''))
    if 'Nebraska' in title and 'Iowa' in title:
        print(f"Title: {title}")
        print(f"Condition ID: {m.get('conditionId')}")
        print(f"Outcomes: {m.get('outcomes')}")
        print(f"Prices: {m.get('outcomePrices')}")
        print(f"Tokens: {m.get('clobTokenIds')}")
        print()
