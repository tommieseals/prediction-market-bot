#!/usr/bin/env python3
"""Quick test of report parser integration."""

import json
import sys
sys.path.insert(0, 'C:/Users/USER/clawd/mirofish-hub')
from report_parser import extract_consensus_from_report

result = extract_consensus_from_report('report_bdb4ae63cf03')
print(json.dumps(result, indent=2))

# Simulate trade signal logic
model_prob = result['consensus_probability'] / 100.0
market_prob = 0.74
edge = model_prob - market_prob

print()
print(f"Raw Model:    {model_prob:.1%}")
print(f"Market:       {market_prob:.1%}")
print(f"Raw Edge:     {edge:+.1%}")

# Apply risk haircuts
adjustments = []
if result.get('has_safety_risk'):
    model_prob -= 0.05
    adjustments.append("Safety -5%")
if result.get('has_cmc_risk'):
    model_prob -= 0.03
    adjustments.append("CMC -3%")

if adjustments:
    print(f"Adjustments:  {', '.join(adjustments)}")
    
final_edge = model_prob - market_prob
print()
print(f"Adjusted:     {model_prob:.1%}")
print(f"Final Edge:   {final_edge:+.1%}")
print()
if abs(final_edge) >= 0.15:
    print("[TARGET] TRADE SIGNAL: YES")
else:
    print("[FAIL] No trade - edge below 15%")
