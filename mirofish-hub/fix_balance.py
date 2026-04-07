#!/usr/bin/env python3
"""Update Polymarket balance view"""

import os
from dotenv import load_dotenv
load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

pk = os.getenv('POLY_PRIVATE_KEY')

client = ClobClient(host='https://clob.polymarket.com', chain_id=POLYGON, key=pk)
creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)

print("Current COLLATERAL balance:")
params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
bal = client.get_balance_allowance(params)
print(f"  Balance: {bal['balance']}")

print("\nUpdating balance view...")
try:
    result = client.update_balance_allowance(params)
    print(f"  Update result: {result}")
except Exception as e:
    print(f"  Error: {e}")

print("\nNew balance:")
bal2 = client.get_balance_allowance(params)
print(f"  Balance: {bal2['balance']}")
print(f"  Allowances: {bal2['allowances']}")

# Check which USDC Polymarket expects
print("\n=== Checking Polymarket USDC requirements ===")
import requests
try:
    # Check if there's token info in their API
    r = requests.get('https://clob.polymarket.com/', timeout=10)
    print(f"CLOB root response: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")
