#!/usr/bin/env python3
"""Swap via ParaSwap aggregator"""

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

w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)
wallet = account.address

print(f"Wallet: {wallet}")

swap_amount = 60 * 10**6  # $60

# ParaSwap API
print("\n=== ParaSwap Price Check ===")
price_url = f"https://apiv5.paraswap.io/prices?srcToken={USDC_NATIVE}&destToken={USDC_BRIDGED}&amount={swap_amount}&side=SELL&network=137&srcDecimals=6&destDecimals=6"

try:
    r = requests.get(price_url, timeout=30)
    price_data = r.json()
    print(f"Price response: {price_data}")
    
    if 'priceRoute' in price_data:
        dest_amount = int(price_data['priceRoute']['destAmount'])
        print(f"Expected output: ${dest_amount/1e6:.2f} USDC.e")
        
        # Get swap transaction
        print("\nGetting swap transaction...")
        tx_url = "https://apiv5.paraswap.io/transactions/137"
        tx_body = {
            'srcToken': USDC_NATIVE,
            'destToken': USDC_BRIDGED,
            'srcAmount': str(swap_amount),
            'destAmount': str(int(dest_amount * 0.99)),  # 1% slippage
            'priceRoute': price_data['priceRoute'],
            'userAddress': wallet,
            'partner': 'clawdbot',
        }
        
        r2 = requests.post(tx_url, json=tx_body, timeout=30)
        tx_data = r2.json()
        print(f"TX data: {tx_data}")
        
        if 'to' in tx_data:
            # Approve first
            ERC20_ABI = [
                {"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
            ]
            usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_NATIVE), abi=ERC20_ABI)
            
            spender = tx_data.get('to')
            print(f"\nApproving {spender}...")
            
            nonce = w3.eth.get_transaction_count(wallet)
            approve_tx = usdc.functions.approve(
                Web3.to_checksum_address(spender),
                swap_amount * 2  # Approve extra
            ).build_transaction({
                'from': wallet,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'chainId': 137
            })
            signed = account.sign_transaction(approve_tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            print("Approved!")
            nonce += 1
            
            # Execute swap
            print("Executing swap...")
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
            print(f"TX: {tx_hash.hex()}")
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            print(f"Status: {'SUCCESS!' if receipt['status'] == 1 else 'FAILED'}")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Check final balances
print("\n=== FINAL BALANCES ===")
ERC20_ABI = [{"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]
usdc_native = w3.eth.contract(address=Web3.to_checksum_address(USDC_NATIVE), abi=ERC20_ABI)
usdc_bridged = w3.eth.contract(address=Web3.to_checksum_address(USDC_BRIDGED), abi=ERC20_ABI)
print(f"Native USDC: ${usdc_native.functions.balanceOf(wallet).call()/1e6:.2f}")
print(f"USDC.e: ${usdc_bridged.functions.balanceOf(wallet).call()/1e6:.2f}")
