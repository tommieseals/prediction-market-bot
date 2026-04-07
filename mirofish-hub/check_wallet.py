from web3 import Web3

rpcs = [
    'https://polygon.llamarpc.com',
    'https://rpc-mainnet.maticvigil.com',
]

wallet = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'
usdc_address = '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359'
usdc_abi = [{'constant':True,'inputs':[{'name':'_owner','type':'address'}],'name':'balanceOf','outputs':[{'name':'balance','type':'uint256'}],'type':'function'}]

for rpc in rpcs:
    try:
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 10}))
        if w3.is_connected():
            usdc = w3.eth.contract(address=Web3.to_checksum_address(usdc_address), abi=usdc_abi)
            balance = usdc.functions.balanceOf(Web3.to_checksum_address(wallet)).call()
            usdc_balance = balance / 10**6
            matic = w3.eth.get_balance(Web3.to_checksum_address(wallet)) / 10**18
            print(f"Trading Wallet Balance:")
            print(f"  USDC: ${usdc_balance:.2f}")
            print(f"  MATIC: {matic:.4f} (gas)")
            break
    except Exception as e:
        print(f"RPC {rpc} failed: {e}")
