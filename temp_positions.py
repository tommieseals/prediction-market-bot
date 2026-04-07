import requests

wallet = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'
r = requests.get(f'https://data-api.polymarket.com/positions?user={wallet}')
positions = r.json()

print("=== POLYMARKET POSITIONS ===\n")

pending_value = 0
pending_pnl = 0
has_positions = False

for p in positions:
    size = float(p.get('size', 0))
    if size <= 0:
        continue
    
    has_positions = True
    title = p.get('title', 'Unknown')[:55]
    avg_price = float(p.get('avgPrice', 0))
    cur_price = float(p.get('curPrice', 0))
    outcome = p.get('outcome')
    redeemable = p.get('redeemable', False)
    
    value = size * cur_price
    pnl = (cur_price - avg_price) * size
    
    if outcome and outcome != 'pending':
        icon = 'WIN' if outcome == 'won' else 'LOSS'
        redeem_flag = ' [REDEEMABLE]' if redeemable else ''
        print(f"{icon}: {title}")
        print(f"    Result: {outcome.upper()}{redeem_flag}")
    else:
        pending_value += value
        pending_pnl += pnl
        status = '+' if pnl >= 0 else '-'
        print(f"OPEN: {title}")
        print(f"    Shares: {size:.1f} @ ${avg_price:.3f} -> ${cur_price:.3f}")
        print(f"    Value: ${value:.2f} | P&L: ${pnl:+.2f}")
    print()

if not has_positions:
    print("No active positions found.")
else:
    print("=" * 40)
    print(f"TOTAL OPEN VALUE: ${pending_value:.2f}")
    print(f"UNREALIZED P&L: ${pending_pnl:+.2f}")
