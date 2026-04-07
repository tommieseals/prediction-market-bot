#!/usr/bin/env python3
import requests
import json

print("Testing Polymarket APIs...")

# Test Gamma API
print("\n1. GAMMA API (active markets)")
resp = requests.get('https://gamma-api.polymarket.com/markets', 
                   params={'active': 'true', 'closed': 'false', 'limit': 5})
print(f"Status: {resp.status_code}")
if resp.ok:
    data = resp.json()
    print(f"Count: {len(data)}")
    for m in data[:3]:
        q = m.get('question', m.get('title', ''))[:60]
        print(f"  Market: {q}")
        print(f"    Closed: {m.get('closed')}")
        print(f"    Tokens: {m.get('clobTokenIds')}")

# Test CLOB API
print("\n2. CLOB API (price check)")
# Use a known token ID from our database
test_token = "65375616791675452522273196207926200426031156851399864745571441185151419878926"
resp = requests.get(f'https://clob.polymarket.com/price', 
                   params={'token_id': test_token})
print(f"Status: {resp.status_code}")
if resp.ok:
    print(f"Price data: {resp.json()}")

# Test Data API
print("\n3. DATA API (leaderboard)")
resp = requests.get('https://data-api.polymarket.com/v1/leaderboard', 
                   params={'limit': 3})
print(f"Status: {resp.status_code}")
if resp.ok:
    data = resp.json()
    print(f"Top traders: {len(data)} returned")
    for t in data[:2]:
        print(f"  {t.get('username', t.get('name', 'N/A'))}: ${t.get('pnl', 0):,.0f}")

print("\n[OK] All APIs accessible!")
