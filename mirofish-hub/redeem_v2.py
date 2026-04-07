# -*- coding: utf-8 -*-
"""Redeem winning Polymarket position - Lakers vs Pistons"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from web3 import Web3

pk = '39f1a59fe9c2c006ac51e1edad69be0a0133df21c053e91f34387ba9cc9f30ae'

RPC_URL = 'https://rpc-mainnet.matic.quiknode.pro'
w3 = Web3(Web3.HTTPProvider(RPC_URL))

print(f"Connected: {w3.is_connected()}")

account = w3.eth.account.from_key(pk)
print(f"Wallet: {account.address}")

# Polymarket Neg Risk CTF Exchange for sports markets
NEG_RISK_CTF_EXCHANGE = Web3.to_checksum_address('0xC5d563A36AE78145C45a50134d48A1215220f80a')

# Neg Risk Adapter
NEG_RISK_ADAPTER = Web3.to_checksum_address('0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296')

# Standard CTF
CTF_CONTRACT = Web3.to_checksum_address('0x4D97DCd97eC945f40cF65F87097ACe5EA0476045')

# USDC.e on Polygon (bridged) - this is what Polymarket uses
USDC_E = Web3.to_checksum_address('0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174')

condition_id = '0x2442fd430fecccb337e64263589d16597d1a6098a3848cba9ff3bc382a1b16f9'

# Try using the Neg Risk Adapter's redeem function
ADAPTER_ABI = [{
    "inputs": [
        {"name": "conditionId", "type": "bytes32"},
        {"name": "amounts", "type": "uint256[]"}
    ],
    "name": "redeemPositions",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
}]

# Standard CTF redeem ABI
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

print(f"\nRedeeming position...")
print(f"Condition: {condition_id[:20]}...")

contract = w3.eth.contract(address=CTF_CONTRACT, abi=CTF_ABI)

nonce = w3.eth.get_transaction_count(account.address)
print(f"Nonce: {nonce}")

# For binary markets: index_sets=[1,2] means both YES and NO
# We hold Pistons (outcome index 1), so we use index set = 2 (binary: 10)
# Actually for full redemption of winning shares, we need the index of our outcome
# outcomeIndex was 1 (Pistons), so the indexSet is 2^1 = 2
parent_collection = bytes(32)
index_sets = [2]  # 2^1 for outcome index 1

try:
    tx = contract.functions.redeemPositions(
        USDC_E,
        parent_collection,
        bytes.fromhex(condition_id[2:]),
        index_sets
    ).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'gas': 300000,
        'maxFeePerGas': w3.to_wei(100, 'gwei'),
        'maxPriorityFeePerGas': w3.to_wei(30, 'gwei'),
        'chainId': 137
    })
    
    print("Signing...")
    signed = account.sign_transaction(tx)
    
    print("Sending...")
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    
    print(f"\nTX SENT: {tx_hash.hex()}")
    print(f"https://polygonscan.com/tx/{tx_hash.hex()}")
    
    print("\nWaiting for confirmation (up to 2 min)...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    
    if receipt['status'] == 1:
        print("SUCCESS - Position redeemed!")
    else:
        print("FAILED - Check polygonscan for details")
    print(f"Gas used: {receipt['gasUsed']}")
    
except Exception as e:
    print(f"\nError: {type(e).__name__}: {e}")
