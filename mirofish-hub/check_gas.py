#!/usr/bin/env python3
from web3 import Web3

w3 = Web3(Web3.HTTPProvider('https://rpc-mainnet.matic.quiknode.pro'))
trading_wallet = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'
personal_wallet = '0xA85b285c265F7748e10DdB30f7643dCA3aa08D4b'

trading_matic = w3.eth.get_balance(trading_wallet)
personal_matic = w3.eth.get_balance(personal_wallet)

print(f"Trading Bot MATIC: {float(w3.from_wei(trading_matic, 'ether')):.6f}")
print(f"Personal MATIC: {float(w3.from_wei(personal_matic, 'ether')):.6f}")

if trading_matic < w3.to_wei(0.001, 'ether'):
    print("\n[WARN]  Trading bot needs MATIC for gas!")
    if personal_matic > w3.to_wei(0.002, 'ether'):
        print("[OK] Can transfer from personal wallet")
    else:
        print("[FAIL] Both wallets low on MATIC")
else:
    print("\n[OK] Ready to trade - enough MATIC for gas")
