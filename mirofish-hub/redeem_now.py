#!/usr/bin/env python3
"""Redeem winning Polymarket position - Lakers vs Pistons"""

from web3 import Web3

# Private key
pk = '39f1a59fe9c2c006ac51e1edad69be0a0133df21c053e91f34387ba9cc9f30ae'

# Connect to Polygon via QuickNode (same as balance checker)
RPC_URL = 'https://rpc-mainnet.matic.quiknode.pro'
w3 = Web3(Web3.HTTPProvider(RPC_URL))

print(f"Connected: {w3.is_connected()}")

account = w3.eth.account.from_key(pk)
print(f"Wallet: {account.address}")

# Polymarket CTF Exchange contract on Polygon
CTF_EXCHANGE = Web3.to_checksum_address('0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E')

# Condition Token Framework (CTF) contract - this is where redemption happens
CTF_CONTRACT = Web3.to_checksum_address('0x4D97DCd97eC945f40cF65F87097ACe5EA0476045')

# The condition ID for Lakers vs Pistons
condition_id = '0x2442fd430fecccb337e64263589d16597d1a6098a3848cba9ff3bc382a1b16f9'

# Collateral token (USDC on Polygon)
USDC = Web3.to_checksum_address('0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174')

# CTF redeemPositions ABI
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

# Get nonce
nonce = w3.eth.get_transaction_count(account.address)
print(f"Nonce: {nonce}")

# Parent collection ID is zero for root positions
parent_collection_id = bytes(32)  # 32 zero bytes

# Index sets: [1, 2] means both outcomes (YES=1, NO=2)
# For a binary market where we hold one outcome, we use the index of our position
# Pistons was outcome index 1, so index set is 2 (2^1)
index_sets = [2]  # This represents the second outcome (index 1)

try:
    # Build transaction
    tx = contract.functions.redeemPositions(
        USDC,
        parent_collection_id,
        bytes.fromhex(condition_id[2:]),
        index_sets
    ).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'gas': 250000,
        'gasPrice': w3.to_wei(50, 'gwei'),
        'chainId': 137
    })
    
    print("Signing transaction...")
    signed = account.sign_transaction(tx)
    
    print("Sending to Polygon...")
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    
    print(f"\n✅ TX SENT!")
    print(f"Hash: {tx_hash.hex()}")
    print(f"View: https://polygonscan.com/tx/{tx_hash.hex()}")
    
    print("\nWaiting for confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f"Status: {'✅ SUCCESS' if receipt['status'] == 1 else '❌ FAILED'}")
    print(f"Gas used: {receipt['gasUsed']}")
    
except Exception as e:
    print(f"\n❌ Error: {type(e).__name__}: {e}")
