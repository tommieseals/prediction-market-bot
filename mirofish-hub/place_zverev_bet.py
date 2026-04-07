#!/usr/bin/env python3
"""Place bet on Cerundolo vs Zverev - NO @ $0.45"""
import requests
import json

# Search for Miami Open tennis
print("Searching for Miami Open tennis markets...")
url = 'https://gamma-api.polymarket.com/markets'

# Try different search terms
searches = ['Zverev', 'Cerundolo', 'Miami Open Zverev']

for search in searches:
    params = {'search': search, 'limit': 20, 'active': 'true'}
    r = requests.get(url, params=params, timeout=10)
    markets = r.json()
    
    for m in markets:
        title = m.get('question', m.get('title', ''))
        if 'Cerundolo' in title and 'Zverev' in title:
            print(f"\n=== FOUND MATCH ===")
            print(f"Title: {title}")
            print(f"Condition ID: {m.get('conditionId')}")
            print(f"Slug: {m.get('slug')}")
            print(f"Active: {m.get('active')}")
            print(f"End Date: {m.get('endDate')}")
            
            # Get tokens/outcomes
            tokens = m.get('tokens', [])
            for t in tokens:
                print(f"  Token: {t.get('outcome')} - ID: {t.get('token_id')}")
            
            # Get current prices from CLOB
            cid = m.get('conditionId')
            if cid:
                try:
                    clob_url = f"https://clob.polymarket.com/markets/{cid}"
                    cr = requests.get(clob_url, timeout=10)
                    if cr.status_code == 200:
                        cdata = cr.json()
                        print(f"\nCLOB Data:")
                        print(json.dumps(cdata, indent=2)[:500])
                except Exception as e:
                    print(f"CLOB error: {e}")
            
            break
    else:
        continue
    break
else:
    print("Market not found in search. Trying data API...")
    
    # Try data API
    data_url = "https://data-api.polymarket.com/markets"
    params = {'limit': 100, 'active': 'true'}
    r = requests.get(data_url, params=params, timeout=15)
    if r.status_code == 200:
        markets = r.json()
        for m in markets:
            title = m.get('question', m.get('title', ''))
            if 'Cerundolo' in title or 'Zverev' in title:
                print(f"Found: {title}")
                print(f"CID: {m.get('conditionId')}")
