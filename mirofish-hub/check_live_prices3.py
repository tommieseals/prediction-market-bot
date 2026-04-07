import requests
import json

print("=== VERIFYING TODAY'S PICKS WITH LIVE DATA ===\n")

# Markets we care about from our consensus picks
markets_to_check = [
    "Raptors",
    "Pistons", 
    "Maple Leafs",
    "Ducks",
    "Pirates",
    "Reds"
]

url = 'https://gamma-api.polymarket.com/markets?_limit=100&active=true&closed=false'
try:
    r = requests.get(url, timeout=15)
    data = r.json()
    
    found = []
    for m in data:
        q = m.get('question', '').lower()
        for term in markets_to_check:
            if term.lower() in q:
                question = m.get('question')
                prices_raw = m.get('outcomePrices', '[]')
                outcomes_raw = m.get('outcomes', '[]')
                
                # Parse JSON strings
                if isinstance(prices_raw, str):
                    prices = json.loads(prices_raw)
                else:
                    prices = prices_raw
                    
                if isinstance(outcomes_raw, str):
                    outcomes = json.loads(outcomes_raw)
                else:
                    outcomes = outcomes_raw
                
                print(f"FOUND: {question}")
                for i, o in enumerate(outcomes):
                    if i < len(prices):
                        p = float(prices[i])
                        print(f"  {o}: ${p:.2f} ({p*100:.0f}%)")
                print()
                found.append(question)
                break
    
    if not found:
        print("No matching markets found in top 100 active markets.")
        print("These games may have already started or not be on Polymarket.")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
