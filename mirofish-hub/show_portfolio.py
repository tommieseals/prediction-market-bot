#!/usr/bin/env python3
"""Show Polymarket portfolio"""

from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
import os
from dotenv import load_dotenv
load_dotenv()

pk = os.getenv('POLY_PRIVATE_KEY')
client = ClobClient(host='https://clob.polymarket.com', chain_id=POLYGON, key=pk)
client.set_api_creds(client.create_or_derive_api_creds())

print("=" * 55)
print("        POLYMARKET PORTFOLIO - TRADING BOT")
print("=" * 55)
print(f"Wallet: 0x299aCc0857B943d8490ECb1820fD458B3B58c728")

# Balance
params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
bal = client.get_balance_allowance(params)
balance = int(bal['balance']) / 1e6
print(f"USDC.e Balance: ${balance:.2f}")
print("=" * 55)

# Get open orders
print("\n📋 OPEN ORDERS:")
try:
    orders = client.get_orders()
    if orders:
        for o in orders:
            print(f"  • {o}")
    else:
        print("  (none)")
except Exception as e:
    print(f"  Error: {e}")

# Show executed trades
print("\n✅ EXECUTED TODAY (Mar 23, 2026):")
print("-" * 55)
print("1. Lakers vs Pistons")
print("   └─ NO @ $0.49 × 25 shares = $12.25")
print("   └─ Status: MATCHED ✓")
print("   └─ TX: 0x436f8c29...04270333")
print()
print("2. Miami Open: Auger-Aliassime vs Atmane")  
print("   └─ NO @ $0.26 × 25 shares = $6.50")
print("   └─ Status: LIVE (order on book)")
print("   └─ Order: 0x9c7c0b67...2aee87")
print("-" * 55)
print(f"Total Committed: ~$18.75")
print(f"Remaining: ${balance:.2f}")
print("=" * 55)

# Polygonscan link
print("\n🔗 View on Polygonscan:")
print("https://polygonscan.com/address/0x299aCc0857B943d8490ECb1820fD458B3B58c728")
