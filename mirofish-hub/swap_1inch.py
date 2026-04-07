import os
#!/usr/bin/env python3
"""Swap USDC to USDC.e using 1inch API"""

import requests
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

PRIVATE_KEY = os.getenv("POLY_PRIVATE_KEY", "")
RPC_URL = "https://rpc-mainnet.matic.quiknode.pro"
WALLET = "0x299aCc0857B943d8490ECb1820fD458B3B58c728"

USDC_NATIVE = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

ONEINCH_ROUTER = "0x111111125421cA6dc452d289314280a0f8842A65"

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}
]

def main():
    print("=== 1INCH SWAP ===")
    
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    print(f"Connected: {w3.is_connected()}")
    
    account = w3.eth.account.from_key(PRIVATE_KEY)
    
    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_NATIVE), abi=ERC20_ABI)
    balance = usdc.functions.balanceOf(WALLET).call()
    decimals = usdc.functions.decimals().call()
    balance_human = balance / (10 ** decimals)
    
    print(f"Native USDC: ${balance_human:.2f}")
    
    # Swap 95%
    swap_amount = int(balance * 0.95)
    swap_human = swap_amount / (10 ** decimals)
    print(f"Swapping: ${swap_human:.2f}")
    
    # Approve 1inch router
    print("\n[1] Checking approval...")
    allowance = usdc.functions.allowance(WALLET, ONEINCH_ROUTER).call()
    
    if allowance < swap_amount:
        print("Approving 1inch router...")
        approve_tx = usdc.functions.approve(
            Web3.to_checksum_address(ONEINCH_ROUTER),
            2**256 - 1
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
        print(f"Approved: {receipt['status'] == 1}")
    else:
        print("Already approved")
    
    # Get swap quote from 1inch
    print("\n[2] Getting swap quote...")
    quote_url = f"https://api.1inch.dev/swap/v6.0/137/swap"
    params = {
        "src": USDC_NATIVE,
        "dst": USDC_E,
        "amount": str(swap_amount),
        "from": WALLET,
        "slippage": 1,
        "disableEstimate": "true"
    }
    headers = {
        "Authorization": "Bearer YOUR_1INCH_API_KEY"  # Need API key
    }
    
    # Try without API key (might work for quotes)
    quote_url_free = f"https://api.1inch.io/v5.2/137/swap"
    resp = requests.get(quote_url_free, params=params, timeout=30)
    
    if resp.status_code != 200:
        print(f"1inch API error: {resp.status_code} - {resp.text[:200]}")
        print("\n1inch requires API key now. Trying Paraswap...")
        
        # Try Paraswap instead
        paraswap_url = "https://apiv5.paraswap.io/transactions/137"
        paraswap_params = {
            "srcToken": USDC_NATIVE,
            "destToken": USDC_E,
            "srcAmount": str(swap_amount),
            "userAddress": WALLET,
            "side": "SELL",
            "network": 137,
            "slippage": 100,  # 1%
            "srcDecimals": 6,
            "destDecimals": 6
        }
        
        # First get price
        price_url = "https://apiv5.paraswap.io/prices"
        price_resp = requests.get(price_url, params=paraswap_params, timeout=30)
        
        if price_resp.status_code == 200:
            price_data = price_resp.json()
            print(f"Paraswap quote: {price_data.get('priceRoute', {}).get('destAmount', 'N/A')}")
            
            # Build transaction
            tx_params = {
                "srcToken": USDC_NATIVE,
                "destToken": USDC_E,
                "srcAmount": str(swap_amount),
                "destAmount": price_data['priceRoute']['destAmount'],
                "priceRoute": price_data['priceRoute'],
                "userAddress": WALLET,
                "slippage": 100
            }
            
            tx_resp = requests.post(paraswap_url, json=tx_params, timeout=30)
            if tx_resp.status_code == 200:
                tx_data = tx_resp.json()
                print(f"Got swap TX data")
                
                # Execute
                swap_tx = {
                    'from': WALLET,
                    'to': Web3.to_checksum_address(tx_data['to']),
                    'data': tx_data['data'],
                    'value': int(tx_data.get('value', 0)),
                    'gas': int(tx_data['gas']),
                    'gasPrice': w3.eth.gas_price,
                    'nonce': w3.eth.get_transaction_count(WALLET),
                    'chainId': 137
                }
                
                signed = account.sign_transaction(swap_tx)
                tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
                print(f"Swap TX: {tx_hash.hex()}")
                
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                print(f"Swap success: {receipt['status'] == 1}")
            else:
                print(f"Paraswap TX error: {tx_resp.text[:200]}")
        else:
            print(f"Paraswap price error: {price_resp.text[:200]}")
        
        return
    
    swap_data = resp.json()
    print(f"Quote received: {swap_data.get('toAmount', 'N/A')}")
    
    # Execute swap
    print("\n[3] Executing swap...")
    swap_tx = {
        'from': WALLET,
        'to': Web3.to_checksum_address(swap_data['tx']['to']),
        'data': swap_data['tx']['data'],
        'value': int(swap_data['tx']['value']),
        'gas': int(swap_data['tx']['gas']),
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(WALLET)
    }
    
    signed = account.sign_transaction(swap_tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Swap TX: {tx_hash.hex()}")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f"Swap confirmed: {receipt['status'] == 1}")
    
    # Check new balance
    usdc_e = w3.eth.contract(address=Web3.to_checksum_address(USDC_E), abi=ERC20_ABI)
    new_balance = usdc_e.functions.balanceOf(WALLET).call() / 1e6
    print(f"\nNew USDC.e balance: ${new_balance:.2f}")

if __name__ == "__main__":
    main()
