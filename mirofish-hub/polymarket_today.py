import requests
from datetime import datetime

print("=== POLYMARKET - RESOLVES TODAY (March 25) ===\n")

# Get all active markets
r = requests.get('https://gamma-api.polymarket.com/markets?closed=false&active=true&limit=500', timeout=30)
markets = r.json()

today = []
for m in markets:
    end = m.get('endDate', '')
    liq = float(m.get('liquidity', 0) or 0)
    q = m.get('question', '')
    prices = m.get('outcomePrices', [])
    
    # Check if ends today or very soon
    if '2026-03-25' in end or 'march 25' in q.lower() or '3/25' in q.lower():
        if liq > 500:  # Some liquidity
            today.append({
                'question': q,
                'liquidity': liq,
                'prices': prices,
                'end': end,
                'cid': m.get('conditionId')
            })

# Sort by liquidity
today.sort(key=lambda x: x['liquidity'], reverse=True)

print(f"Found {len(today)} markets ending today with liquidity\n")

for t in today[:15]:
    print(f"{t['question'][:60]}")
    print(f"  Liquidity: ${t['liquidity']:,.0f}")
    if t['prices']:
        try:
            yes_price = float(t['prices'][0]) if t['prices'] else 0
            print(f"  YES: ${yes_price:.2f} | NO: ${1-yes_price:.2f}")
        except (ValueError, TypeError, IndexError):  # H12 FIX: Price parsing errors
            pass
    print()

if not today:
    print("No liquid markets found ending today on Polymarket.")
    print("\nChecking NBA games tonight...")
    
    # Look for NBA
    nba_markets = []
    for m in markets:
        q = m.get('question', '')
        liq = float(m.get('liquidity', 0) or 0)
        if any(team in q for team in ['Celtics', 'Thunder', 'Lakers', 'Warriors', 'Heat', 'Cavaliers', 'Bucks', 'Nuggets']):
            if liq > 1000:
                nba_markets.append({
                    'question': q,
                    'liquidity': liq,
                    'prices': m.get('outcomePrices')
                })
    
    if nba_markets:
        print(f"\nNBA markets found: {len(nba_markets)}")
        for n in nba_markets[:5]:
            print(f"  {n['question'][:55]} | ${n['liquidity']:,.0f}")
