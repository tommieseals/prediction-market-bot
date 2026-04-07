import requests

r = requests.get('http://localhost:8081/api/consensus', timeout=15)
d = r.json()
picks = d.get('picks', [])
summary = d.get('summary', {})

print('=== CONSENSUS PICKS SUMMARY ===')
print(f"GREEN (High Confidence): {summary.get('green', 0)}")
print(f"YELLOW (Medium): {summary.get('yellow', 0)}")
print(f"RED (Low): {summary.get('red', 0)}")
print(f"TOTAL: {summary.get('total', 0)}")
print()
print('=== GREEN PICKS (High Confidence) ===')
for p in picks:
    if p.get('confidence_tier') == 'GREEN':
        title = p.get('market_title', '')[:50]
        whales = p.get('whale_count', 0)
        side = p.get('consensus_side', '')
        pct = p.get('agreement_pct', 0)
        elite = p.get('avg_elite_score', 0)
        size = p.get('total_size_usd', 0)
        exp = p.get('end_date', '')[:10]
        print(f"{title}")
        print(f"  {whales} whales | {pct:.0f}% {side} | Elite: {elite:.1f} | Size: ${size:,.0f} | Exp: {exp}")
        print()
