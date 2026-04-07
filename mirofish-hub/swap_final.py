#!/usr/bin/env python3
"""FINAL Swap: Approve first, then swap"""

import os
import requests
from dotenv import load_dotenv
load_dotenv()

from web3 import Web3
from eth_account import Account

PRIVATE_KEY = os.getenv('POLY_PRIVATE_KEY')
RPC_URL = "https://rpc-mainnet.matic.quiknode.pro"

USDC_NATIVE = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
USDC_BRIDGED = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
PARASWAP_PROXY = "0x216b4b4ba9f3e719726886d34a177484278bfcae"

w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)
wallet = account.address

swap_amount = 60 * 10**6

print(f"Wallet: {wallet}")
print(f"Swapping ${swap_amount/1e6:.0f} USDC → USDC.e")

# Step 1: Approve ParaSwap TokenTransferProxy
print("\n[1] Approving ParaSwap...")
ERC20_ABI = [
    {"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
]

usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_NATIVE), abi=ERC20_ABI)
nonce = w3.eth.get_transaction_count(wallet)

approve_tx = usdc.functions.approve(
    Web3.to_checksum_address(PARASWAP_PROXY),
    2**256 - 1  # Max approval
).build_transaction({
    'from': wallet,
    'nonce': nonce,
    'gas': 100000,
    'gasPrice': w3.eth.gas_price,
    'chainId': 137
})

signed = account.sign_transaction(approve_tx)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f"Approve TX: {tx_hash.hex()[:20]}...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
print(f"Approved: {'OK' if receipt['status'] == 1 else 'FAILED'}")
nonce += 1

# Step 2: Get swap price
print("\n[2] Getting swap quote...")
price_url = f"https://apiv5.paraswap.io/prices?srcToken={USDC_NATIVE}&destToken={USDC_BRIDGED}&amount={swap_amount}&side=SELL&network=137&srcDecimals=6&destDecimals=6"
r = requests.get(price_url, timeout=30)
price_data = r.json()
dest_amount = int(price_data['priceRoute']['destAmount'])
print(f"Will receive: ${dest_amount/1e6:.2f} USDC.e")

# Step 3: Get swap transaction
print("\n[3] Building swap transaction...")
tx_url = "https://apiv5.paraswap.io/transactions/137"
tx_body = {
    'srcToken': USDC_NATIVE,
    'destToken': USDC_BRIDGED,
    'srcAmount': str(swap_amount),
    'destAmount': str(int(dest_amount * 0.99)),
    'priceRoute': price_data['priceRoute'],
    'userAddress': wallet,
    'partner': 'clawdbot',
}

r2 = requests.post(tx_url, json=tx_body, timeout=30)
tx_data = r2.json()

if 'error' in tx_data:
    print(f"Error: {tx_data['error']}")
else:
    print(f"Contract: {tx_data['to']}")
    
    # Step 4: Execute swap
    print("\n[4] Executing swap...")
    swap_tx = {
        'from': wallet,
        'to': Web3.to_checksum_address(tx_data['to']),
        'data': tx_data['data'],
        'value': int(tx_data.get('value', 0)),
        'gas': int(tx_data.get('gas', 500000)),
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
        'chainId': 137
    }
    
    signed = account.sign_transaction(swap_tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Swap TX: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    
    if receipt['status'] == 1:
        print("SWAP SUCCESS!")
    else:
        print("SWAP FAILED")

# Final balances
print("\n=== FINAL BALANCES ===")
usdc_bridged = w3.eth.contract(address=Web3.to_checksum_address(USDC_BRIDGED), abi=ERC20_ABI)
print(f"Native USDC: ${usdc.functions.balanceOf(wallet).call()/1e6:.2f}")
print(f"USDC.e: ${usdc_bridged.functions.balanceOf(wallet).call()/1e6:.2f}")
