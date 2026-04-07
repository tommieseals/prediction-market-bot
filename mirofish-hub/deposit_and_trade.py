#!/usr/bin/env python3
"""Deposit USDC to Polymarket and execute trades"""

import os
import json
from dotenv import load_dotenv
load_dotenv()

from web3 import Web3
from eth_account import Account

# Config
PRIVATE_KEY = os.getenv('POLY_PRIVATE_KEY')
RPC_URL = "https://rpc-mainnet.matic.quiknode.pro"

# Polygon addresses
USDC_ADDRESS = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # USDC (native) on Polygon
POLYMARKET_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"  # CTF Exchange

# USDC ABI (minimal for approve)
USDC_ABI = [
    {"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}
]

print("=== POLYMARKET DEPOSIT & TRADE ===")

# Connect
w3 = Web3(Web3.HTTPProvider(RPC_URL))
print(f"Connected to Polygon: {w3.is_connected()}")

account = Account.from_key(PRIVATE_KEY)
wallet = account.address
print(f"Wallet: {wallet}")

# Check USDC balance
usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=USDC_ABI)
balance = usdc.functions.balanceOf(wallet).call()
balance_human = balance / 1e6
print(f"USDC Balance: ${balance_human:.2f}")

# Check current allowance
allowance = usdc.functions.allowance(wallet, Web3.to_checksum_address(POLYMARKET_EXCHANGE)).call()
allowance_human = allowance / 1e6
print(f"Current allowance for Polymarket: ${allowance_human:.2f}")

if allowance_human < 100:
    print("\n[!] Setting unlimited USDC allowance for Polymarket...")
    
    # Build approve transaction
    nonce = w3.eth.get_transaction_count(wallet)
    max_uint256 = 2**256 - 1
    
    approve_tx = usdc.functions.approve(
        Web3.to_checksum_address(POLYMARKET_EXCHANGE),
        max_uint256
    ).build_transaction({
        'from': wallet,
        'nonce': nonce,
        'gas': 100000,
        'gasPrice': w3.eth.gas_price,
        'chainId': 137
    })
    
    # Sign and send
    signed = account.sign_transaction(approve_tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Approve TX: {tx_hash.hex()}")
    
    # Wait for confirmation
    print("Waiting for confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f"Confirmed! Status: {receipt['status']}")
    
    # Verify new allowance
    new_allowance = usdc.functions.allowance(wallet, Web3.to_checksum_address(POLYMARKET_EXCHANGE)).call()
    print(f"New allowance: ${new_allowance / 1e6:.2f}")
else:
    print("[OK] Allowance already set")

print("\n=== NOW EXECUTING TRADES ===")

# Now try the trades via CLOB
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY

client = ClobClient(
    host='https://clob.polymarket.com', 
    chain_id=POLYGON, 
    key=PRIVATE_KEY,
    signature_type=2,
)
creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)

# Trade 1: Lakers vs Pistons NO
print("\n[TRADE 1] Lakers vs Pistons NO @ $0.49 - $25")
token1 = "90898434341036885550167009542356127359697126382953020709355461557872368670502"
try:
    order1 = OrderArgs(token_id=token1, price=0.49, size=25.0, side=BUY)
    result1 = client.create_and_post_order(order1)
    print(f"SUCCESS: {result1}")
except Exception as e:
    print(f"Error: {e}")

# Trade 2: Miami Open NO
print("\n[TRADE 2] Miami Open NO @ $0.26 - $25")
token2 = "66821844545064790634205316417181093550754708801200021790172871331785360277200"
try:
    order2 = OrderArgs(token_id=token2, price=0.26, size=25.0, side=BUY)
    result2 = client.create_and_post_order(order2)
    print(f"SUCCESS: {result2}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== DONE ===")
