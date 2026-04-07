#!/usr/bin/env python3
"""Fix USDC allowance for Polymarket trading"""

import os
from dotenv import load_dotenv
load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

pk = os.getenv('POLY_PRIVATE_KEY')
print(f"Using wallet with key: {pk[:8]}...")

client = ClobClient(
    host='https://clob.polymarket.com', 
    chain_id=POLYGON, 
    key=pk,
    signature_type=2,  # EIP712
    funder=None
)

print("Setting API credentials...")
creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)
print(f"API Key: {creds.api_key[:16]}...")

print("\nChecking balance allowance...")
try:
    from py_clob_client.clob_types import BalanceAllowanceParams
    params = BalanceAllowanceParams(signature_type=2)
    bal = client.get_balance_allowance(params)
    print(f"Balance/Allowance: {bal}")
except Exception as e:
    print(f"Balance check error: {e}")

print("\nUpdating allowance...")
try:
    from py_clob_client.clob_types import BalanceAllowanceParams
    params = BalanceAllowanceParams(signature_type=2)
    result = client.update_balance_allowance(params)
    print(f"Update result: {result}")
except Exception as e:
    print(f"Update error: {e}")
