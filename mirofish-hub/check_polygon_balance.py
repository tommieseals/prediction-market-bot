#!/usr/bin/env python3
"""Check wallet balance directly on Polygon"""
from web3 import Web3
import json

# Polygon RPC - try multiple public endpoints
RPCS = [
    'https://rpc-mainnet.matic.quiknode.pro',
    'https://polygon.llamarpc.com',
    'https://1rpc.io/matic',
]

w3 = None
for rpc in RPCS:
    try:
        test_w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 10}))
        if test_w3.is_connected():
            w3 = test_w3
            print(f"Connected via: {rpc}")
            break
    except Exception as e:  # H12 FIX: Log RPC connection failures
        print(f"RPC {rpc} failed: {e}")
        continue

if not w3:
    print("Could not connect to any RPC")
    exit(1)

# Wallet address
WALLET = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'

# USDC contract on Polygon (native USDC)
USDC_ADDRESS = '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359'

# USDC.e (bridged) on Polygon  
USDCE_ADDRESS = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'

# Minimal ERC20 ABI for balanceOf
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

print(f"Checking wallet: {WALLET}")
print(f"Connected to Polygon: {w3.is_connected()}")
print()

# Check MATIC balance
matic_balance = w3.eth.get_balance(WALLET)
print(f"MATIC: {w3.from_wei(matic_balance, 'ether'):.6f}")

# Check native USDC
try:
    usdc_contract = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=ERC20_ABI)
    usdc_balance = usdc_contract.functions.balanceOf(Web3.to_checksum_address(WALLET)).call()
    print(f"USDC (native): ${usdc_balance / 1e6:.2f}")
except Exception as e:
    print(f"USDC check error: {e}")

# Check USDC.e (bridged)
try:
    usdce_contract = w3.eth.contract(address=Web3.to_checksum_address(USDCE_ADDRESS), abi=ERC20_ABI)
    usdce_balance = usdce_contract.functions.balanceOf(Web3.to_checksum_address(WALLET)).call()
    print(f"USDC.e (bridged): ${usdce_balance / 1e6:.2f}")
except Exception as e:
    print(f"USDC.e check error: {e}")

print()
total_usdc = (usdc_balance + usdce_balance) / 1e6 if 'usdce_balance' in dir() else usdc_balance / 1e6
if total_usdc > 0:
    print(f"[OK] Total USDC: ${total_usdc:.2f} - READY TO TRADE!")
else:
    print("[FAIL] No USDC found in this wallet")
    print("\nTo fund the wallet:")
    print("1. Send USDC to this address on Polygon network")
    print("2. Or bridge from Ethereum: https://wallet.polygon.technology/")
