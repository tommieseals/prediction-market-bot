#!/usr/bin/env python3
"""Test the three-agent pipeline components (Planner + Evaluator) without MiroFish."""
import os
import sys
os.environ["PYTHONUTF8"] = "1"
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("THREE-AGENT COMPONENT TEST")
print("=" * 60)

# Test 1: Planner
print("\n[1] PLANNER TEST")
try:
    from agents.planner import PlannerAgent, AnalysisSpec
    print("  Import OK")
    
    planner = PlannerAgent()
    print("  Agent created OK")
    
    spec = planner.expand_pick({
        'market_title': 'Rockets vs Timberwolves',
        'side': 'YES',
        'whale_count': 5,
        'avg_entry_price': 0.55,
        'end_date': '2026-03-26'
    })
    
    print(f"  Category: {spec.market_category}")
    print(f"  Key factors: {spec.key_factors}")
    print(f"  Thresholds: edge={spec.edge_threshold}, conf={spec.confidence_threshold}")
    print("  [OK] PLANNER WORKS!")
    
except Exception as e:
    print(f"  [FAIL] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Evaluator
print("\n[2] EVALUATOR TEST")
try:
    from agents.evaluator import EvaluatorAgent
    from agents.generator import GeneratorResult
    print("  Import OK")
    
    evaluator = EvaluatorAgent()
    print("  Agent created OK")
    
    # Create mock generator result
    mock_result = GeneratorResult(
        spec={'market_title': 'Test'},
        simulation_id='test',
        report_id='test',
        swarm_probability=0.65,
        swarm_sentiment='bullish',
        agent_agreement=0.7,
        key_arguments_for=['Strong home record'],
        key_arguments_against=['Key player injured'],
        risk_flags=[],
        agents_participated=100,
        simulation_rounds=3,
        total_posts=500,
        predicted_side='YES',
        edge_vs_market=0.10,
        validates_whales=True,
        status='success'
    )
    
    # Create simple spec for evaluation (use planner's output directly)
    simple_spec = planner.expand_pick({
        'market_title': 'Rockets vs Timberwolves',
        'side': 'YES',
        'whale_count': 5,
        'avg_entry_price': 0.55,
        'condition_id': 'test123'
    })
    
    decision = evaluator.evaluate(mock_result, bankroll=500.0)
    print(f"  Decision: {decision.decision}")
    print(f"  Confidence: {decision.confidence:.1%}")
    print(f"  Overall Score: {decision.overall_score:.1f}")
    print(f"  Recommended Size: ${decision.recommended_size:.2f}")
    print(f"  Summary: {decision.summary[:100]}...")
    print("  [OK] EVALUATOR WORKS!")
    
except Exception as e:
    print(f"  [FAIL] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
