#!/usr/bin/env python3
"""Check if USDC is on Ethereum mainnet"""
from web3 import Web3

ETH_RPCS = [
    'https://eth.llamarpc.com',
    'https://1rpc.io/eth',
    'https://cloudflare-eth.com',
]

WALLET = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'
USDC_ETH = '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'

ERC20_ABI = [{'constant': True, 'inputs': [{'name': '_owner', 'type': 'address'}], 'name': 'balanceOf', 'outputs': [{'name': 'balance', 'type': 'uint256'}], 'type': 'function'}]

print(f"Checking Ethereum mainnet for: {WALLET}\n")

for rpc in ETH_RPCS:
    try:
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 10}))
        if w3.is_connected():
            print(f"Connected via: {rpc}")
            
            # Check ETH balance
            eth_bal = w3.eth.get_balance(WALLET)
            eth_amount = float(w3.from_wei(eth_bal, 'ether'))
            print(f"ETH: {eth_amount:.6f}")
            
            # Check USDC
            usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_ETH), abi=ERC20_ABI)
            usdc_bal = usdc.functions.balanceOf(Web3.to_checksum_address(WALLET)).call()
            usdc_amount = usdc_bal / 1e6
            print(f"USDC (Ethereum): ${usdc_amount:.2f}")
            
            if usdc_amount > 0:
                print("\n[OK] USDC found on Ethereum!")
                print("To use on Polymarket, bridge to Polygon:")
                print("https://wallet.polygon.technology/")
            elif eth_amount == 0 and usdc_amount == 0:
                print("\n[FAIL] Wallet is empty on Ethereum too")
                print("Make sure you sent to the right address!")
            break
    except Exception as e:
        print(f"{rpc}: {e}")
        continue
