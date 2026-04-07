#!/usr/bin/env python3
"""Test Polymarket trading"""
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path(__file__).parent / '.env')

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

PRIVATE_KEY = os.environ.get('POLY_PRIVATE_KEY')
print(f"Key loaded: {bool(PRIVATE_KEY)}")

# Initialize client
client = ClobClient(
    host='https://clob.polymarket.com',
    key=PRIVATE_KEY,
    chain_id=137
)

# Derive API credentials
print("Deriving API credentials...")
try:
    creds = client.derive_api_key()
    print(f"API Key: {creds.api_key[:20]}...")
    print(f"API Secret: {creds.api_secret[:20]}...")
    
    # Create new client with creds
    creds_obj = ApiCreds(
        api_key=creds.api_key,
        api_secret=creds.api_secret,
        api_passphrase=creds.api_passphrase
    )
    
    client = ClobClient(
        host='https://clob.polymarket.com',
        key=PRIVATE_KEY,
        chain_id=137,
        creds=creds_obj
    )
    
    # Check balance using API
    print("\nChecking balance...")
    
    # Try direct API call
    import requests
    headers = {
        'Authorization': f'Bearer {creds.api_key}'
    }
    
    # Get markets to test API
    print("\nFetching sample markets...")
    markets = client.get_markets()
    print(f"Found {len(markets)} markets")
    
    if markets:
        m = markets[0]
        print(f"\nSample market: {m.get('question', 'N/A')[:60]}...")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
