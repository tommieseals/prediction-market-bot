"""
Check longer-term markets for whale activity and edge
"""
import requests
import json
import sqlite3
from datetime import datetime

print(f"=== LONGER-TERM OPPORTUNITY SCAN ===")
print(f"Time: {datetime.now()}\n")

# Markets we found open
targets = [
    ('Italy qualify for 2026 World Cup', 'italy'),
    ('Sweden qualify for 2026 World Cup', 'sweden'),
    ('Poland qualify for 2026 World Cup', 'poland'),
    ('Carolina Hurricanes Stanley Cup', 'hurricanes'),
]

# Get all markets
url = 'https://gamma-api.polymarket.com/markets?_limit=500&active=true&closed=false'
r = requests.get(url, timeout=30)
markets = r.json()

# Find our targets
found = []
for m in markets:
    q = m.get('question', '').lower()
    for name, keyword in targets:
        if keyword in q:
            prices_raw = m.get('outcomePrices', '[]')
            if isinstance(prices_raw, str):
                prices = json.loads(prices_raw)
            else:
                prices = prices_raw
            
            found.append({
                'name': name,
                'question': m.get('question'),
                'yes': float(prices[0]) if prices else 0,
                'no': float(prices[1]) if len(prices) > 1 else 0,
                'volume': m.get('volumeNum', 0),
                'condition_id': m.get('conditionId'),
                'slug': m.get('slug', '')
            })
            break

print("=== OPEN LONGER-TERM BETS ===\n")
for f in found:
    print(f"{f['name']}")
    print(f"  YES: ${f['yes']:.2f} ({f['yes']*100:.0f}%)")
    print(f"  NO: ${f['no']:.2f} ({f['no']*100:.0f}%)")
    print(f"  Volume: ${f['volume']:,.0f}")
    print(f"  https://polymarket.com/event/{f['slug']}")
    print()

# Check wallet balance
print("=== CHECKING WALLET BALANCE ===\n")
try:
    from web3 import Web3
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    
    # Polygon RPC
    w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))
    
    wallet = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'
    
    # USDC on Polygon
    usdc_address = '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359'
    usdc_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
    
    usdc = w3.eth.contract(address=Web3.to_checksum_address(usdc_address), abi=usdc_abi)
    balance = usdc.functions.balanceOf(Web3.to_checksum_address(wallet)).call()
    usdc_balance = balance / 10**6
    
    matic_balance = w3.eth.get_balance(Web3.to_checksum_address(wallet)) / 10**18
    
    print(f"Wallet: {wallet}")
    print(f"USDC: ${usdc_balance:.2f}")
    print(f"MATIC: {matic_balance:.4f}")
    
except Exception as e:
    print(f"Could not check wallet: {e}")

print("\n=== RECOMMENDATION ===\n")
print("World Cup qualifiers end in late 2025 - these are LONG bets.")
print("Stanley Cup playoffs start April 2026 - medium term.")
print()
print("For DAILY action, we need to catch sports markets when they open")
print("(usually a few hours before game time).")
