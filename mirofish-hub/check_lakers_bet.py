#!/usr/bin/env python3
from polymarket_api import PolymarketAPI
import json

WALLET = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'

api = PolymarketAPI()

# Get our position
print("=== OUR CURRENT POSITION ===")
positions = api.get_positions(WALLET)
for p in positions:
    print(f"Market: {p.get('title')}")
    print(f"Our bet: {p.get('outcome')}")
    print(f"Size: {p.get('size')} shares")
    print(f"Entry price: ${p.get('avgPrice')}")
    print(f"Current price: ${p.get('curPrice')}")
    print(f"Cash PnL: ${p.get('cashPnl')}")
    print(f"Redeemable: {p.get('redeemable')}")
    print(f"End date: {p.get('endDate')}")
    print()

# Check if market is resolved
print("=== CHECKING MARKET STATUS ===")
condition_id = None
for p in positions:
    condition_id = p.get('conditionId')
    
if condition_id:
    # Try to get market info
    try:
        market = api.get_market(condition_id)
        if market:
            print(f"Market resolved: {market.get('resolved', 'Unknown')}")
            print(f"Winning outcome: {market.get('winner', market.get('outcome', 'Unknown'))}")
    except Exception as e:
        print(f"Could not get market status: {e}")

# Check closed/resolved positions
print("\n=== CLOSED POSITIONS (last 10) ===")
try:
    closed = api.get_closed_positions(WALLET, limit=10)
    print(f"Found {len(closed)} closed positions")
    for c in closed:
        title = c.get('title', c.get('marketSlug', 'Unknown'))
        if 'lakers' in title.lower() or 'pistons' in title.lower():
            print(f"*** FOUND: {title}")
            print(f"    Outcome: {c.get('outcome')}")
            print(f"    PnL: {c.get('pnl', c.get('realizedPnl', 'N/A'))}")
except Exception as e:
    print(f"Error checking closed positions: {e}")

api.close()
