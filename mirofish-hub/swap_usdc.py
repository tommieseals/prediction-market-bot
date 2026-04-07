import os
#!/usr/bin/env python3
"""Swap native USDC to USDC.e on Polygon via QuickSwap"""

from web3 import Web3
import json

# Config
PRIVATE_KEY = os.getenv("POLY_PRIVATE_KEY", "")
RPC_URL = "https://rpc-mainnet.matic.quiknode.pro"
WALLET = "0x299aCc0857B943d8490ECb1820fD458B3B58c728"

# Token addresses on Polygon
USDC_NATIVE = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # Native USDC
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"      # USDC.e (bridged)

# QuickSwap V3 Router
QUICKSWAP_ROUTER = "0xf5b509bB0909a69B1c207E495f687a596C168E12"

# ERC20 ABI for approve and balanceOf
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}
]

# QuickSwap Router ABI (simplified for exactInputSingle)
ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "tokenIn", "type": "address"},
                    {"name": "tokenOut", "type": "address"},
                    {"name": "recipient", "type": "address"},
                    {"name": "deadline", "type": "uint256"},
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "amountOutMinimum", "type": "uint256"},
                    {"name": "limitSqrtPrice", "type": "uint160"}
                ],
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "exactInputSingle",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    }
]

def main():
    print("=== USDC SWAP ===")
    
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    # Polygon is a POA chain - inject middleware
    from web3.middleware import ExtraDataToPOAMiddleware
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    
    print(f"Connected: {w3.is_connected()}")
    
    account = w3.eth.account.from_key(PRIVATE_KEY)
    
    # Check native USDC balance
    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_NATIVE), abi=ERC20_ABI)
    balance = usdc.functions.balanceOf(WALLET).call()
    decimals = usdc.functions.decimals().call()
    balance_human = balance / (10 ** decimals)
    
    print(f"Native USDC balance: ${balance_human:.2f}")
    
    if balance_human < 1:
        print("Not enough USDC to swap")
        return
    
    # Swap amount (leave a little buffer)
    swap_amount = int(balance * 0.95)  # 95% of balance
    swap_human = swap_amount / (10 ** decimals)
    print(f"Swapping: ${swap_human:.2f} USDC -> USDC.e")
    
    # Step 1: Approve router to spend USDC
    print("\n[1] Approving router...")
    allowance = usdc.functions.allowance(WALLET, QUICKSWAP_ROUTER).call()
    
    if allowance < swap_amount:
        approve_tx = usdc.functions.approve(
            Web3.to_checksum_address(QUICKSWAP_ROUTER),
            2**256 - 1  # Max approval
        ).build_transaction({
            'from': WALLET,
            'gas': 100000,
            'gasPrice': w3.eth.gas_price,
            'nonce': w3.eth.get_transaction_count(WALLET)
        })
        
        signed = account.sign_transaction(approve_tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Approve TX: {tx_hash.hex()}")
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print(f"Approve confirmed: {receipt['status'] == 1}")
    else:
        print("Already approved")
    
    # Step 2: Swap via router
    print("\n[2] Executing swap...")
    router = w3.eth.contract(address=Web3.to_checksum_address(QUICKSWAP_ROUTER), abi=ROUTER_ABI)
    
    deadline = w3.eth.get_block('latest')['timestamp'] + 300  # 5 min
    
    swap_params = {
        'tokenIn': Web3.to_checksum_address(USDC_NATIVE),
        'tokenOut': Web3.to_checksum_address(USDC_E),
        'recipient': Web3.to_checksum_address(WALLET),
        'deadline': deadline,
        'amountIn': swap_amount,
        'amountOutMinimum': int(swap_amount * 0.99),  # 1% slippage
        'limitSqrtPrice': 0
    }
    
    swap_tx = router.functions.exactInputSingle(swap_params).build_transaction({
        'from': WALLET,
        'gas': 300000,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(WALLET),
        'value': 0
    })
    
    signed = account.sign_transaction(swap_tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Swap TX: {tx_hash.hex()}")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f"Swap confirmed: {receipt['status'] == 1}")
    
    # Check new balance
    usdc_e = w3.eth.contract(address=Web3.to_checksum_address(USDC_E), abi=ERC20_ABI)
    new_balance = usdc_e.functions.balanceOf(WALLET).call()
    new_balance_human = new_balance / (10 ** 6)  # USDC.e is 6 decimals
    print(f"\nNew USDC.e balance: ${new_balance_human:.2f}")
    
    print("\n=== SWAP COMPLETE ===")

if __name__ == "__main__":
    main()
