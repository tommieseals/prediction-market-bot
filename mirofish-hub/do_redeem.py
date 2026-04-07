from web3 import Web3

pk = '39f1a59fe9c2c006ac51e1edad69be0a0133df21c053e91f34387ba9cc9f30ae'
w3 = Web3(Web3.HTTPProvider('https://rpc-mainnet.matic.quiknode.pro'))
account = w3.eth.account.from_key(pk)
print(f'Wallet: {account.address}')

# Gnosis CTF Contract on Polygon
CTF = Web3.to_checksum_address('0x4D97DCd97eC945f40cF65F87097ACe5EA0476045')

# USDC.e (bridged) - Polymarket collateral
USDC_E = Web3.to_checksum_address('0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174')

# Condition ID for Lakers vs Pistons
condition_id = bytes.fromhex('2442fd430fecccb337e64263589d16597d1a6098a3848cba9ff3bc382a1b16f9')

# Parent collection (zero for root positions)
parent = bytes(32)

# Index set: we hold outcome index 1 (Pistons), so indexSet = 2^1 = 2
index_sets = [2]

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

nonce = w3.eth.get_transaction_count(account.address, 'latest')
print(f'Nonce: {nonce}')

print('Building redeem transaction...')
tx = contract.functions.redeemPositions(
    USDC_E,
    parent,
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

print('Signing...')
signed = account.sign_transaction(tx)

print('Sending to Polygon...')
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f'TX Hash: {tx_hash.hex()}')
print(f'https://polygonscan.com/tx/{tx_hash.hex()}')

print('Waiting for confirmation...')
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

status = receipt.get('status', 0)
if status == 1:
    print('\n*** SUCCESS! Position redeemed! ***')
else:
    print('\n*** FAILED - check polygonscan ***')
print(f'Gas used: {receipt.get("gasUsed", 0)}')
