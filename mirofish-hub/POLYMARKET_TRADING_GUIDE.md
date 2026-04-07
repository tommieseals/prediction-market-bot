# 🎯 Polymarket Trading Setup Guide

## Quick Start

### 1. Generate a Wallet
```bash
python polymarket_trader.py --new-wallet
```
This creates a fresh Ethereum wallet. **SAVE THE PRIVATE KEY!**

### 2. Configure Environment
```bash
cp .env.polymarket .env
# Edit .env with your private key and proxy
```

### 3. Fund Your Wallet
- Send USDC to your wallet address on **Polygon network**
- Minimum: ~$10 for testing
- Bridge from Ethereum: https://wallet.polygon.technology/

### 4. Test Connection
```bash
python polymarket_trader.py --balance
```

---

## 📡 API Flow (How Trading Works)

### Step 1: Authentication
```
Wallet Private Key → Sign Message → Get API Key → L2 Headers
```

The py-clob-client handles this automatically:
```python
client.set_api_creds(client.create_or_derive_api_creds())
```

### Step 2: Find a Market
```bash
python polymarket_trader.py --markets "trump"
```

Returns:
- `conditionId` - Market identifier
- `clobTokenIds[0]` - YES token ID
- `clobTokenIds[1]` - NO token ID

### Step 3: Check Price/Orderbook
```bash
python polymarket_trader.py --price TOKEN_ID
python polymarket_trader.py --book TOKEN_ID
```

### Step 4: Place Order
```bash
# Buy 10 YES shares at $0.55
python polymarket_trader.py --buy TOKEN_ID 0.55 10

# Sell 5 NO shares at $0.40
python polymarket_trader.py --sell TOKEN_ID 0.40 5
```

### Step 5: Manage Orders
```bash
python polymarket_trader.py --orders    # List open orders
python polymarket_trader.py --cancel ORDER_ID
```

---

## 🌐 Proxy Setup (For US Access)

### Option 1: Webshare Residential
```
Provider: webshare.io
Cost: ~$5/month for 1GB
Format: http://USER:PASS@p.webshare.io:80
Features: Sticky sessions, residential IPs
```

### Option 2: VPN + Proxy Chain
```bash
# Connect VPN to UK/Canada first
# Then use local SOCKS proxy if needed
POLY_PROXY=socks5://127.0.0.1:1080
```

### Option 3: Residential Proxy Services
- BrightData (expensive but reliable)
- Oxylabs
- SmartProxy

---

## 🔧 Full Python API Example

```python
from py_clob_client.client import ClobClient
from py_clob_client.order_builder.constants import BUY, SELL

# Initialize
client = ClobClient(
    host="https://clob.polymarket.com",
    key="YOUR_PRIVATE_KEY",
    chain_id=137,  # Polygon
)

# Get API credentials
client.set_api_creds(client.create_or_derive_api_creds())

# Check balance
balance = client.get_balance_allowance()
print(f"USDC: ${balance['balance']}")

# Get market info
# Use Gamma API to find token IDs first

# Place a BUY order
order = client.create_and_post_order(
    token_id="12345...",  # YES or NO token ID
    side=BUY,
    price=0.55,           # $0.55 per share
    size=100,             # 100 shares = $55 risk
)
print(f"Order ID: {order['orderID']}")

# Check order status
orders = client.get_orders()

# Cancel order
client.cancel(order['orderID'])
```

---

## 📊 Token ID Lookup

Markets have two tokens:
- **YES Token** - Pays $1 if outcome is YES
- **NO Token** - Pays $1 if outcome is NO

To find token IDs:
```python
import requests

resp = requests.get(
    "https://gamma-api.polymarket.com/markets",
    params={"query": "trump", "active": "true"}
)
market = resp.json()[0]

yes_token = market["clobTokenIds"][0]
no_token = market["clobTokenIds"][1]
```

---

## ⚠️ Important Notes

1. **No KYC for trading** - Only needed for fiat withdrawals
2. **Gas fees** - Polygon is cheap (~$0.01 per tx)
3. **Slippage** - Use limit orders, not market orders
4. **US Access** - Use VPN/proxy, fresh wallet recommended
5. **Allowance** - First trade may need USDC approval tx

---

## 🔗 Resources

- Polymarket CLOB Docs: https://docs.polymarket.com/
- py-clob-client: https://github.com/Polymarket/py-clob-client
- Gamma API: https://gamma-api.polymarket.com
- Polygon Bridge: https://wallet.polygon.technology/

---

## 🚀 Integration with Whale Tracker

Once trading is set up, we can:
1. **Auto-follow** whales with good tracked records
2. **Auto-fade** whales with poor tracked records (like wooter)
3. **Copy trades** in real-time when new positions detected

```python
# In whale_hunter_connector.py
if signal_direction == "FOLLOW":
    trader.place_order(token_id, "BUY", price, kelly_size)
elif signal_direction == "FADE":
    # Opposite side
    trader.place_order(opposite_token, "BUY", 1-price, kelly_size)
```
