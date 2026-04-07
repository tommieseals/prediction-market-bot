#!/usr/bin/env python3
"""Send MATIC from personal to trading wallet for gas"""
from web3 import Web3
from eth_account import Account

w3 = Web3(Web3.HTTPProvider('https://rpc-mainnet.matic.quiknode.pro', request_kwargs={'timeout': 30}))
print(f"Connected: {w3.is_connected()}")

PERSONAL_KEY = 'ddacdb3d5c7751e8a974a87c5bc704850f3fcb68b95e8bba29fe85d435709784'
TRADING_WALLET = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'

account = Account.from_key(PERSONAL_KEY)
personal = account.address

# Check balance
matic = w3.eth.get_balance(personal)
print(f"Personal MATIC: {float(w3.from_wei(matic, 'ether')):.6f}")

# Calculate how much we can send (keep enough for gas)
gas_price = w3.eth.gas_price
# Use 80% of market gas price to save
gas_price = int(gas_price * 0.8)
gas_limit = 21000
gas_cost = gas_price * gas_limit

print(f"Gas price: {w3.from_wei(gas_price, 'gwei'):.2f} gwei")
print(f"Transfer cost: {float(w3.from_wei(gas_cost, 'ether')):.6f} MATIC")

# Send most of what's left after gas (keep tiny buffer)
sendable = matic - int(gas_cost * 1.5)
if sendable <= 0:
    print("Not enough MATIC to send!")
    exit(1)

amount = sendable  # Send everything we can
print(f"Sending {float(w3.from_wei(amount, 'ether')):.6f} MATIC to trading bot...")

nonce = w3.eth.get_transaction_count(personal)
tx = {
    'nonce': nonce,
    'to': TRADING_WALLET,
    'value': amount,
    'gas': gas_limit,
    'gasPrice': gas_price,
    'chainId': 137
}

signed = w3.eth.account.sign_transaction(tx, PERSONAL_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f"TX: {tx_hash.hex()}")

receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
if receipt['status'] == 1:
    # Check new balance
    new_bal = w3.eth.get_balance(TRADING_WALLET)
    print(f"\n[OK] Done! Trading bot now has {float(w3.from_wei(new_bal, 'ether')):.6f} MATIC")
else:
    print("[FAIL] Failed")
