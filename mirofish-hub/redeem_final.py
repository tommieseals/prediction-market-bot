# -*- coding: utf-8 -*-
"""Redeem Polymarket position - Final attempt"""

from web3 import Web3
import time

pk = '39f1a59fe9c2c006ac51e1edad69be0a0133df21c053e91f34387ba9cc9f30ae'
RPC_URL = 'https://rpc-mainnet.matic.quiknode.pro'
w3 = Web3(Web3.HTTPProvider(RPC_URL))

account = w3.eth.account.from_key(pk)
print(f"Wallet: {account.address}")

# Check current nonce situation
pending_nonce = w3.eth.get_transaction_count(account.address, 'pending')
confirmed_nonce = w3.eth.get_transaction_count(account.address, 'latest')
print(f"Confirmed nonce: {confirmed_nonce}, Pending: {pending_nonce}")

# If there's a stuck transaction, cancel it first
if pending_nonce > confirmed_nonce:
    print(f"\nCancelling stuck transaction at nonce {confirmed_nonce}...")
    
    # Send empty transaction with high gas to cancel
    cancel_tx = {
        'from': account.address,
        'to': account.address,
        'value': 0,
        'nonce': confirmed_nonce,
        'gas': 21000,
        'maxFeePerGas': w3.to_wei(200, 'gwei'),
        'maxPriorityFeePerGas': w3.to_wei(100, 'gwei'),
        'chainId': 137
    }
    
    signed_cancel = account.sign_transaction(cancel_tx)
    cancel_hash = w3.eth.send_raw_transaction(signed_cancel.raw_transaction)
    print(f"Cancel TX: {cancel_hash.hex()}")
    
    # Wait for cancel to confirm
    print("Waiting for cancel to confirm...")
    receipt = w3.eth.wait_for_transaction_receipt(cancel_hash, timeout=60)
    print(f"Cancel confirmed, status: {receipt['status']}")
    time.sleep(2)

# Now do the actual redemption
print("\n--- REDEEMING POSITION ---")

# Gnosis CTF Contract
CTF = Web3.to_checksum_address('0x4D97DCd97eC945f40cF65F87097ACe5EA0476045')

# USDC.e (what Polymarket uses)
USDC_E = Web3.to_checksum_address('0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174')

# Condition ID for Lakers vs Pistons
condition_id_hex = '2442fd430fecccb337e64263589d16597d1a6098a3848cba9ff3bc382a1b16f9'
condition_id = bytes.fromhex(condition_id_hex)

# Parent collection ID (zero for root)
parent_collection = bytes(32)

# Index sets - we hold outcome index 1 (Pistons), so indexSet = 2^1 = 2
# But to redeem ALL outcomes we won, we pass [1, 2] for both sides
# Actually for winning side only: [2] means outcome index 1
index_sets = [2]

# CTF ABI for redeemPositions
CTF_ABI = [{
    "inputs": [
        {"name": "collateralToken", "type": "address"},
        {"name": "parentCollectionId", "type": "bytes32"},
        {"name": "conditionId", "type": "bytes32"},
        {"name": "indexSets", "type": "uint256[]"}
    ],
    "name": "redeemPositions",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
}]

contract = w3.eth.contract(address=CTF, abi=CTF_ABI)

# Get fresh nonce
nonce = w3.eth.get_transaction_count(account.address, 'latest')
print(f"Using nonce: {nonce}")

# Build the redeem transaction
tx = contract.functions.redeemPositions(
    USDC_E,
    parent_collection,
    condition_id,
    index_sets
).build_transaction({
    'from': account.address,
    'nonce': nonce,
    'gas': 300000,
    'maxFeePerGas': w3.to_wei(150, 'gwei'),
    'maxPriorityFeePerGas': w3.to_wei(50, 'gwei'),
    'chainId': 137
})

print("Signing redeem transaction...")
signed = account.sign_transaction(tx)

print("Sending to Polygon...")
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f"TX Hash: {tx_hash.hex()}")
print(f"View: https://polygonscan.com/tx/{tx_hash.hex()}")

print("\nWaiting for confirmation...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

if receipt['status'] == 1:
    print("\n=== SUCCESS! Position redeemed! ===")
else:
    print("\n=== FAILED - Check polygonscan for details ===")

print(f"Gas used: {receipt['gasUsed']}")
print(f"Block: {receipt['blockNumber']}")
