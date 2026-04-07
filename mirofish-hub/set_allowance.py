#!/usr/bin/env python3
"""Set USDC allowance for Polymarket trading"""

import os
from dotenv import load_dotenv
load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from py_clob_client.constants import POLYGON

private_key = os.getenv("POLY_PRIVATE_KEY")
if not private_key:
    print("ERROR: POLY_PRIVATE_KEY not set in .env")
    exit(1)

print("Initializing CLOB client...")
client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=POLYGON,
    key=private_key,
)

print("Deriving API credentials...")
client.set_api_creds(client.create_or_derive_api_creds())

print("Setting allowances for USDC and conditional tokens...")
try:
    # This sets the ERC20 approval for the exchange
    result = client.set_allowances()
    print(f"Allowances set: {result}")
except Exception as e:
    print(f"Error setting allowances: {e}")
    
    # Try alternative methods
    print("\nTrying alternative methods...")
    methods = [m for m in dir(client) if 'allow' in m.lower() or 'approv' in m.lower()]
    print(f"Available approval methods: {methods}")
