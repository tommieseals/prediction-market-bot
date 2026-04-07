from web3 import Web3

pk = '39f1a59fe9c2c006ac51e1edad69be0a0133df21c053e91f34387ba9cc9f30ae'
w3 = Web3(Web3.HTTPProvider('https://rpc-mainnet.matic.quiknode.pro'))
account = w3.eth.account.from_key(pk)
print(f'Wallet: {account.address}')

# Cancel stuck tx at nonce 12
tx = {
    'from': account.address,
    'to': account.address,
    'value': 0,
    'nonce': 12,
    'gas': 21000,
    'maxFeePerGas': w3.to_wei(300, 'gwei'),
    'maxPriorityFeePerGas': w3.to_wei(150, 'gwei'),
    'chainId': 137
}
signed = account.sign_transaction(tx)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f'Cancel TX sent: {tx_hash.hex()}')
print('Waiting for confirmation...')
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
status = receipt.get('status', 0)
print(f'Status: {status} (1=success)')
print(f'Gas used: {receipt.get("gasUsed", 0)}')
