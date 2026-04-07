import os
#!/usr/bin/env python3
"""Place whale consensus bets on Polymarket"""

import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY

# Config
PRIVATE_KEY = os.getenv("POLY_PRIVATE_KEY", "")
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon

def main():
    print("=== POLYMARKET TRADE EXECUTION ===")
    print()
    
    # Initialize client
    client = ClobClient(HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID)
    creds = client.derive_api_key()
    client.set_api_creds(creds)
    
    print("[OK] Client initialized")
    
    # Get market data and tokens
    # Thunder O/U market
    resp = requests.get('https://clob.polymarket.com/markets/0x46c72d5cb92972c2d20d24f6ba68065a10545853557d0474cc73a88a718428f4')
    thunder_market = resp.json()
    print(f"\nThunder O/U 218.5:")
    THUNDER_UNDER = None
    thunder_price = 0
    for t in thunder_market.get('tokens', []):
        print(f"  {t['outcome']}: @ {t['price']}")
        if t['outcome'] == 'Under':
            THUNDER_UNDER = t['token_id']
            thunder_price = float(t['price'])
    
    # Heat vs Cavs market  
    resp = requests.get('https://clob.polymarket.com/markets/0xc75831d24fabad4f6ff9dc932a177b5a611d769a704b4ee446eb57add7a8fd51')
    cavs_market = resp.json()
    print(f"\nHeat vs Cavaliers:")
    CAVS = None
    cavs_price = 0
    for t in cavs_market.get('tokens', []):
        print(f"  {t['outcome']}: @ {t['price']}")
        if t['outcome'] == 'Cavaliers':
            CAVS = t['token_id']
            cavs_price = float(t['price'])
    
    if not THUNDER_UNDER or not CAVS:
        print("ERROR: Could not find tokens!")
        return
    
    # Calculate bet sizes ($20 each)
    BET_SIZE = 20.0
    
    thunder_shares = BET_SIZE / thunder_price
    cavs_shares = BET_SIZE / cavs_price
    
    print(f"\n=== TRADE PLAN ===")
    print(f"1. Thunder UNDER 218.5 @ {thunder_price:.3f} -> ${BET_SIZE} for {thunder_shares:.1f} shares")
    print(f"   Payout if hit: ${thunder_shares:.2f}")
    print(f"2. Cavaliers ML @ {cavs_price:.3f} -> ${BET_SIZE} for {cavs_shares:.1f} shares")
    print(f"   Payout if hit: ${cavs_shares:.2f}")
    print(f"\nTotal risk: ${BET_SIZE * 2}")
    print(f"Max payout: ${thunder_shares + cavs_shares:.2f} if both hit")
    
    # Execute trades
    print("\n>>> EXECUTING TRADES...")
    
    # Trade 1: Thunder Under
    try:
        order1 = client.create_and_post_order(OrderArgs(
            token_id=THUNDER_UNDER,
            price=min(thunder_price + 0.02, 0.99),  # Slightly above to ensure fill
            size=thunder_shares,
            side=BUY
        ))
        print(f"[OK] Thunder UNDER order: {order1}")
    except Exception as e:
        print(f"[FAIL] Thunder order failed: {e}")
    
    # Trade 2: Cavaliers ML
    try:
        order2 = client.create_and_post_order(OrderArgs(
            token_id=CAVS,
            price=min(cavs_price + 0.02, 0.99),
            size=cavs_shares,
            side=BUY
        ))
        print(f"[OK] Cavaliers ML order: {order2}")
    except Exception as e:
        print(f"[FAIL] Cavaliers order failed: {e}")
    
    print("\n=== DONE ===")

if __name__ == "__main__":
    main()
