"""
PLANNER AGENT - Expands whale consensus picks into full analysis specs

Takes a simple input (whale consensus pick) and expands it into:
- Full market context
- Key factors to analyze
- Risk considerations
- Success criteria for the evaluator

Inspired by Anthropic's harness design.
"""

import json
import requests
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class AnalysisSpec:
    """Structured specification for a market analysis."""
    market_title: str
    condition_id: str
    consensus_side: str  # YES or NO
    whale_count: int
    avg_entry_price: float
    
    # Expanded by planner
    market_category: str  # sports, crypto, politics, etc.
    key_factors: list  # What should the swarm analyze?
    risk_factors: list  # What could go wrong?
    time_sensitivity: str  # urgent, normal, long-term
    confidence_threshold: float  # Minimum confidence to trade
    edge_threshold: float  # Minimum edge % to trade
    
    # Success criteria for evaluator
    success_criteria: Dict[str, Any]
    
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class PlannerAgent:
    """
    Planner Agent - Expands simple whale picks into full analysis specs.
    
    Uses LLM to:
    1. Categorize the market
    2. Identify key factors to analyze
    3. Assess risks
    4. Define success criteria
    """
    
    def __init__(self, 
                 api_key: str = None,
                 base_url: str = None,
                 model: str = None):
        # Load from environment with fallbacks
        import os
        self.api_key = api_key or os.getenv("LLM_API_KEY", "ollama")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
        self.model = model or os.getenv("LLM_MODEL_NAME", "qwen2.5:14b")
        self.use_openai_format = "groq" in self.base_url or self.api_key != "ollama"
    
    def _call_llm(self, prompt: str, max_tokens: int = 2000) -> str:
        """Call LLM - supports Groq/OpenAI format and Ollama."""
        try:
            if self.use_openai_format:
                # OpenAI-compatible API (Groq, Together, etc.)
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
                        "temperature": 0.3,
                    },
                    timeout=60
                )
                if resp.ok:
                    return resp.json()["choices"][0]["message"]["content"]
                print(f"[Planner] API error: {resp.status_code} - {resp.text[:200]}")
                return ""
            else:
                # Local Ollama format
                resp = requests.post(
                    f"{self.base_url.replace('/v1', '')}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": 0.3,
                        }
                    },
                    timeout=120
                )
                if resp.ok:
                    return resp.json().get("response", "")
                return ""
        except Exception as e:
            print(f"[Planner] LLM error: {e}")
            return ""
    
    def expand_pick(self, pick: Dict[str, Any]) -> AnalysisSpec:
        """
        Expand a whale consensus pick into a full analysis spec.
        
        Args:
            pick: Dict with market_title, condition_id, consensus_side, 
                  whale_count, avg_entry_price, etc.
        
        Returns:
            AnalysisSpec with full analysis plan
        """
        market_title = pick.get("market_title", "Unknown Market")
        
        # Step 1: Categorize and analyze with LLM
        planning_prompt = f"""You are a prediction market analyst. Analyze this market and create an analysis plan.

MARKET: {market_title}
WHALE CONSENSUS: {pick.get('consensus_side', 'YES')} (from {pick.get('whale_count', 0)} whales)
AVERAGE ENTRY PRICE: ${pick.get('avg_entry_price', 0.5):.3f}

Respond in this exact JSON format:
{{
    "category": "sports|crypto|politics|entertainment|science|economics|other",
    "key_factors": ["factor1", "factor2", "factor3"],
    "risk_factors": ["risk1", "risk2"],
    "time_sensitivity": "urgent|normal|long-term",
    "confidence_threshold": 0.65,
    "edge_threshold": 0.08,
    "analysis_approach": "Brief description of how to analyze this"
}}

Be specific to THIS market. What factors matter for {market_title}?"""

        llm_response = self._call_llm(planning_prompt)
        
        # Parse LLM response
        try:
            # Extract JSON from response
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                plan_data = json.loads(llm_response[json_start:json_end])
            else:
                plan_data = {}
        except json.JSONDecodeError:
            plan_data = {}
        
        # Build success criteria
        success_criteria = {
            "min_swarm_agreement": 0.6,  # 60% of agents agree
            "min_confidence": plan_data.get("confidence_threshold", 0.65),
            "min_edge": plan_data.get("edge_threshold", 0.08),
            "validates_whale_consensus": True,  # Swarm should agree with whales
            "max_contradiction_rate": 0.3,  # Max 30% strong disagreement
        }
        
        # Create the spec
        spec = AnalysisSpec(
            market_title=market_title,
            condition_id=pick.get("condition_id", ""),
            consensus_side=pick.get("consensus_side", "YES"),
            whale_count=pick.get("whale_count", 0),
            avg_entry_price=pick.get("avg_entry_price", 0.5),
            market_category=plan_data.get("category", self._guess_category(market_title)),
            key_factors=plan_data.get("key_factors", self._default_factors(market_title)),
            risk_factors=plan_data.get("risk_factors", ["Unexpected outcome", "Market manipulation"]),
            time_sensitivity=plan_data.get("time_sensitivity", "normal"),
            confidence_threshold=plan_data.get("confidence_threshold", 0.65),
            edge_threshold=plan_data.get("edge_threshold", 0.08),
            success_criteria=success_criteria,
        )
        
        return spec
    
    def _guess_category(self, title: str) -> str:
        """Fallback category detection."""
        title_lower = title.lower()
        if any(x in title_lower for x in ['vs.', 'game', 'match', 'nba', 'nfl', 'mlb', 'spread', 'o/u']):
            return "sports"
        elif any(x in title_lower for x in ['bitcoin', 'btc', 'eth', 'crypto', 'token']):
            return "crypto"
        elif any(x in title_lower for x in ['trump', 'biden', 'election', 'congress', 'president']):
            return "politics"
        elif any(x in title_lower for x in ['iran', 'ukraine', 'war', 'military']):
            return "geopolitics"
        return "other"
    
    def _default_factors(self, title: str) -> list:
        """Fallback key factors based on category."""
        cat = self._guess_category(title)
        if cat == "sports":
            return ["Team form", "Head-to-head record", "Injuries", "Home/away advantage"]
        elif cat == "crypto":
            return ["Market sentiment", "Technical indicators", "News catalyst", "Macro environment"]
        elif cat == "politics":
            return ["Polling data", "Historical precedent", "Recent events", "Expert consensus"]
        return ["Public sentiment", "Expert opinion", "Historical data"]


# Quick test
if __name__ == "__main__":
    planner = PlannerAgent()
    
    test_pick = {
        "market_title": "Lakers vs. Celtics: O/U 220.5",
        "condition_id": "0xabc123",
        "consensus_side": "OVER",
        "whale_count": 5,
        "avg_entry_price": 0.52,
    }
    
    spec = planner.expand_pick(test_pick)
    print(spec.to_json())
