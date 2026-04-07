#!/usr/bin/env python3
"""Send USDC from personal wallet to trading wallet"""
from web3 import Web3
from eth_account import Account
import json

# Polygon RPC
RPCS = [
    'https://rpc-mainnet.matic.quiknode.pro',
    'https://polygon.llamarpc.com',
    'https://1rpc.io/matic',
]

# Connect
w3 = None
for rpc in RPCS:
    try:
        test_w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 15}))
        if test_w3.is_connected():
            w3 = test_w3
            print(f"Connected via: {rpc}")
            break
    except Exception as e:  # H12 FIX: Log RPC failures
        print(f"RPC {rpc} failed: {e}")
        continue

if not w3:
    print("Could not connect to Polygon")
    exit(1)

# Wallets
PERSONAL_KEY = 'ddacdb3d5c7751e8a974a87c5bc704850f3fcb68b95e8bba29fe85d435709784'
TRADING_WALLET = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'

# USDC on Polygon (native)
USDC_ADDRESS = '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359'

# ERC20 ABI for transfer
ERC20_ABI = [
    {'constant': True, 'inputs': [{'name': '_owner', 'type': 'address'}], 'name': 'balanceOf', 'outputs': [{'name': 'balance', 'type': 'uint256'}], 'type': 'function'},
    {'constant': False, 'inputs': [{'name': '_to', 'type': 'address'}, {'name': '_value', 'type': 'uint256'}], 'name': 'transfer', 'outputs': [{'name': '', 'type': 'bool'}], 'type': 'function'},
    {'constant': True, 'inputs': [], 'name': 'decimals', 'outputs': [{'name': '', 'type': 'uint8'}], 'type': 'function'}
]

# Get account from private key
account = Account.from_key(PERSONAL_KEY)
personal_address = account.address
print(f"Personal wallet: {personal_address}")
print(f"Trading wallet: {TRADING_WALLET}")

# Check balances
matic_balance = w3.eth.get_balance(personal_address)
print(f"\nMATIC for gas: {w3.from_wei(matic_balance, 'ether'):.6f}")

usdc_contract = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=ERC20_ABI)
usdc_balance = usdc_contract.functions.balanceOf(personal_address).call()
usdc_amount = usdc_balance / 1e6
print(f"USDC balance: ${usdc_amount:.2f}")

if usdc_balance == 0:
    print("\n[FAIL] No USDC to send!")
    # Check USDC.e (bridged version)
    USDCE_ADDRESS = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
    usdce_contract = w3.eth.contract(address=Web3.to_checksum_address(USDCE_ADDRESS), abi=ERC20_ABI)
    usdce_balance = usdce_contract.functions.balanceOf(personal_address).call()
    if usdce_balance > 0:
        print(f"Found USDC.e (bridged): ${usdce_balance/1e6:.2f}")
        usdc_contract = usdce_contract
        usdc_balance = usdce_balance
        USDC_ADDRESS = USDCE_ADDRESS
    else:
        exit(1)

if matic_balance < w3.to_wei(0.001, 'ether'):
    print("\n[FAIL] Not enough MATIC for gas!")
    exit(1)

# Send USDC
print(f"\n[LAUNCH] Sending ${usdc_balance/1e6:.2f} USDC to trading wallet...")

# Build transaction
nonce = w3.eth.get_transaction_count(personal_address)
# Use lower gas price to fit in budget
gas_price = int(w3.eth.gas_price * 0.8)  # 80% of suggested
max_gas = 65000  # USDC transfers typically need ~50k

# Calculate max affordable gas price
available_matic = matic_balance - w3.to_wei(0.001, 'ether')  # Keep small buffer
max_gas_price = available_matic // max_gas
gas_price = min(gas_price, max_gas_price)

print(f"Gas price: {w3.from_wei(gas_price, 'gwei'):.2f} gwei")

tx = usdc_contract.functions.transfer(
    Web3.to_checksum_address(TRADING_WALLET),
    usdc_balance
).build_transaction({
    'from': personal_address,
    'nonce': nonce,
    'gas': max_gas,
    'gasPrice': gas_price,
    'chainId': 137
})

# Sign and send
signed_tx = w3.eth.account.sign_transaction(tx, PERSONAL_KEY)
tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
print(f"Transaction sent: {tx_hash.hex()}")

# Wait for confirmation
print("Waiting for confirmation...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

if receipt['status'] == 1:
    print(f"\n[OK] SUCCESS! ${usdc_balance/1e6:.2f} USDC sent to trading wallet!")
    print(f"TX: https://polygonscan.com/tx/{tx_hash.hex()}")
else:
    print(f"\n[FAIL] Transaction failed!")
    print(receipt)
