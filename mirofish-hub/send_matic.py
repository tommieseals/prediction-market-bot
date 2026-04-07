#!/usr/bin/env python3
"""Send some MATIC for gas"""
from web3 import Web3
from eth_account import Account

w3 = Web3(Web3.HTTPProvider('https://rpc-mainnet.matic.quiknode.pro', request_kwargs={'timeout': 30}))
print(f"Connected: {w3.is_connected()}")

PERSONAL_KEY = 'ddacdb3d5c7751e8a974a87c5bc704850f3fcb68b95e8bba29fe85d435709784'
TRADING_WALLET = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'

account = Account.from_key(PERSONAL_KEY)
addr = account.address

# Check how much MATIC we have
matic = w3.eth.get_balance(addr)
print(f"Personal wallet MATIC: {float(w3.from_wei(matic, 'ether')):.6f}")

# Send half of remaining MATIC (keep some for gas)
amount_to_send = (matic - w3.to_wei(0.002, 'ether')) // 2  # Send ~half, keep rest for gas
gas_price = w3.eth.gas_price
gas_limit = 21000
gas_cost = gas_price * gas_limit

if matic < amount_to_send + gas_cost:
    print("Not enough MATIC to send!")
    exit(1)

nonce = w3.eth.get_transaction_count(addr)

tx = {
    'nonce': nonce,
    'to': TRADING_WALLET,
    'value': amount_to_send,
    'gas': gas_limit,
    'gasPrice': gas_price,
    'chainId': 137
}

print(f"Sending 0.002 MATIC to trading wallet...")
signed = w3.eth.account.sign_transaction(tx, PERSONAL_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f"TX: {tx_hash.hex()}")

receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
if receipt['status'] == 1:
    print("[OK] MATIC sent!")
else:
    print("[FAIL] Failed")
