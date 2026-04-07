#!/usr/bin/env python3
"""Place NO bet on Cerundolo vs Zverev"""
import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from eth_account import Account

load_dotenv()

# Market details
MARKET_TITLE = "Miami Open: Francisco Cerundolo vs Alexander Zverev"
CONDITION_ID = "0x975268bb712c2ccb47267286bc8e99689057cb9a00ca9a6e463fe4f08c590448"
TOKEN_ID = "115788675318557680730128024074324154048239448688490429829875719919215023255421"
SIDE = "NO"
PRICE = 0.45
SIZE_USD = 7.00  # Kelly 7.8% of ~$90

# Initialize client
pk = os.getenv('POLY_PRIVATE_KEY')
host = "https://clob.polymarket.com"
chain_id = 137  # Polygon

print(f"=== PLACING BET ===")
print(f"Market: {MARKET_TITLE}")
print(f"Side: {SIDE} @ ${PRICE}")
print(f"Size: ${SIZE_USD}")

try:
    client = ClobClient(host, key=pk, chain_id=chain_id)
    
    # Get API credentials
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    print(f"API creds set")
    
    # Calculate shares
    shares = SIZE_USD / PRICE
    print(f"Shares: {shares:.2f}")
    
    # Create order
    order_args = OrderArgs(
        token_id=TOKEN_ID,
        price=PRICE,
        size=shares,
        side="BUY"
    )
    
    signed_order = client.create_order(order_args)
    print(f"Order created: {signed_order}")
    
    # Post order
    result = client.post_order(signed_order)
    print(f"Order result: {result}")
    
    # Log to database
    conn = sqlite3.connect('data/whale_hunter.db')
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO my_trades (market_title, condition_id, token_id, side, entry_price, shares, cost, outcome, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (MARKET_TITLE, CONDITION_ID, TOKEN_ID, SIDE, PRICE, shares, SIZE_USD, 
          "HIGH CONFIDENCE - 8 whales 88% agree, MiroFish 76%, Edge +31.3%", 
          datetime.now().isoformat()))
    conn.commit()
    trade_id = cur.lastrowid
    conn.close()
    
    print(f"\n=== SUCCESS ===")
    print(f"Trade logged as ID: {trade_id}")
    print(f"Order: {result}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
