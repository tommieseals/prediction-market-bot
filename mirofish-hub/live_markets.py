#!/usr/bin/env python3
"""Get LIVE markets from Polymarket"""
import requests
import json
from datetime import datetime

# Gamma API for markets
url = 'https://gamma-api.polymarket.com/markets'
params = {
    'closed': 'false',
    'active': 'true', 
    'limit': 100
}

response = requests.get(url, params=params, timeout=30)
markets = response.json()

now = datetime.now().strftime("%H:%M")
print('='*70)
print(f'[RED] LIVE POLYMARKET MARKETS (Fetched: {now} CDT)')
print('='*70)

# Filter for tradeable markets
count = 0
for m in markets:
    q = m.get('question', '')
    
    # Skip long-term
    skip_words = ['finals', 'championship', 'president', 'gta vi', '2027', '2028', 'world cup', 'before june', 'before july']
    if any(x in q.lower() for x in skip_words):
        continue
    
    # Get prices from outcomePrices
    prices_str = m.get('outcomePrices', '[]')
    try:
        prices = json.loads(prices_str)
        if len(prices) >= 2:
            yes_price = float(prices[0])
            no_price = float(prices[1])
        else:
            continue
    except (ValueError, TypeError, json.JSONDecodeError):  # H12 FIX: Specific JSON errors
        continue
    
    # Market must be liquid
    liquidity = float(m.get('liquidity', 0) or 0)
    volume = float(m.get('volume', 0) or 0)
    
    if liquidity < 1000:
        continue
    
    # Get end date
    end_date = m.get('endDate', '')[:10] if m.get('endDate') else 'Unknown'
    
    # Flag underdogs
    flag = ''
    if yes_price <= 0.30:
        flag = ' [HOT] UNDERDOG'
    elif yes_price >= 0.70:
        flag = ' [UP] FAVORITE'
    
    print(f"\n[STATS] {q[:62]}")
    print(f"   YES: ${yes_price:.2f} | NO: ${no_price:.2f} | Liq: ${liquidity:,.0f} | Ends: {end_date}{flag}")
    
    count += 1
    if count >= 25:
        break

print(f"\n{'='*70}")
print(f"Showing {count} LIVE markets (liquidity > $1,000)")
print(f"[MONEY] Your capital: $77.36 USDC")
print('='*70)
