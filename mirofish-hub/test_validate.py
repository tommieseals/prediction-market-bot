# -*- coding: utf-8 -*-
"""Test the validation pipeline step by step"""
import sys

# Force unbuffered output
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, '.')

print("Step 1: Testing imports...", flush=True)

try:
    from agents.validate_picks import get_pending_picks
    print("  - validate_picks OK", flush=True)
except Exception as e:
    print(f"  - validate_picks FAILED: {e}", flush=True)
    sys.exit(1)

try:
    from agents.orchestrator import AgentOrchestrator
    print("  - orchestrator OK", flush=True)
except Exception as e:
    print(f"  - orchestrator FAILED: {e}", flush=True)
    sys.exit(1)

print("\nStep 2: Getting pending picks...", flush=True)
picks = get_pending_picks(5)
print(f"Found {len(picks)} pending picks:", flush=True)
for p in picks:
    title = str(p.get('market_title', 'Unknown'))[:40]
    side = p.get('consensus_side', '?')
    whales = p.get('whale_count', 0)
    print(f"  ID {p.get('id')}: {title}... | {side} | {whales} whales", flush=True)

if not picks:
    print("No pending picks found!", flush=True)
    sys.exit(0)

print("\nStep 3: Initializing orchestrator...", flush=True)
try:
    orchestrator = AgentOrchestrator()
    print("  - Orchestrator initialized OK", flush=True)
except Exception as e:
    print(f"  - Orchestrator init FAILED: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nStep 4: Testing one pick through pipeline...", flush=True)
pick = picks[0]
title = str(pick.get('market_title', 'Unknown'))[:50]
print(f"Testing: {title}", flush=True)

try:
    result = orchestrator.process_pick({
        'market_title': pick.get('market_title'),
        'condition_id': pick.get('condition_id'),
        'whale_consensus_side': pick.get('consensus_side'),
        'whale_count': pick.get('whale_count'),
        'avg_entry_price': pick.get('avg_entry_price'),
        'confidence': pick.get('confidence')
    })
    print(f"\nRESULT:", flush=True)
    print(f"  Decision: {result.decision}", flush=True)
    print(f"  Side: {result.side}", flush=True)
    print(f"  Edge: {result.edge:.1%}", flush=True)
    print(f"  Score: {result.overall_score:.0%}", flush=True)
except Exception as e:
    print(f"PIPELINE FAILED: {e}", flush=True)
    import traceback
    traceback.print_exc()

print("\nTest complete!", flush=True)
