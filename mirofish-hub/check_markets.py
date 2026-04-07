import requests

# Check market status by condition ID
THUNDER_CONDITION = '0x46c72d5cb92972c2d20d24f6ba68065a10545853557d0474cc73a88a718428f4'
CAVS_CONDITION = '0xc75831d24fabad4f6ff9dc932a177b5a611d769a704b4ee446eb57add7a8fd51'

THUNDER_TOKEN_NO = '59862632585511436198857766530429981952248716030567258213873926483088936736967'
CAVS_TOKEN_NO = '3432670311544361562896003314110816516903559805884757448626772409947882253911'

print('=== CHECKING MARKET STATUS ===')

# Check Thunder market
resp = requests.get(f'https://clob.polymarket.com/markets/{THUNDER_CONDITION}', timeout=15)
print(f'Thunder O/U 218.5 status: {resp.status_code}')
if resp.ok:
    m = resp.json()
    print(f"  Question: {m.get('question')}")
    print(f"  Active: {m.get('active')}, Closed: {m.get('closed')}, Accepting: {m.get('accepting_orders')}")
    for t in m.get('tokens', []):
        print(f"  {t.get('outcome')}: price={t.get('price')}")

# Check Cavs market
resp = requests.get(f'https://clob.polymarket.com/markets/{CAVS_CONDITION}', timeout=15)
print(f'\nCavs ML status: {resp.status_code}')
if resp.ok:
    m = resp.json()
    print(f"  Question: {m.get('question')}")
    print(f"  Active: {m.get('active')}, Closed: {m.get('closed')}, Accepting: {m.get('accepting_orders')}")
    for t in m.get('tokens', []):
        print(f"  {t.get('outcome')}: price={t.get('price')}")

# Get order book prices
print('\n=== ORDER BOOK ===')
for name, token in [('Thunder UNDER', THUNDER_TOKEN_NO), ('Cavs (Heat NO)', CAVS_TOKEN_NO)]:
    resp = requests.get(f'https://clob.polymarket.com/book?token_id={token}', timeout=15)
    if resp.ok:
        book = resp.json()
        bids = book.get('bids', [])[:3]
        asks = book.get('asks', [])[:3]
        print(f"\n{name}:")
        print(f"  Best bid: {bids[0] if bids else 'None'}")
        print(f"  Best ask: {asks[0] if asks else 'None'}")
