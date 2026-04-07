#!/usr/bin/env python3
"""Send MATIC for gas"""
from web3 import Web3
from eth_account import Account

w3 = Web3(Web3.HTTPProvider('https://rpc-mainnet.matic.quiknode.pro', request_kwargs={'timeout': 30}))
print(f"Connected: {w3.is_connected()}")

PERSONAL_KEY = 'ddacdb3d5c7751e8a974a87c5bc704850f3fcb68b95e8bba29fe85d435709784'
TRADING_WALLET = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'

account = Account.from_key(PERSONAL_KEY)
personal = account.address

# Send 0.5 MATIC (enough for many trades)
amount = w3.to_wei(0.5, 'ether')
gas_price = w3.eth.gas_price

print(f"Sending 0.5 MATIC to trading bot...")

nonce = w3.eth.get_transaction_count(personal)
tx = {
    'nonce': nonce,
    'to': TRADING_WALLET,
    'value': amount,
    'gas': 21000,
    'gasPrice': gas_price,
    'chainId': 137
}

signed = w3.eth.account.sign_transaction(tx, PERSONAL_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f"TX: {tx_hash.hex()}")

print("Waiting for confirmation...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

if receipt['status'] == 1:
    new_bal = w3.eth.get_balance(TRADING_WALLET)
    print(f"\n[OK] SUCCESS! Trading bot now has {float(w3.from_wei(new_bal, 'ether')):.4f} MATIC")
    print("[LAUNCH] READY TO TRADE!")
else:
    print("[FAIL] Failed")
