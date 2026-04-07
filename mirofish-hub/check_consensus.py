import requests
from datetime import datetime

r = requests.get('http://100.115.12.91:8081/api/consensus?limit=25', timeout=30)
d = r.json()

print('=== CONSENSUS PAGE STATUS ===')
print(f"Generated: {d.get('summary', {}).get('generated_at', 'N/A')}")
print(f"Total picks: {d.get('summary', {}).get('total', 0)}")
print(f"GREEN: {d.get('summary', {}).get('green', 0)} | YELLOW: {d.get('summary', {}).get('yellow', 0)} | RED: {d.get('summary', {}).get('red', 0)}")
print()

# Check for stale/expired markets
now = datetime.now()
stale = []
live = []

print('=== TOP PICKS ===')
for i, p in enumerate(d.get('picks', [])[:15], 1):
    tier = p.get('confidence_tier', 'N/A')
    side = p.get('consensus_side')
    whales = p.get('whale_count')
    end = p.get('end_date', '')[:10] if p.get('end_date') else 'N/A'
    cat = p.get('category', 'other')
    
    # Check if expired
    if end and end != 'N/A':
        try:
            end_dt = datetime.strptime(end, '%Y-%m-%d')
            if end_dt.date() < now.date():
                stale.append(p['market_title'][:40])
                continue
        except ValueError:  # H12 FIX: Date parsing errors only
            pass
    
    live.append(p)
    symbol = '[GREEN]' if tier == 'GREEN' else '[YELLOW]' if tier == 'YELLOW' else '[RED]'
    print(f"{i}. {symbol} {p['market_title'][:50]}")
    print(f"   {side} | {whales} whales | {cat} | Ends: {end}")
    print()

if stale:
    print(f"\n[WARNING] STALE MARKETS FOUND: {len(stale)}")
    for s in stale[:5]:
        print(f"  - {s}")
else:
    print("\n[OK] No stale markets - all picks are current!")

# Check liquidity on top 3 GREEN picks
print("\n=== LIQUIDITY CHECK (Top 3 GREEN) ===")
green_picks = [p for p in d.get('picks', []) if p.get('confidence_tier') == 'GREEN'][:3]
for p in green_picks:
    cid = p.get('condition_id')
    try:
        lr = requests.get(f'http://100.115.12.91:8081/api/liquidity/{cid}', timeout=10)
        ld = lr.json()
        status = "LIQUID" if ld.get('liquid') else f"ILLIQUID - {ld.get('reason', 'N/A')}"
        print(f"{p['market_title'][:40]}: {status}")
    except Exception as e:
        print(f"{p['market_title'][:40]}: Check failed")
