import os
#!/usr/bin/env python3
"""Place Hawks vs Pistons bet"""

import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY

PRIVATE_KEY = os.getenv("POLY_PRIVATE_KEY", "")
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137

HAWKS_CONDITION = "0x9f8ff09142e006b13e263d07b6c8813e89327ba79bd73f7f3cee6a2ef88903c4"

def main():
    print("=== HAWKS BET EXECUTION ===")
    print()
    
    client = ClobClient(HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID)
    creds = client.derive_api_key()
    client.set_api_creds(creds)
    print("[OK] Client initialized")
    
    # Get market data
    resp = requests.get(f'https://clob.polymarket.com/markets/{HAWKS_CONDITION}', timeout=15)
    market = resp.json()
    print(f"Market: {market.get('question')}")
    print(f"Active: {market.get('active')}, Accepting: {market.get('accepting_orders')}")
    
    HAWKS_TOKEN = None
    hawks_price = 0
    for t in market.get('tokens', []):
        print(f"  {t['outcome']}: @ {t['price']}")
        if t['outcome'] == 'Hawks':
            HAWKS_TOKEN = t['token_id']
            hawks_price = float(t['price'])
    
    if not HAWKS_TOKEN:
        print("ERROR: Could not find Hawks token!")
        return
    
    BET_SIZE = 2.0
    hawks_shares = BET_SIZE / hawks_price
    
    print(f"\n=== TRADE PLAN ===")
    print(f"Hawks YES @ {hawks_price:.3f} -> ${BET_SIZE} for {hawks_shares:.1f} shares")
    print(f"Payout if win: ${hawks_shares:.2f}")
    
    print("\n>>> EXECUTING TRADE...")
    
    try:
        order = client.create_and_post_order(OrderArgs(
            token_id=HAWKS_TOKEN,
            price=min(hawks_price + 0.02, 0.99),
            size=hawks_shares,
            side=BUY
        ))
        print(f"[OK] Hawks order: {order}")
    except Exception as e:
        print(f"[FAIL] Order failed: {e}")
    
    print("\n=== DONE ===")

if __name__ == "__main__":
    main()
