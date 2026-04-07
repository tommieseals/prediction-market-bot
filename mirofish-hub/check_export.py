#!/usr/bin/env python3
import json

with open('C:/Users/USER/clawd/mirofish-hub/whale_positions.json') as f:
    data = json.load(f)

print('=== OUTCOME DISTRIBUTION IN EXPORT ===')
outcomes = {}
for p in data['positions']:
    o = p.get('outcome', 'pending') or 'pending'
    outcomes[o] = outcomes.get(o, 0) + 1

for k, v in sorted(outcomes.items()):
    print(f'  {k}: {v}')

print(f'\nTotal positions in export: {len(data["positions"])}')

print('\n=== POSITIONS WITH WON OUTCOME ===')
won_count = 0
for p in data['positions']:
    if p.get('outcome') == 'won':
        won_count += 1
        pnl = p.get('actual_pnl', 0) or 0
        print(f"  {p['whale']}: {p['market'][:50]}... | ${pnl:,.0f}")

print(f'\nTotal won in export: {won_count}')
