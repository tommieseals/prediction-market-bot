import requests
import sys

condition_id = sys.argv[1] if len(sys.argv) > 1 else '0xe96bab86f43e9ae8647eedb5ed680747a8875571c027d11f1f2bae39867d4209'

r = requests.get(f'https://gamma-api.polymarket.com/markets?conditionId={condition_id}', timeout=30)
markets = r.json()

if not markets:
    # Try searching by slug or broader search
    r = requests.get('https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=300', timeout=30)
    markets = r.json()
    markets = [m for m in markets if 'Nebraska' in str(m.get('question', '')) or 'Cornhuskers' in str(m.get('question', ''))]

for m in markets:
    print(f"Question: {m.get('question')}")
    print(f"Outcomes: {m.get('outcomes')}")
    print(f"Prices: {m.get('outcomePrices')}")
    print(f"Tokens: {m.get('clobTokenIds')}")
    print(f"Active: {m.get('active')}")
    print(f"Closed: {m.get('closed')}")
    print(f"End Date: {m.get('endDate')}")
    print()
