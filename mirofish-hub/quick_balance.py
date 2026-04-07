#!/usr/bin/env python3
"""Quick balance check with proper auth"""
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path(__file__).parent / '.env')
pk = os.environ.get('POLY_PRIVATE_KEY', '')
print(f'Key loaded: {bool(pk)}')
print(f'Key length: {len(pk)}')

if not pk:
    print("No private key found!")
    exit(1)

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

# Init client
client = ClobClient(
    host='https://clob.polymarket.com',
    key=pk,
    chain_id=137
)

# Derive API credentials
print('Deriving API credentials...')
try:
    creds = client.derive_api_key()
    print(f'API Key: {creds.api_key[:20]}...')
    
    # Create authenticated client
    creds_obj = ApiCreds(
        api_key=creds.api_key,
        api_secret=creds.api_secret,
        api_passphrase=creds.api_passphrase
    )
    
    client2 = ClobClient(
        host='https://clob.polymarket.com',
        key=pk,
        chain_id=137,
        creds=creds_obj
    )
    
    # Check balance
    balance = client2.get_balance_allowance()
    usdc = float(balance.get("balance", 0)) / 1e6
    allowance = float(balance.get("allowance", 0)) / 1e6
    
    print(f'\n=== POLYMARKET WALLET ===')
    print(f'Address: 0x299aCc0857B943d8490ECb1820fD458B3B58c728')
    print(f'USDC Balance: ${usdc:.2f}')
    print(f'Allowance: ${allowance:.2f}')
    
    if usdc > 0:
        print('\n[OK] READY TO TRADE!')
    else:
        print('\n[FAIL] Wallet is empty - need to deposit USDC on Polygon')
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
