import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType

# Market details from our consensus pick
TOKEN_ID = "53672610104884801589662124213210078919813716584355622362595283011438952484973"
CONDITION_ID = "0xf819e1271eb99985143505bd2ad3ca397515a37e741e66b411e954c8ef14ab97"

# Trading wallet
PRIVATE_KEY = "39f1a59fe9c2c006ac51e1edad69be0a0133df21c053e91f34387ba9cc9f30ae"

# Get current market prices
print("=== Getting current prices ===")
r = requests.get(f'https://clob.polymarket.com/book?token_id={TOKEN_ID}')
book = r.json()

if 'bids' in book and book['bids']:
    # Bids are sorted ascending, get the highest bid
    bids_sorted = sorted(book['bids'], key=lambda x: float(x['price']), reverse=True)
    best_bid = float(bids_sorted[0]['price'])
    print(f"Best Bid: ${best_bid}")
else:
    best_bid = 0.48

if 'asks' in book and book['asks']:
    # Asks are sorted descending, get the lowest ask
    asks_sorted = sorted(book['asks'], key=lambda x: float(x['price']))
    best_ask = float(asks_sorted[0]['price'])
    print(f"Best Ask: ${best_ask}")
else:
    best_ask = 0.52

print(f"Spread: ${best_ask - best_bid:.2f}")
print(f"Last trade: ${book.get('last_trade_price', 'N/A')}")

# Initialize trading client
host = "https://clob.polymarket.com"
chain_id = 137  # Polygon

client = ClobClient(
    host=host,
    key=PRIVATE_KEY,
    chain_id=chain_id,
    signature_type=2
)

# Set API credentials
client.set_api_creds(client.create_or_derive_api_creds())
print("\n[OK] API Connected")

# Trade parameters - buy at the ask to get filled immediately
TRADE_PRICE = best_ask  # Buy at best ask for immediate fill
TRADE_SIZE = 20  # $20 position

print(f"\n=== Placing Trade ===")
print(f"Market: Arkansas Razorbacks vs. Arizona Wildcats O/U 165.5")
print(f"Side: BUY NO (betting UNDER)")
print(f"Price: ${TRADE_PRICE}")
print(f"Size: ${TRADE_SIZE}")
print(f"Potential Win: ${TRADE_SIZE / TRADE_PRICE:.2f} if Under hits")

try:
    order_args = OrderArgs(
        token_id=TOKEN_ID,
        price=TRADE_PRICE,
        size=TRADE_SIZE,
        side="BUY"
    )
    
    signed_order = client.create_order(order_args)
    result = client.post_order(signed_order, OrderType.GTC)
    print(f"\n[SUCCESS] ORDER PLACED!")
    print(f"Result: {result}")
except Exception as e:
    print(f"\n[FAILED] Order failed: {e}")
    import traceback
    traceback.print_exc()
