#!/usr/bin/env python3
"""Execute Polymarket trades with proper signing"""

import os
from dotenv import load_dotenv
load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

pk = os.getenv('POLY_PRIVATE_KEY')

print("=== POLYMARKET TRADE EXECUTION ===")

# Try with default signature type (let client decide)
client = ClobClient(
    host='https://clob.polymarket.com', 
    chain_id=POLYGON, 
    key=pk,
)

print("Deriving API credentials...")
creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)
print(f"API Key: {creds.api_key[:16]}...")
print(f"Wallet: {client.get_address()}")

# Check balance
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
bal = client.get_balance_allowance(params)
print(f"\nPolymarket balance: {bal}")

# Create order properly
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY

print("\n[TRADE 1] Lakers vs Pistons NO @ $0.49 - $25")
token1 = "90898434341036885550167009542356127359697126382953020709355461557872368670502"
try:
    # Use create_order first, then post
    order_args = OrderArgs(
        token_id=token1,
        price=0.49,
        size=25.0,
        side=BUY,
    )
    
    # Try creating the signed order
    signed_order = client.create_order(order_args)
    print(f"Signed order: {signed_order}")
    
    # Post it
    result = client.post_order(signed_order)
    print(f"Result: {result}")
    
except Exception as e:
    print(f"Error: {e}")
    
    # Try alternative: create_and_post_order with explicit tick size
    print("\nTrying alternative method...")
    try:
        # Get market info first
        resp = client.get_order_book(token1)
        print(f"Order book: {resp}")
    except Exception as e2:
        print(f"Order book error: {e2}")

print("\n[TRADE 2] Miami Open NO @ $0.26 - $25")
token2 = "66821844545064790634205316417181093550754708801200021790172871331785360277200"
try:
    order_args = OrderArgs(
        token_id=token2,
        price=0.26,
        size=25.0,
        side=BUY,
    )
    signed_order = client.create_order(order_args)
    result = client.post_order(signed_order)
    print(f"Result: {result}")
except Exception as e:
    print(f"Error: {e}")
