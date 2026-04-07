# Polymarket Position Redemption - Complete Workflow

**Last Updated:** 2026-03-24
**Status:** WORKING ✅

## Quick Reference

### Check Wallet Balance
```powershell
cd C:\Users\USER\clawd\mirofish-hub
python check_polygon_balance.py
```

### Check Redeemable Positions
```powershell
python -c "import requests; r=requests.get('https://data-api.polymarket.com/positions?user=0x299aCc0857B943d8490ECb1820fD458B3B58c728'); [print(p.get('title'), '- $'+str(p.get('currentValue',0)), '- redeemable:', p.get('redeemable')) for p in r.json()]"
```

### Redeem a Position
```powershell
python do_redeem.py
```

---

## Full Technical Details

### Wallet Info
| Item | Value |
|------|-------|
| **Address** | `0x299aCc0857B943d8490ECb1820fD458B3B58c728` |
| **Private Key** | See `vault/polymarket_wallets.md` |
| **Network** | Polygon (Chain ID: 137) |
| **RPC** | `https://rpc-mainnet.matic.quiknode.pro` |

### Key Contracts (Polygon)
| Contract | Address |
|----------|---------|
| **CTF (Gnosis)** | `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` |
| **USDC.e** | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` |
| **NegRiskAdapter** | `0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296` |
| **NegRiskCtfExchange** | `0xC5d563A36AE78145C45a50134d48A1215220f80a` |

### Redemption Process

#### Step 1: Get Position Info
```python
import requests
wallet = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'
r = requests.get(f'https://data-api.polymarket.com/positions?user={wallet}')
positions = r.json()

for p in positions:
    if p.get('redeemable'):
        print(f"Market: {p['title']}")
        print(f"Condition ID: {p['conditionId']}")
        print(f"Outcome Index: {p['outcomeIndex']}")
        print(f"Value: ${p['currentValue']}")
```

#### Step 2: Calculate Index Set
For binary markets:
- Outcome index 0 → indexSet = 1 (2^0)
- Outcome index 1 → indexSet = 2 (2^1)

#### Step 3: Check for Stuck Transactions
```python
from web3 import Web3
w3 = Web3(Web3.HTTPProvider('https://rpc-mainnet.matic.quiknode.pro'))
wallet = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'

pending = w3.eth.get_transaction_count(wallet, 'pending')
confirmed = w3.eth.get_transaction_count(wallet, 'latest')

if pending > confirmed:
    print(f"WARNING: {pending - confirmed} stuck transactions!")
    print("Run cancel_tx.py first")
```

#### Step 4: Cancel Stuck TX (if needed)
```python
# cancel_tx.py
from web3 import Web3

pk = 'YOUR_PRIVATE_KEY'
w3 = Web3(Web3.HTTPProvider('https://rpc-mainnet.matic.quiknode.pro'))
account = w3.eth.account.from_key(pk)

stuck_nonce = w3.eth.get_transaction_count(account.address, 'latest')

tx = {
    'from': account.address,
    'to': account.address,
    'value': 0,
    'nonce': stuck_nonce,
    'gas': 21000,
    'maxFeePerGas': w3.to_wei(300, 'gwei'),  # High gas to replace
    'maxPriorityFeePerGas': w3.to_wei(150, 'gwei'),
    'chainId': 137
}
signed = account.sign_transaction(tx)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
```

#### Step 5: Execute Redemption
```python
# do_redeem.py
from web3 import Web3

pk = 'YOUR_PRIVATE_KEY'
w3 = Web3(Web3.HTTPProvider('https://rpc-mainnet.matic.quiknode.pro'))
account = w3.eth.account.from_key(pk)

CTF = Web3.to_checksum_address('0x4D97DCd97eC945f40cF65F87097ACe5EA0476045')
USDC_E = Web3.to_checksum_address('0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174')

# Get these from position data
condition_id = bytes.fromhex('YOUR_CONDITION_ID_WITHOUT_0x')
index_sets = [2]  # Adjust based on outcomeIndex

CTF_ABI = [{
    "inputs": [
        {"name": "collateralToken", "type": "address"},
        {"name": "parentCollectionId", "type": "bytes32"},
        {"name": "conditionId", "type": "bytes32"},
        {"name": "indexSets", "type": "uint256[]"}
    ],
    "name": "redeemPositions",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
}]

contract = w3.eth.contract(address=CTF, abi=CTF_ABI)
nonce = w3.eth.get_transaction_count(account.address, 'latest')

tx = contract.functions.redeemPositions(
    USDC_E,
    bytes(32),  # parent collection (zeros for root)
    condition_id,
    index_sets
).build_transaction({
    'from': account.address,
    'nonce': nonce,
    'gas': 300000,
    'maxFeePerGas': w3.to_wei(150, 'gwei'),
    'maxPriorityFeePerGas': w3.to_wei(50, 'gwei'),
    'chainId': 137
})

signed = account.sign_transaction(tx)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
```

---

## Troubleshooting

### "replacement transaction underpriced"
There's a stuck TX in the mempool. Run `cancel_tx.py` with high gas to clear it.

### Position still shows redeemable after TX
- Check the TX status on Polygonscan
- Verify you used the correct conditionId
- Verify the indexSet matches your outcomeIndex

### Web3 connection issues
- QuickNode RPC is reliable: `https://rpc-mainnet.matic.quiknode.pro`
- Avoid `https://polygon-rpc.com` (often 401 errors)

---

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `check_polygon_balance.py` | Check wallet USDC/MATIC balance |
| `cancel_tx.py` | Cancel stuck transactions |
| `do_redeem.py` | Execute position redemption |
| `polymarket_trader.py` | Place trades |

---

## First Successful Redemption
- **Date:** 2026-03-24
- **Market:** Lakers vs Pistons
- **Position:** Pistons (won)
- **Redeemed:** $25.00
- **TX:** `b590b629bf3bd75fc862e7c21d13502fd3a796f6f5a9532bfa5175cfe9f535c6`
