import requests

print("=== CHECKING LIVE POLYMARKET PRICES ===\n")

# Search for today's NBA games
searches = ["Raptors", "Maple Leafs", "Pirates"]

for search in searches:
    url = f'https://gamma-api.polymarket.com/markets?_limit=3&active=true&closed=false&title_contains={search}'
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        for m in data:
            question = m.get("question", "N/A")
            outcomes = m.get('outcomes', [])
            prices = m.get('outcomePrices', [])
            
            print(f"Market: {question}")
            for i, o in enumerate(outcomes):
                if i < len(prices):
                    print(f"  {o}: ${float(prices[i]):.2f}")
            print()
    except Exception as e:
        print(f"Error searching {search}: {e}\n")
