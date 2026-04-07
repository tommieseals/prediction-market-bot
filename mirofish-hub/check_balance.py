#!/usr/bin/env python3
"""Check Polymarket USDC balance"""
import os
from dotenv import load_dotenv

# Load env
load_dotenv('.env.polymarket')

private_key = os.environ.get('POLY_PRIVATE_KEY')
api_key = os.environ.get('POLY_API_KEY')
api_secret = os.environ.get('POLY_API_SECRET')

print(f"Private key found: {bool(private_key)}")
print(f"API key found: {bool(api_key)}")
print(f"API secret found: {bool(api_secret)}")

if private_key:
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds
        
        # Create client with API creds if available
        if api_key and api_secret:
            creds = ApiCreds(api_key=api_key, api_secret=api_secret, api_passphrase="")
            client = ClobClient(
                host='https://clob.polymarket.com',
                key=private_key,
                chain_id=137,
                creds=creds
            )
        else:
            client = ClobClient(
                host='https://clob.polymarket.com',
                key=private_key,
                chain_id=137
            )
        
        # Get balance
        balances = client.get_balance_allowance()
        print(f"\n=== POLYMARKET WALLET ===")
        balance = float(balances.get("balance", 0)) / 1e6
        allowance = float(balances.get("allowance", 0)) / 1e6
        print(f"USDC Balance: ${balance:.2f}")
        print(f"Allowance: ${allowance:.2f}")
        
        if balance > 0:
            print("\n[OK] READY TO TRADE!")
        else:
            print("\n[FAIL] No USDC balance detected")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
else:
    print("No private key found in .env.polymarket")
