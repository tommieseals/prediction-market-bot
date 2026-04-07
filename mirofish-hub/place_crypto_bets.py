import os
#!/usr/bin/env python3
"""Place crypto price bets on Polymarket"""

import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY

# Config
PRIVATE_KEY = os.getenv("POLY_PRIVATE_KEY", "")
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137

# Market condition IDs from whale database
BTC_70K_CONDITION = "0x5ebf0e6b2bd070e527124bb70f9162288f325ea68dc645b7c777ca0da9a1ccee"
ETH_2100_CONDITION = "0x1620faf803551d45a828b63536125851aee9e069acda72fe08f4b2ebd2761b13"

def main():
    print("=== CRYPTO BETS EXECUTION ===")
    print()
    
    # Initialize client
    client = ClobClient(HOST, key=PRIVATE_KEY, chain_id=CHAIN_ID)
    creds = client.derive_api_key()
    client.set_api_creds(creds)
    print("[OK] Client initialized")
    
    # Get market data
    print("\n--- BTC > $70k March 26 ---")
    resp = requests.get(f'https://clob.polymarket.com/markets/{BTC_70K_CONDITION}', timeout=15)
    btc_market = resp.json()
    print(f"Question: {btc_market.get('question')}")
    print(f"Active: {btc_market.get('active')}, Accepting: {btc_market.get('accepting_orders')}")
    
    BTC_YES_TOKEN = None
    btc_price = 0
    for t in btc_market.get('tokens', []):
        print(f"  {t['outcome']}: @ {t['price']}")
        if t['outcome'] == 'Yes':
            BTC_YES_TOKEN = t['token_id']
            btc_price = float(t['price'])
    
    print("\n--- ETH > $2,100 March 26 ---")
    resp = requests.get(f'https://clob.polymarket.com/markets/{ETH_2100_CONDITION}', timeout=15)
    eth_market = resp.json()
    print(f"Question: {eth_market.get('question')}")
    print(f"Active: {eth_market.get('active')}, Accepting: {eth_market.get('accepting_orders')}")
    
    ETH_YES_TOKEN = None
    eth_price = 0
    for t in eth_market.get('tokens', []):
        print(f"  {t['outcome']}: @ {t['price']}")
        if t['outcome'] == 'Yes':
            ETH_YES_TOKEN = t['token_id']
            eth_price = float(t['price'])
    
    if not BTC_YES_TOKEN or not ETH_YES_TOKEN:
        print("ERROR: Could not find tokens!")
        return
    
    # Calculate bet sizes ($15 each to leave some buffer)
    BET_SIZE = 15.0
    
    btc_shares = BET_SIZE / btc_price
    eth_shares = BET_SIZE / eth_price
    
    print(f"\n=== TRADE PLAN ===")
    print(f"1. BTC > $70k YES @ {btc_price:.3f} -> ${BET_SIZE} for {btc_shares:.1f} shares")
    print(f"   Payout if hit: ${btc_shares:.2f}")
    print(f"2. ETH > $2,100 YES @ {eth_price:.3f} -> ${BET_SIZE} for {eth_shares:.1f} shares")
    print(f"   Payout if hit: ${eth_shares:.2f}")
    print(f"\nTotal risk: ${BET_SIZE * 2}")
    print(f"Max payout: ${btc_shares + eth_shares:.2f} if both hit")
    
    print("\n>>> EXECUTING TRADES...")
    
    # Trade 1: BTC > $70k YES
    try:
        order1 = client.create_and_post_order(OrderArgs(
            token_id=BTC_YES_TOKEN,
            price=min(btc_price + 0.02, 0.99),
            size=btc_shares,
            side=BUY
        ))
        print(f"[OK] BTC > $70k YES order: {order1}")
    except Exception as e:
        print(f"[FAIL] BTC order failed: {e}")
    
    # Trade 2: ETH > $2,100 YES
    try:
        order2 = client.create_and_post_order(OrderArgs(
            token_id=ETH_YES_TOKEN,
            price=min(eth_price + 0.02, 0.99),
            size=eth_shares,
            side=BUY
        ))
        print(f"[OK] ETH > $2,100 YES order: {order2}")
    except Exception as e:
        print(f"[FAIL] ETH order failed: {e}")
    
    print("\n=== DONE ===")

if __name__ == "__main__":
    main()
