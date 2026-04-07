import os
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, ApiCreds
from py_clob_client.order_builder.constants import BUY

load_dotenv()

# Initialize client with API credentials
host = "https://clob.polymarket.com"
chain_id = 137  # Polygon
private_key = os.getenv('POLY_PRIVATE_KEY')

# Derived API credentials
creds = ApiCreds(
    api_key="3a4ac263-a95a-99b2-75e9-3f2d3fa04ac7",
    api_secret="TmVuSssnv_QGtbD5A5slAxWRiNr_Ks4HnD7gYotfKUU=",
    api_passphrase="1061f58748c8179440e59e7d7d5634d08edf5e8cf45dcb6e42ca3f957333df47"
)

client = ClobClient(host, key=private_key, chain_id=chain_id, creds=creds)

# Nebraska moneyline token
NEBRASKA_TOKEN = "6143758395191852229197516807548968371194839168426806816072019634277215860097"

# Bet parameters
BET_AMOUNT = 10  # $10 USDC
PRICE = 0.54  # Slightly above market (0.525) to ensure fill

print(f"Placing ${BET_AMOUNT} bet on Nebraska to WIN at {PRICE*100}¢")
num_shares = BET_AMOUNT / PRICE
print(f"Shares: {num_shares:.2f}")
print(f"Potential payout if Nebraska wins: ${num_shares:.2f}")

# Create and sign order
order_args = OrderArgs(
    price=PRICE,
    size=num_shares,
    side=BUY,
    token_id=NEBRASKA_TOKEN,
)

try:
    signed_order = client.create_order(order_args)
    print(f"Order created and signed!")
    
    # Submit order
    response = client.post_order(signed_order, OrderType.GTC)
    print(f"✅ ORDER SUBMITTED!")
    print(f"Response: {response}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
