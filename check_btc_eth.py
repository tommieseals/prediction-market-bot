import requests

wallet = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'
r = requests.get(f'https://data-api.polymarket.com/positions?user={wallet}')
positions = r.json()

print("=== CHECKING BTC & ETH POSITIONS ===\n")

for p in positions:
    title = p.get('title', '')
    if 'Bitcoin' in title or 'BTC' in title or 'Ethereum' in title or 'ETH' in title:
        print(f"Market: {title}")
        print(f"  Side: {p.get('side')}")
        print(f"  Outcome: {p.get('outcome')}")
        print(f"  Size: {p.get('size')}")
        print(f"  Avg Price: {p.get('avgPrice')}")
        print(f"  Redeemable: {p.get('redeemable')}")
        print(f"  Full data: {p}")
        print()

print("\n=== ALL RESOLVED POSITIONS (to see what we actually bet) ===\n")
for p in positions:
    outcome = p.get('outcome')
    if outcome and outcome != 'pending':
        title = p.get('title', 'Unknown')[:50]
        side = p.get('side', '?')
        print(f"{title}")
        print(f"  Our side: {side} | Result: {outcome}")
        print()
