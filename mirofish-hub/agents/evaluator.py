"""
EVALUATOR AGENT - Grades generator output and decides if we should trade

The key insight from Anthropic's paper:
"Separating the agent doing the work from the agent judging it proves to be 
a strong lever... tuning a standalone evaluator to be skeptical turns out to 
be far more tractable than making a generator critical of its own work."

This evaluator:
1. Grades the simulation output against success criteria
2. Checks for red flags and contradictions
3. Makes a final TRADE / NO_TRADE / NEEDS_REVISION decision
4. Provides detailed feedback if revision needed
"""

import json
import requests
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

# Import from sibling modules
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.generator import GeneratorResult


class Decision(Enum):
    TRADE = "TRADE"
    NO_TRADE = "NO_TRADE"
    NEEDS_REVISION = "NEEDS_REVISION"


@dataclass
class GradingCriteria:
    """Individual grading criterion with score and feedback."""
    name: str
    weight: float  # 0-1, how important is this criterion
    score: float  # 0-1, how well did we do
    threshold: float  # Minimum score to pass
    passed: bool
    feedback: str


@dataclass
class EvaluatorResult:
    """Complete evaluation result."""
    decision: str  # TRADE, NO_TRADE, NEEDS_REVISION
    confidence: float  # 0-1, how confident in this decision
    
    # Grading breakdown
    criteria: list  # List of GradingCriteria
    overall_score: float  # Weighted average
    
    # Trade parameters (if TRADE)
    recommended_size: float  # Dollar amount
    kelly_fraction: float  # Kelly criterion output
    stop_loss: Optional[float]  # Exit if price drops to this
    
    # Feedback
    summary: str
    concerns: list
    strengths: list
    
    # If NEEDS_REVISION
    revision_instructions: Optional[str]
    
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['criteria'] = [asdict(c) if hasattr(c, '__dict__') else c for c in self.criteria]
        return result


class EvaluatorAgent:
    """
    Evaluator Agent - Grades generator output with skepticism.
    
    Key principle: Be skeptical by default. The generator is optimistic,
    so the evaluator must be the voice of caution.
    """
    
    def __init__(self,
                 api_key: str = None,
                 base_url: str = None,
                 model: str = None,
                 min_edge: float = 0.08,
                 min_confidence: float = 0.60,
                 max_position: float = 100.0):  # Max $100 per trade
        import os
        self.api_key = api_key or os.getenv("LLM_API_KEY", "ollama")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
        self.model = model or os.getenv("LLM_MODEL_NAME", "qwen2.5:14b")
        self.use_openai_format = "groq" in self.base_url or self.api_key != "ollama"
        self.min_edge = min_edge
        self.min_confidence = min_confidence
        self.max_position = max_position
    
    def _call_llm(self, prompt: str, max_tokens: int = 1500) -> str:
        """Call LLM for evaluation reasoning - supports Groq/OpenAI and Ollama."""
        try:
            if self.use_openai_format:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.2,
                    },
                    timeout=60
                )
                if resp.ok:
                    return resp.json()["choices"][0]["message"]["content"]
                print(f"[Evaluator] API error: {resp.status_code} - {resp.text[:200]}")
                return ""
            else:
                resp = requests.post(
                    f"{self.base_url.replace('/v1', '')}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": 0.2,
                        }
                    },
                    timeout=90
                )
                if resp.ok:
                    return resp.json().get("response", "")
                return ""
        except Exception as e:
            print(f"[Evaluator] LLM error: {e}")
            return ""
    
    def _grade_edge_quality(self, result: GeneratorResult) -> GradingCriteria:
        """Grade: Is the edge sufficient and reliable?"""
        edge = abs(result.edge_vs_market)
        
        if edge >= 0.15:
            score = 1.0
            feedback = f"Strong edge of {edge:.1%}"
        elif edge >= 0.10:
            score = 0.85
            feedback = f"Good edge of {edge:.1%}"
        elif edge >= 0.08:
            score = 0.7
            feedback = f"Acceptable edge of {edge:.1%}"
        elif edge >= 0.05:
            score = 0.5
            feedback = f"Marginal edge of {edge:.1%} - risky"
        else:
            score = 0.2
            feedback = f"Insufficient edge of {edge:.1%} - NO TRADE"
        
        return GradingCriteria(
            name="Edge Quality",
            weight=0.30,
            score=score,
            threshold=0.6,
            passed=score >= 0.6,
            feedback=feedback
        )
    
    def _grade_whale_agreement(self, result: GeneratorResult) -> GradingCriteria:
        """Grade: Does our analysis agree with whale consensus?"""
        if result.validates_whales:
            score = 0.9
            feedback = "Swarm validates whale consensus ✓"
        else:
            # Disagreement with whales is a yellow flag, not automatic fail
            score = 0.4
            feedback = "⚠️ Swarm DISAGREES with whale consensus - proceed with caution"
        
        return GradingCriteria(
            name="Whale Agreement",
            weight=0.25,
            score=score,
            threshold=0.3,  # Low threshold - disagreement is data, not failure
            passed=True,  # Always passes, but affects score
            feedback=feedback
        )
    
    def _grade_argument_quality(self, result: GeneratorResult) -> GradingCriteria:
        """Grade: Are the arguments substantive?"""
        args_for = result.key_arguments_for
        args_against = result.key_arguments_against
        
        total_args = len(args_for) + len(args_against)
        
        if total_args >= 6:
            score = 0.9
            feedback = f"Strong analysis with {total_args} distinct arguments"
        elif total_args >= 4:
            score = 0.7
            feedback = f"Adequate analysis with {total_args} arguments"
        elif total_args >= 2:
            score = 0.5
            feedback = f"Thin analysis with only {total_args} arguments"
        else:
            score = 0.2
            feedback = "Insufficient analysis - no clear arguments"
        
        # Bonus for balanced analysis (both sides considered)
        if args_for and args_against:
            score = min(1.0, score + 0.1)
            feedback += " (balanced)"
        
        return GradingCriteria(
            name="Argument Quality",
            weight=0.20,
            score=score,
            threshold=0.5,
            passed=score >= 0.5,
            feedback=feedback
        )
    
    def _grade_confidence(self, result: GeneratorResult) -> GradingCriteria:
        """Grade: How confident is the prediction?"""
        # Confidence = how far from 50/50
        prob = result.swarm_probability
        confidence = abs(prob - 0.5) * 2  # 0 at 50%, 1 at 0% or 100%
        
        if confidence >= 0.4:
            score = 0.9
            feedback = f"High conviction ({prob:.0%} probability)"
        elif confidence >= 0.25:
            score = 0.7
            feedback = f"Moderate conviction ({prob:.0%} probability)"
        elif confidence >= 0.15:
            score = 0.5
            feedback = f"Low conviction ({prob:.0%} probability)"
        else:
            score = 0.3
            feedback = f"Near 50/50 - essentially a coin flip ({prob:.0%})"
        
        return GradingCriteria(
            name="Prediction Confidence",
            weight=0.15,
            score=score,
            threshold=0.4,
            passed=score >= 0.4,
            feedback=feedback
        )
    
    def _grade_risk_flags(self, result: GeneratorResult) -> GradingCriteria:
        """Grade: Are there concerning risk flags?"""
        risk_count = len(result.risk_flags)
        
        # Check for specific red flags
        red_flags = ['manipulation', 'insider', 'illiquid', 'error', 'failed']
        critical_risks = [r for r in result.risk_flags 
                         if any(rf in r.lower() for rf in red_flags)]
        
        if critical_risks:
            score = 0.2
            feedback = f"CRITICAL RISKS: {', '.join(critical_risks[:3])}"
        elif risk_count > 3:
            score = 0.5
            feedback = f"Multiple risk factors ({risk_count})"
        elif risk_count > 0:
            score = 0.7
            feedback = f"Some risk factors noted ({risk_count})"
        else:
            score = 0.9
            feedback = "No major risk flags"
        
        return GradingCriteria(
            name="Risk Assessment",
            weight=0.10,
            score=score,
            threshold=0.3,
            passed=score >= 0.3,
            feedback=feedback
        )
    
    def _calculate_position_size(self, 
                                  edge: float, 
                                  confidence: float,
                                  bankroll: float = 500.0) -> Tuple[float, float]:
        """
        Calculate position size using Kelly Criterion.
        
        Returns: (dollar_size, kelly_fraction)
        """
        # Kelly formula: f* = (p*b - q) / b
        # where p = prob of win, q = prob of loss, b = odds
        
        p = 0.5 + edge  # Probability of winning given our edge
        q = 1 - p
        b = 1.0  # Even money assumption
        
        kelly = (p * b - q) / b if b > 0 else 0
        
        # Use fractional Kelly (1/5th) for safety
        kelly_fraction = max(0, min(kelly / 5, 0.1))  # Cap at 10%
        
        # Apply confidence multiplier
        adjusted_kelly = kelly_fraction * confidence
        
        # Calculate dollar size
        dollar_size = min(bankroll * adjusted_kelly, self.max_position)
        
        return dollar_size, kelly_fraction
    
    def evaluate(self, result: GeneratorResult, bankroll: float = 500.0) -> EvaluatorResult:
        """
        Evaluate generator output and make a decision.
        
        Args:
            result: GeneratorResult from the Generator agent
            bankroll: Current bankroll for position sizing
            
        Returns:
            EvaluatorResult with decision and detailed grading
        """
        print(f"[Evaluator] Grading: {result.spec.get('market_title', 'Unknown')}")
        
        # Check for failed generation
        if result.status == "failed":
            return EvaluatorResult(
                decision=Decision.NO_TRADE.value,
                confidence=1.0,
                criteria=[],
                overall_score=0.0,
                recommended_size=0.0,
                kelly_fraction=0.0,
                stop_loss=None,
                summary="Generation failed - no simulation data",
                concerns=[result.error or "Unknown error"],
                strengths=[],
                revision_instructions="Re-run simulation with longer timeout"
            )
        
        # Grade each criterion
        criteria = [
            self._grade_edge_quality(result),
            self._grade_whale_agreement(result),
            self._grade_argument_quality(result),
            self._grade_confidence(result),
            self._grade_risk_flags(result),
        ]
        
        # Calculate weighted score
        total_weight = sum(c.weight for c in criteria)
        overall_score = sum(c.score * c.weight for c in criteria) / total_weight
        
        # Count failures
        failures = [c for c in criteria if not c.passed]
        
        # Collect concerns and strengths
        concerns = [c.feedback for c in criteria if c.score < 0.6]
        strengths = [c.feedback for c in criteria if c.score >= 0.8]
        
        # Make decision
        if len(failures) >= 2:
            decision = Decision.NO_TRADE
            confidence = 0.9
            summary = f"Failed {len(failures)} criteria - NO TRADE"
        elif overall_score >= 0.75 and result.edge_vs_market >= self.min_edge:
            decision = Decision.TRADE
            confidence = min(0.95, overall_score)
            summary = f"All criteria passed (score: {overall_score:.0%}) - TRADE"
        elif overall_score >= 0.6:
            decision = Decision.NEEDS_REVISION
            confidence = 0.6
            summary = f"Borderline score ({overall_score:.0%}) - needs more analysis"
        else:
            decision = Decision.NO_TRADE
            confidence = 0.8
            summary = f"Low score ({overall_score:.0%}) - NO TRADE"
        
        # Calculate position size if trading
        if decision == Decision.TRADE:
            size, kelly = self._calculate_position_size(
                edge=abs(result.edge_vs_market),
                confidence=overall_score,
                bankroll=bankroll
            )
            stop_loss = result.spec.get('avg_entry_price', 0.5) * 0.7  # 30% stop loss
        else:
            size = 0.0
            kelly = 0.0
            stop_loss = None
        
        # Build revision instructions if needed
        revision_instructions = None
        if decision == Decision.NEEDS_REVISION:
            revision_instructions = self._build_revision_instructions(criteria, result)
        
        return EvaluatorResult(
            decision=decision.value,
            confidence=confidence,
            criteria=[c.__dict__ for c in criteria],
            overall_score=overall_score,
            recommended_size=size,
            kelly_fraction=kelly,
            stop_loss=stop_loss,
            summary=summary,
            concerns=concerns,
            strengths=strengths,
            revision_instructions=revision_instructions
        )
    
    def _build_revision_instructions(self, 
                                      criteria: list, 
                                      result: GeneratorResult) -> str:
        """Build specific instructions for revision."""
        weak_criteria = [c for c in criteria if c.score < 0.6]
        
        instructions = ["Please revise the analysis focusing on:"]
        
        for c in weak_criteria:
            if c.name == "Edge Quality":
                instructions.append("- Find additional factors that could increase edge")
            elif c.name == "Argument Quality":
                instructions.append("- Develop more substantive arguments for both sides")
            elif c.name == "Prediction Confidence":
                instructions.append("- Gather more data to increase conviction")
            elif c.name == "Risk Assessment":
                instructions.append("- Address the identified risk factors")
        
        return "\n".join(instructions)


# Quick test
if __name__ == "__main__":
    from generator import GeneratorResult
    
    # Create a mock result
    test_result = GeneratorResult(
        spec={"market_title": "Test Market", "avg_entry_price": 0.55},
        simulation_id="sim_test",
        report_id="report_test",
        swarm_probability=0.72,
        swarm_sentiment="bullish",
        agent_agreement=0.8,
        key_arguments_for=["Strong momentum", "Expert consensus"],
        key_arguments_against=["Historical variance"],
        risk_flags=[],
        agents_participated=10,
        simulation_rounds=3,
        total_posts=50,
        predicted_side="YES",
        edge_vs_market=0.12,
        validates_whales=True,
        status="success"
    )
    
    evaluator = EvaluatorAgent()
    eval_result = evaluator.evaluate(test_result)
    print(json.dumps(eval_result.to_dict(), indent=2))
