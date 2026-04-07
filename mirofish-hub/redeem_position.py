#!/usr/bin/env python3
"""Redeem winning Polymarket position"""

import os
import sys

# Read .env manually to avoid null character issues
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                val = val.strip().strip('"').strip("'")
                if val and '\x00' not in val:
                    os.environ[key] = val

from py_clob_client.client import ClobClient

host = 'https://clob.polymarket.com'
chain_id = 137
pk = os.environ.get('POLYMARKET_PRIVATE_KEY')

if not pk:
    print("ERROR: No private key found")
    sys.exit(1)

print(f"Key loaded: {pk[:8]}...")

client = ClobClient(host, key=pk, chain_id=chain_id)

# The condition ID for Lakers vs Pistons
condition_id = '0x2442fd430fecccb337e64263589d16597d1a6098a3848cba9ff3bc382a1b16f9'

print(f"Redeeming condition: {condition_id}")
print("Sending transaction...")

try:
    result = client.redeem(condition_id)
    print(f"SUCCESS! Result: {result}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    
    # Try alternative method if available
    try:
        print("\nTrying CTF exchange redeem...")
        from py_clob_client.clob_types import RequestArgs
        # Alternative approach
    except ImportError as ie:  # H12 FIX: Specific import error
        print(f"CTF alternative not available: {ie}")
