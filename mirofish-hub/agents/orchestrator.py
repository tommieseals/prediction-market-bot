"""
AGENT ORCHESTRATOR - Coordinates the three-agent architecture

Flow:
1. Planner expands whale pick → AnalysisSpec
2. Generator runs MiroFish simulation → GeneratorResult
3. Evaluator grades output → Decision (TRADE / NO_TRADE / NEEDS_REVISION)
4. If NEEDS_REVISION: Generator refines → back to step 3
5. Final output: Trade signal or rejection with full reasoning

This implements the GAN-inspired feedback loop from Anthropic's paper.
"""

import json
import sqlite3
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import sys
import os

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.planner import PlannerAgent, AnalysisSpec
from agents.generator import GeneratorAgent, GeneratorResult
from agents.evaluator import EvaluatorAgent, EvaluatorResult, Decision


@dataclass
class TradeSignal:
    """Final output from the orchestrator."""
    market_title: str
    condition_id: str
    
    # Decision
    decision: str  # TRADE, NO_TRADE
    side: str  # YES or NO
    
    # If TRADE
    recommended_size: float
    entry_price: float
    stop_loss: Optional[float]
    edge: float
    
    # Reasoning
    summary: str
    key_arguments: list
    concerns: list
    
    # Scores
    overall_score: float
    confidence: float
    
    # Metadata
    whale_count: int
    whale_consensus: str
    validates_whales: bool
    
    # Audit trail
    iterations: int
    planner_spec: Dict
    final_evaluation: Dict
    
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class AgentOrchestrator:
    """
    Orchestrates the three-agent architecture for whale pick validation.
    
    Implements the feedback loop:
    Planner → Generator → Evaluator → (revise?) → Final Decision
    """
    
    def __init__(self,
                 max_iterations: int = 3,
                 bankroll: float = 500.0,
                 db_path: str = None,
                 fast_mode: bool = False):
        
        self.planner = PlannerAgent()
        self.generator = GeneratorAgent(fast_mode=fast_mode)
        self.evaluator = EvaluatorAgent()
        self.fast_mode = fast_mode
        
        self.max_iterations = max_iterations
        self.bankroll = bankroll
        
        # Database for logging
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "agent_orchestrator.db"
        )
        self._init_db()
    
    def _init_db(self):
        """Initialize the orchestrator database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_title TEXT,
                condition_id TEXT,
                decision TEXT,
                side TEXT,
                recommended_size REAL,
                edge REAL,
                overall_score REAL,
                confidence REAL,
                iterations INTEGER,
                whale_count INTEGER,
                validates_whales INTEGER,
                created_at TEXT,
                full_result TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def _log_run(self, signal: TradeSignal):
        """Log the orchestrator run to database."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT INTO orchestrator_runs
                (market_title, condition_id, decision, side, recommended_size,
                 edge, overall_score, confidence, iterations, whale_count,
                 validates_whales, created_at, full_result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.market_title,
                signal.condition_id,
                signal.decision,
                signal.side,
                signal.recommended_size,
                signal.edge,
                signal.overall_score,
                signal.confidence,
                signal.iterations,
                signal.whale_count,
                1 if signal.validates_whales else 0,
                signal.created_at,
                signal.to_json()
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[Orchestrator] DB log error: {e}")
    
    def process_pick(self, pick: Dict[str, Any]) -> TradeSignal:
        """
        Process a whale consensus pick through the full pipeline.
        
        Args:
            pick: Dict with market_title, condition_id, consensus_side,
                  whale_count, avg_entry_price, etc.
        
        Returns:
            TradeSignal with final decision and reasoning
        """
        market_title = pick.get("market_title", "Unknown")
        print(f"\n{'='*60}")
        print(f"[Orchestrator] Processing: {market_title}")
        print(f"{'='*60}")
        
        # Step 1: Planner
        print("\n[Step 1] PLANNER - Expanding pick into analysis spec...")
        spec = self.planner.expand_pick(pick)
        print(f"  Category: {spec.market_category}")
        print(f"  Key factors: {spec.key_factors[:3]}")
        print(f"  Thresholds: edge={spec.edge_threshold:.0%}, conf={spec.confidence_threshold:.0%}")
        
        # Step 2-4: Generator → Evaluator loop
        iterations = 0
        final_gen_result = None
        final_eval_result = None
        
        while iterations < self.max_iterations:
            iterations += 1
            print(f"\n[Step 2] GENERATOR - Iteration {iterations}/{self.max_iterations}")
            
            # Run generator
            gen_result = self.generator.run(spec)
            final_gen_result = gen_result
            
            if gen_result.status == "failed":
                print(f"  ❌ Generation failed: {gen_result.error}")
                break
            
            print(f"  Probability: {gen_result.swarm_probability:.0%}")
            print(f"  Predicted: {gen_result.predicted_side}")
            print(f"  Edge: {gen_result.edge_vs_market:.1%}")
            print(f"  Validates whales: {gen_result.validates_whales}")
            
            # Run evaluator
            print(f"\n[Step 3] EVALUATOR - Grading output...")
            eval_result = self.evaluator.evaluate(gen_result, self.bankroll)
            final_eval_result = eval_result
            
            print(f"  Overall score: {eval_result.overall_score:.0%}")
            print(f"  Decision: {eval_result.decision}")
            
            # Check decision
            if eval_result.decision == Decision.TRADE.value:
                print(f"  ✅ TRADE - Size: ${eval_result.recommended_size:.2f}")
                break
            elif eval_result.decision == Decision.NO_TRADE.value:
                print(f"  ❌ NO TRADE - {eval_result.summary}")
                break
            elif eval_result.decision == Decision.NEEDS_REVISION.value:
                print(f"  🔄 Needs revision - will retry")
                if eval_result.revision_instructions:
                    print(f"     Instructions: {eval_result.revision_instructions[:100]}")
                # Continue to next iteration
            else:
                break
        
        # Build final signal
        if final_gen_result is None or final_eval_result is None:
            # Complete failure
            signal = TradeSignal(
                market_title=market_title,
                condition_id=pick.get("condition_id", ""),
                decision="NO_TRADE",
                side="UNKNOWN",
                recommended_size=0.0,
                entry_price=pick.get("avg_entry_price", 0.5),
                stop_loss=None,
                edge=0.0,
                summary="Pipeline failed - no valid output",
                key_arguments=[],
                concerns=["Complete pipeline failure"],
                overall_score=0.0,
                confidence=0.0,
                whale_count=pick.get("whale_count", 0),
                whale_consensus=pick.get("consensus_side", "UNKNOWN"),
                validates_whales=False,
                iterations=iterations,
                planner_spec=spec.to_dict(),
                final_evaluation={}
            )
        else:
            signal = TradeSignal(
                market_title=market_title,
                condition_id=pick.get("condition_id", ""),
                decision=final_eval_result.decision,
                side=final_gen_result.predicted_side,
                recommended_size=final_eval_result.recommended_size,
                entry_price=pick.get("avg_entry_price", 0.5),
                stop_loss=final_eval_result.stop_loss,
                edge=final_gen_result.edge_vs_market,
                summary=final_eval_result.summary,
                key_arguments=final_gen_result.key_arguments_for[:3],
                concerns=final_eval_result.concerns,
                overall_score=final_eval_result.overall_score,
                confidence=final_eval_result.confidence,
                whale_count=pick.get("whale_count", 0),
                whale_consensus=pick.get("consensus_side", "UNKNOWN"),
                validates_whales=final_gen_result.validates_whales,
                iterations=iterations,
                planner_spec=spec.to_dict(),
                final_evaluation=final_eval_result.to_dict()
            )
        
        # Log to database
        self._log_run(signal)
        
        # Final summary
        print(f"\n{'='*60}")
        print(f"[FINAL] {signal.decision} - {market_title}")
        print(f"  Side: {signal.side} | Edge: {signal.edge:.1%} | Score: {signal.overall_score:.0%}")
        if signal.decision == "TRADE":
            print(f"  💰 Recommended: ${signal.recommended_size:.2f}")
        print(f"{'='*60}\n")
        
        return signal
    
    def process_batch(self, picks: List[Dict]) -> List[TradeSignal]:
        """Process multiple picks."""
        results = []
        for i, pick in enumerate(picks):
            print(f"\n[Batch {i+1}/{len(picks)}]")
            signal = self.process_pick(pick)
            results.append(signal)
            time.sleep(1)  # Small delay between picks
        return results
    
    def get_recent_signals(self, limit: int = 10) -> List[Dict]:
        """Get recent trade signals from database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM orchestrator_runs
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]


# Integration with whale_hunter_connector
def validate_whale_pick(pick: Dict[str, Any], 
                        bankroll: float = 500.0) -> TradeSignal:
    """
    Convenience function to validate a single whale pick.
    
    This is the main entry point for the whale_hunter_connector.
    """
    orchestrator = AgentOrchestrator(bankroll=bankroll)
    return orchestrator.process_pick(pick)


# CLI
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MiroFish Agent Orchestrator")
    parser.add_argument("--test", action="store_true", help="Run test pick")
    parser.add_argument("--history", type=int, default=0, help="Show recent signals")
    args = parser.parse_args()
    
    orchestrator = AgentOrchestrator()
    
    if args.history > 0:
        signals = orchestrator.get_recent_signals(args.history)
        print(f"\nRecent {len(signals)} signals:")
        for s in signals:
            print(f"  {s['decision']} | {s['market_title'][:40]} | "
                  f"Edge: {s['edge']:.1%} | Score: {s['overall_score']:.0%}")
    
    elif args.test:
        test_pick = {
            "market_title": "Lakers vs. Celtics: O/U 220.5",
            "condition_id": "0xtest123",
            "consensus_side": "OVER",
            "whale_count": 5,
            "avg_entry_price": 0.52,
        }
        
        signal = orchestrator.process_pick(test_pick)
        print("\n" + signal.to_json())
    
    else:
        print("Usage: python orchestrator.py --test | --history N")
