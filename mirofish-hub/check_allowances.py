import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams

# Trading wallet
PRIVATE_KEY = "39f1a59fe9c2c006ac51e1edad69be0a0133df21c053e91f34387ba9cc9f30ae"
WALLET = "0x299aCc0857B943d8490ECb1820fD458B3B58c728"

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
creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)
print(f"API Key: {creds.api_key[:30]}...")
print(f"API Secret: {creds.api_secret[:20]}...")

# Check balance and allowances
TOKEN_ID = "53672610104884801589662124213210078919813716584355622362595283011438952484973"

print("\n=== Checking Balance & Allowances ===")
try:
    params = BalanceAllowanceParams(
        asset_type="CONDITIONAL",
        token_id=TOKEN_ID
    )
    result = client.get_balance_allowance(params)
    print(f"Balance/Allowance: {result}")
except Exception as e:
    print(f"Balance check error: {e}")

# Check USDC balance
try:
    usdc_params = BalanceAllowanceParams(asset_type="COLLATERAL")
    usdc_result = client.get_balance_allowance(usdc_params)
    print(f"USDC Balance/Allowance: {usdc_result}")
except Exception as e:
    print(f"USDC check error: {e}")

# Check what the wallet looks like to the API
print("\n=== Checking API Access ===")
try:
    # Check if we can get tick sizes
    r = requests.get('https://clob.polymarket.com/tick-sizes')
    print(f"API tick-sizes accessible: {r.status_code == 200}")
except Exception as e:
    print(f"API check error: {e}")

# Try to derive credentials fresh
print("\n=== Re-deriving API Creds ===")
try:
    creds = client.derive_api_key()
    print(f"Derived key: {creds}")
except Exception as e:
    print(f"Derive error: {e}")
