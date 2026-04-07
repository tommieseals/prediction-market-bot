"""
GENERATOR AGENT - Runs MiroFish swarm simulation

Takes an AnalysisSpec from the Planner and:
1. Builds seed text from the spec
2. Runs MiroFish swarm simulation
3. Extracts probability/sentiment from the report
4. Returns structured results for the Evaluator

This is the "worker" that does the actual prediction work.
"""

import json
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mirofish_client import MiroFishClient
from agents.planner import AnalysisSpec


@dataclass
class GeneratorResult:
    """Structured output from the Generator agent."""
    spec: Dict[str, Any]  # Original spec
    
    # Simulation results
    simulation_id: str
    report_id: str
    
    # Extracted predictions
    swarm_probability: float  # 0-1, probability of YES outcome
    swarm_sentiment: str  # bullish, bearish, neutral
    agent_agreement: float  # 0-1, how much agents agreed
    
    # Key insights from report
    key_arguments_for: list
    key_arguments_against: list
    risk_flags: list
    
    # Metadata
    agents_participated: int
    simulation_rounds: int
    total_posts: int
    
    # Calculated
    predicted_side: str  # YES or NO based on probability
    edge_vs_market: float  # swarm_prob - market_price
    validates_whales: bool  # Does swarm agree with whale consensus?
    
    status: str  # success, partial, failed
    error: Optional[str] = None
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return asdict(self)


class GeneratorAgent:
    """
    Generator Agent - Runs MiroFish swarm simulations.
    
    Takes specs from Planner, runs simulations, extracts predictions.
    """
    
    def __init__(self,
                 mirofish_url: str = "http://localhost:5001",
                 timeout: int = 1800,
                 fast_mode: bool = False):  # 30 min timeout
        self.client = MiroFishClient(
            base_url=mirofish_url,
            request_timeout=timeout,
            poll_interval=5.0
        )
        self.fast_mode = fast_mode
    
    def _build_seed_text(self, spec: AnalysisSpec) -> str:
        """Build seed text for MiroFish from the analysis spec."""
        seed = f"""
Prediction Market Analysis: {spec.market_title}

Current market data:
- {spec.whale_count} whale traders have taken positions
- Whale consensus: {spec.consensus_side}
- Average entry price: ${spec.avg_entry_price:.3f}

Key factors to consider:
{chr(10).join(f'- {f}' for f in spec.key_factors)}

Risk factors:
{chr(10).join(f'- {r}' for r in spec.risk_factors)}

Time sensitivity: {spec.time_sensitivity}
Market category: {spec.market_category}

Analyze this market from multiple perspectives. Consider both bull and bear cases.
What is the most likely outcome and why?
"""
        return seed.strip()
    
    def _extract_probability(self, report: Dict) -> float:
        """Extract probability from MiroFish report."""
        # Try multiple locations where probability might be stored
        
        # Check metrics first
        metrics = report.get("metrics", {})
        if metrics.get("predicted_probability"):
            return float(metrics["predicted_probability"])
        
        # Check sentiment scores
        sentiment = report.get("sentiment", {})
        if sentiment.get("yes_probability"):
            return float(sentiment["yes_probability"])
        
        # Check the markdown content for probability mentions
        content = report.get("markdown_content", "")
        
        # Look for patterns like "probability: 65%" or "65% likely"
        import re
        prob_patterns = [
            r'probability[:\s]+(\d+(?:\.\d+)?)\s*%',
            r'(\d+(?:\.\d+)?)\s*%\s*(?:likely|chance|probability)',
            r'YES:\s*(\d+(?:\.\d+)?)\s*%',
        ]
        
        for pattern in prob_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return float(match.group(1)) / 100.0
        
        # Fallback: analyze sentiment words
        content_lower = content.lower()
        bullish_words = ['bullish', 'likely', 'expect', 'will', 'confident', 'strong']
        bearish_words = ['bearish', 'unlikely', 'doubt', 'won\'t', 'weak', 'risky']
        
        bull_count = sum(1 for w in bullish_words if w in content_lower)
        bear_count = sum(1 for w in bearish_words if w in content_lower)
        
        if bull_count + bear_count > 0:
            return 0.5 + (bull_count - bear_count) / (2 * (bull_count + bear_count + 1))
        
        return 0.5  # Default to 50/50 if we can't extract
    
    def _extract_sentiment(self, report: Dict) -> str:
        """Extract overall sentiment from report."""
        prob = self._extract_probability(report)
        if prob > 0.6:
            return "bullish"
        elif prob < 0.4:
            return "bearish"
        return "neutral"
    
    def _extract_arguments(self, report: Dict) -> tuple:
        """Extract key arguments for and against from report."""
        content = report.get("markdown_content", "")
        
        # Simple extraction - look for bullet points or numbered lists
        lines = content.split('\n')
        
        args_for = []
        args_against = []
        
        current_section = None
        for line in lines:
            line_lower = line.lower().strip()
            
            # Detect sections
            if 'bull' in line_lower or 'favor' in line_lower or 'for:' in line_lower:
                current_section = 'for'
            elif 'bear' in line_lower or 'against' in line_lower or 'risk' in line_lower:
                current_section = 'against'
            
            # Extract bullet points
            if line.strip().startswith(('-', '*', '•')) and len(line.strip()) > 5:
                arg = line.strip().lstrip('-*• ').strip()
                if current_section == 'for' and len(args_for) < 5:
                    args_for.append(arg)
                elif current_section == 'against' and len(args_against) < 5:
                    args_against.append(arg)
        
        return args_for[:5], args_against[:5]
    
    def run(self, spec: AnalysisSpec) -> GeneratorResult:
        """
        Run MiroFish simulation for the given spec.
        
        Args:
            spec: AnalysisSpec from the Planner
            
        Returns:
            GeneratorResult with simulation output
        """
        print(f"[Generator] Starting simulation for: {spec.market_title}")
        
        try:
            # Build seed text
            seed_text = self._build_seed_text(spec)
            
            # Run full MiroFish pipeline
            result = self.client.run_pipeline(
                simulation_requirement=f"Analyze prediction market: {spec.market_title}",
                seed_text=seed_text,
                project_name=f"whale_analysis_{spec.condition_id[:8]}",
                platform="parallel",
                max_rounds=3,
                skip_graph=True,  # Skip Zep for speed
                fast_mode=self.fast_mode,  # Skip LLM profiles if fast_mode enabled
            )
            
            # Check if we got a report
            report = result.get("report", {})
            if not report or not report.get("markdown_content"):
                return GeneratorResult(
                    spec=spec.to_dict(),
                    simulation_id=result.get("simulation_id", ""),
                    report_id=result.get("report_id", ""),
                    swarm_probability=0.5,
                    swarm_sentiment="neutral",
                    agent_agreement=0.0,
                    key_arguments_for=[],
                    key_arguments_against=[],
                    risk_flags=["No report generated"],
                    agents_participated=0,
                    simulation_rounds=0,
                    total_posts=0,
                    predicted_side="UNKNOWN",
                    edge_vs_market=0.0,
                    validates_whales=False,
                    status="partial",
                    error="No report content"
                )
            
            # Extract predictions
            probability = self._extract_probability(report)
            sentiment = self._extract_sentiment(report)
            args_for, args_against = self._extract_arguments(report)
            
            # Calculate derived values
            predicted_side = "YES" if probability > 0.5 else "NO"
            edge = probability - spec.avg_entry_price if predicted_side == spec.consensus_side else spec.avg_entry_price - probability
            validates_whales = predicted_side == spec.consensus_side
            
            # Get metrics
            metrics = report.get("metrics", {})
            
            return GeneratorResult(
                spec=spec.to_dict(),
                simulation_id=result.get("simulation_id", ""),
                report_id=result.get("report_id", ""),
                swarm_probability=probability,
                swarm_sentiment=sentiment,
                agent_agreement=metrics.get("agreement_score", 0.7),
                key_arguments_for=args_for,
                key_arguments_against=args_against,
                risk_flags=spec.risk_factors,
                agents_participated=metrics.get("agent_count", 10),
                simulation_rounds=metrics.get("rounds", 3),
                total_posts=metrics.get("total_posts", 0),
                predicted_side=predicted_side,
                edge_vs_market=edge,
                validates_whales=validates_whales,
                status="success"
            )
            
        except Exception as e:
            print(f"[Generator] Error: {e}")
            return GeneratorResult(
                spec=spec.to_dict(),
                simulation_id="",
                report_id="",
                swarm_probability=0.5,
                swarm_sentiment="neutral",
                agent_agreement=0.0,
                key_arguments_for=[],
                key_arguments_against=[],
                risk_flags=[str(e)],
                agents_participated=0,
                simulation_rounds=0,
                total_posts=0,
                predicted_side="UNKNOWN",
                edge_vs_market=0.0,
                validates_whales=False,
                status="failed",
                error=str(e)
            )


# Quick test
if __name__ == "__main__":
    from planner import PlannerAgent, AnalysisSpec
    
    # Create a test spec
    spec = AnalysisSpec(
        market_title="Test Market",
        condition_id="0xtest",
        consensus_side="YES",
        whale_count=3,
        avg_entry_price=0.55,
        market_category="sports",
        key_factors=["Factor 1", "Factor 2"],
        risk_factors=["Risk 1"],
        time_sensitivity="normal",
        confidence_threshold=0.65,
        edge_threshold=0.08,
        success_criteria={"min_edge": 0.08}
    )
    
    generator = GeneratorAgent()
    result = generator.run(spec)
    print(json.dumps(result.to_dict(), indent=2))
