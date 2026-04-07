#!/usr/bin/env python3
"""Fix USDC allowance for Polymarket trading"""

import os
from dotenv import load_dotenv
load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

pk = os.getenv('POLY_PRIVATE_KEY')
print(f"Using wallet with key: {pk[:8]}...")

client = ClobClient(
    host='https://clob.polymarket.com', 
    chain_id=POLYGON, 
    key=pk,
    signature_type=2,  # EIP712
)

print("Setting API credentials...")
creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)
print(f"API Key: {creds.api_key[:16]}...")

# Check COLLATERAL (USDC) balance and allowance
print("\n=== COLLATERAL (USDC) ===")
params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=2)
try:
    bal = client.get_balance_allowance(params)
    print(f"Balance/Allowance: {bal}")
except Exception as e:
    print(f"Error: {e}")

print("\nUpdating COLLATERAL allowance...")
try:
    result = client.update_balance_allowance(params)
    print(f"Result: {result}")
except Exception as e:
    print(f"Error: {e}")

# Also check CONDITIONAL tokens
print("\n=== CONDITIONAL ===")
params2 = BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, signature_type=2)
try:
    bal2 = client.get_balance_allowance(params2)
    print(f"Balance/Allowance: {bal2}")
except Exception as e:
    print(f"Error: {e}")

print("\nUpdating CONDITIONAL allowance...")
try:
    result2 = client.update_balance_allowance(params2)
    print(f"Result: {result2}")
except Exception as e:
    print(f"Error: {e}")
