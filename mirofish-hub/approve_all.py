#!/usr/bin/env python3
"""Approve USDC for ALL Polymarket contracts"""

import os
from dotenv import load_dotenv
load_dotenv()

from web3 import Web3
from eth_account import Account

PRIVATE_KEY = os.getenv('POLY_PRIVATE_KEY')
RPC_URL = "https://rpc-mainnet.matic.quiknode.pro"

# Both USDC addresses on Polygon
USDC_NATIVE = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
USDC_BRIDGED = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# ALL Polymarket contracts that need approval
POLYMARKET_CONTRACTS = [
    "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",  # CTF Exchange
    "0xC5d563A36AE78145C45a50134d48A1215220f80a",  # Neg Risk CTF Exchange  
    "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",  # Neg Risk Adapter
]

USDC_ABI = [
    {"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)
wallet = account.address

print(f"Connected: {w3.is_connected()}")
print(f"Wallet: {wallet}")

# Check balances for both USDC tokens
for name, addr in [("Native USDC", USDC_NATIVE), ("Bridged USDC.e", USDC_BRIDGED)]:
    usdc = w3.eth.contract(address=Web3.to_checksum_address(addr), abi=USDC_ABI)
    bal = usdc.functions.balanceOf(wallet).call()
    print(f"{name}: ${bal/1e6:.2f}")

# Approve ALL contracts for BOTH USDC tokens
max_uint256 = 2**256 - 1
nonce = w3.eth.get_transaction_count(wallet)

for usdc_name, usdc_addr in [("Native USDC", USDC_NATIVE), ("Bridged USDC.e", USDC_BRIDGED)]:
    usdc = w3.eth.contract(address=Web3.to_checksum_address(usdc_addr), abi=USDC_ABI)
    
    for contract in POLYMARKET_CONTRACTS:
        print(f"\nApproving {usdc_name} for {contract[:10]}...")
        
        try:
            approve_tx = usdc.functions.approve(
                Web3.to_checksum_address(contract),
                max_uint256
            ).build_transaction({
                'from': wallet,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'chainId': 137
            })
            
            signed = account.sign_transaction(approve_tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            print(f"  TX: {tx_hash.hex()[:16]}...")
            
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            print(f"  Status: {'OK' if receipt['status'] == 1 else 'FAILED'}")
            
            nonce += 1
        except Exception as e:
            print(f"  Error: {e}")

print("\n=== NOW TRYING TRADE ===")

from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY

client = ClobClient(host='https://clob.polymarket.com', chain_id=POLYGON, key=PRIVATE_KEY, signature_type=2)
client.set_api_creds(client.create_or_derive_api_creds())

print("\n[TRADE 1] Lakers vs Pistons NO @ $0.49 - $25")
try:
    order = OrderArgs(token_id="90898434341036885550167009542356127359697126382953020709355461557872368670502", price=0.49, size=25.0, side=BUY)
    result = client.create_and_post_order(order)
    print(f"SUCCESS: {result}")
except Exception as e:
    print(f"Error: {e}")

print("\n[TRADE 2] Miami Open NO @ $0.26 - $25")
try:
    order = OrderArgs(token_id="66821844545064790634205316417181093550754708801200021790172871331785360277200", price=0.26, size=25.0, side=BUY)
    result = client.create_and_post_order(order)
    print(f"SUCCESS: {result}")
except Exception as e:
    print(f"Error: {e}")
