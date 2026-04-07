#!/usr/bin/env python3
"""Find Polymarket proxy wallet and check actual balances"""

import os
from dotenv import load_dotenv
load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

pk = os.getenv('POLY_PRIVATE_KEY')

client = ClobClient(
    host='https://clob.polymarket.com', 
    chain_id=POLYGON, 
    key=pk,
    signature_type=2,
)

print("Setting up client...")
creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)

print(f"\nMain wallet: {client.get_address()}")

# Check if there's a proxy address
print("\nLooking for proxy wallet methods...")
for attr in dir(client):
    if 'proxy' in attr.lower() or 'funder' in attr.lower():
        print(f"  Found: {attr}")
        val = getattr(client, attr, None)
        if val and not callable(val):
            print(f"    Value: {val}")

# Try to get the funder address
print(f"\nFunder address: {client.funder if hasattr(client, 'funder') else 'Not set'}")

# Check proxy address attribute
if hasattr(client, 'proxy_address'):
    print(f"Proxy address: {client.proxy_address}")

# Check all attributes
print("\nAll client attributes with values:")
for attr in ['chain_id', 'host', 'signer', 'funder', 'sig_type', 'creds']:
    try:
        val = getattr(client, attr, None)
        if val:
            print(f"  {attr}: {val}")
    except Exception:
        pass

# Get balance allowance properly
print("\n=== Checking COLLATERAL balance ===")
params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=2)
try:
    result = client.get_balance_allowance(params)
    print(f"Result: {result}")
except Exception as e:
    print(f"Error: {e}")
