#!/usr/bin/env python3
"""Send USDC - simple version"""
from web3 import Web3
from eth_account import Account

# Connect to Polygon
w3 = Web3(Web3.HTTPProvider('https://rpc-mainnet.matic.quiknode.pro', request_kwargs={'timeout': 30}))
print(f"Connected: {w3.is_connected()}")

# Keys
PERSONAL_KEY = 'ddacdb3d5c7751e8a974a87c5bc704850f3fcb68b95e8bba29fe85d435709784'
TRADING_WALLET = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'

# USDC contracts (try both)
USDC_NATIVE = '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359'
USDC_BRIDGED = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'

ERC20_ABI = [
    {'constant': True, 'inputs': [{'name': '_owner', 'type': 'address'}], 'name': 'balanceOf', 'outputs': [{'name': 'balance', 'type': 'uint256'}], 'type': 'function'},
    {'constant': False, 'inputs': [{'name': '_to', 'type': 'address'}, {'name': '_value', 'type': 'uint256'}], 'name': 'transfer', 'outputs': [{'name': '', 'type': 'bool'}], 'type': 'function'},
]

# Get account
account = Account.from_key(PERSONAL_KEY)
addr = account.address
print(f"From: {addr}")
print(f"To: {TRADING_WALLET}")

# Check MATIC
matic = w3.eth.get_balance(addr)
print(f"MATIC: {float(w3.from_wei(matic, 'ether')):.6f}")

# Find USDC
usdc_addr = None
usdc_bal = 0

for token_addr in [USDC_NATIVE, USDC_BRIDGED]:
    contract = w3.eth.contract(address=Web3.to_checksum_address(token_addr), abi=ERC20_ABI)
    bal = contract.functions.balanceOf(addr).call()
    if bal > 0:
        usdc_addr = token_addr
        usdc_bal = bal
        print(f"Found USDC at {token_addr}: ${bal/1e6:.2f}")
        break

if not usdc_addr:
    print("No USDC found!")
    exit(1)

# Build and send
contract = w3.eth.contract(address=Web3.to_checksum_address(usdc_addr), abi=ERC20_ABI)
nonce = w3.eth.get_transaction_count(addr)

# Estimate gas properly
gas_estimate = contract.functions.transfer(
    Web3.to_checksum_address(TRADING_WALLET),
    usdc_bal
).estimate_gas({'from': addr})

gas_price = w3.eth.gas_price
total_gas_cost = gas_estimate * gas_price

print(f"Gas estimate: {gas_estimate}")
print(f"Gas price: {w3.from_wei(gas_price, 'gwei'):.2f} gwei")
print(f"Total gas cost: {w3.from_wei(total_gas_cost, 'ether'):.6f} MATIC")

if total_gas_cost > matic:
    print("Not enough MATIC for gas! Need more POL/MATIC")
    exit(1)

tx = contract.functions.transfer(
    Web3.to_checksum_address(TRADING_WALLET),
    usdc_bal
).build_transaction({
    'from': addr,
    'nonce': nonce,
    'gas': gas_estimate + 10000,
    'gasPrice': gas_price,
    'chainId': 137
})

print(f"\nSending ${usdc_bal/1e6:.2f} USDC...")
signed = w3.eth.account.sign_transaction(tx, PERSONAL_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f"TX Hash: {tx_hash.hex()}")

print("Waiting for confirmation...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

if receipt['status'] == 1:
    print(f"\n[OK] SUCCESS!")
    print(f"https://polygonscan.com/tx/{tx_hash.hex()}")
else:
    print(f"\n[FAIL] Failed!")
