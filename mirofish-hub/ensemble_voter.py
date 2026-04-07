"""
ensemble_voter.py - Multi-model ensemble voting system for probability estimation.

Queries multiple Ollama LLM models with the same question, extracts probability
estimates from each, and computes a weighted ensemble probability.

Phase 1: All models run on local RTX 3060 via Ollama at localhost:11434.

Usage:
    python ensemble_voter.py "Will Lakers win tonight?"
    python ensemble_voter.py "Will BTC hit 100k?" --context "BTC at 97k, strong momentum"
"""

import argparse
import json
import math
import re
import sys
import time
from typing import Optional

import requests

# Context injection for enriched prompts
try:
    from context_injector import ContextInjector
    HAS_CONTEXT_INJECTOR = True
except ImportError:
    HAS_CONTEXT_INJECTOR = False


# ---------------------------------------------------------------------------
# Model registry -- Full network ensemble (Updated 2026-03-26)
# ---------------------------------------------------------------------------
MODELS = {
    "rtx_4b":      {"model": "qwen3:4b", "host": "localhost:11434", "weight": 0.40},           # RTX 3060 - Primary (97.5 tok/sec!)
    "macpro_7b":   {"model": "qwen2.5:7b",  "host": "100.85.43.98:11434", "weight": 0.30},        # Mac Pro - Secondary
    "cloud_7b":    {"model": "qwen2.5:7b",  "host": "100.107.231.87:11434", "weight": 0.20},      # Google Cloud - Always-on
    "macmini_3b":  {"model": "qwen2.5:3b",  "host": "100.88.105.106:11434", "weight": 0.10},      # Mac Mini - Fast tiebreaker
}

PROMPT_TEMPLATE = (
    "You are an expert prediction market analyst. Based on the following "
    "information, estimate the probability that the following event will happen.\n"
    "\n"
    "Context: {context}\n"
    "\n"
    "Question: {question}\n"
    "\n"
    "Respond with ONLY a number between 0 and 100 representing the percentage "
    "probability.\n"
    "For example: 65"
)


class EnsembleVoter:
    """Query multiple Ollama models and aggregate their probability estimates.

    Each model receives an identical prompt asking for a 0-100 probability.
    Results are combined via weighted average, with failed models excluded
    and weights renormalized over the surviving set.

    Attributes:
        ollama_host: Default Ollama API host (overridden per-model if set).
        timeout: HTTP timeout in seconds for each model query.
        models: Copy of the MODELS registry used for this voter instance.
    """

    def __init__(self, ollama_host: str = "localhost:11434", timeout: int = 60):
        """Initialize the ensemble voter.

        Args:
            ollama_host: Default Ollama host:port. Individual model entries
                         can override this via their own 'host' key.
            timeout: Per-model HTTP request timeout in seconds.
        """
        self.ollama_host = ollama_host
        self.timeout = timeout
        self.models = dict(MODELS)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_probability(response_text: str) -> float:
        """Parse an LLM response to find a probability value.

        Searches for common patterns such as:
          - Plain integers/decimals: "65", "0.65", "72.5"
          - Percentage notation:     "65%", "72.5%"
          - Labelled values:         "probability: 65", "Probability is 0.72"

        The first match wins.  Values > 1.0 are assumed to be on a 0-100
        scale and are divided by 100.  The result is clamped to [0.0, 1.0].

        Args:
            response_text: Raw text returned by the LLM.

        Returns:
            Probability as a float in [0.0, 1.0].

        Raises:
            ValueError: If no numeric probability pattern is found.
        """
        text = response_text.strip()

        # Pattern 1: "probability: 65" / "probability is 0.72"
        labelled = re.search(
            r"probability\s*(?:is|:|\=)\s*([0-9]+(?:\.[0-9]+)?)\s*%?",
            text,
            re.IGNORECASE,
        )
        if labelled:
            val = float(labelled.group(1))
            return max(0.0, min(1.0, val / 100.0 if val > 1.0 else val))

        # Pattern 2: "65%" or "72.5%"
        pct = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", text)
        if pct:
            return max(0.0, min(1.0, float(pct.group(1)) / 100.0))

        # Pattern 3: bare number -- take the first number found
        bare = re.search(r"\b([0-9]+(?:\.[0-9]+)?)\b", text)
        if bare:
            val = float(bare.group(1))
            if val > 1.0:
                val = val / 100.0
            return max(0.0, min(1.0, val))

        raise ValueError(f"Could not extract probability from response: {text[:200]}")

    def _query_model(self, model_name: str, prompt: str) -> float:
        """Query a single Ollama model and return a probability.

        Sends a POST request to the Ollama /api/generate endpoint with
        stream=False so the full response is returned in one shot.

        Args:
            model_name: Key into self.models (e.g. "qwen14b").
            prompt: The fully-formatted prompt string.

        Returns:
            Extracted probability as a float in [0.0, 1.0].

        Raises:
            requests.RequestException: On HTTP or connection failures.
            ValueError: If the response cannot be parsed into a probability.
        """
        cfg = self.models[model_name]
        host = cfg.get("host", self.ollama_host)
        url = f"http://{host}/api/generate"

        payload = {
            "model": cfg["model"],
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 64,
            },
        }

        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()

        data = resp.json()
        response_text = data.get("response", "")
        return self._extract_probability(response_text)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def vote(self, question: str, context: str = "") -> dict:
        """Query all models and compute a weighted ensemble probability.

        Models are queried sequentially.  If a model fails (network error,
        timeout, unparseable response), it is skipped and a warning is
        printed.  The remaining models' weights are renormalized so they
        still sum to 1.0.

        Args:
            question: The prediction question to evaluate.
            context: Optional background information for the models.

        Returns:
            A dict with:
                ensemble_prob  -- weighted average probability [0.0, 1.0]
                model_votes    -- list of per-model result dicts
                confidence     -- 1 - normalized_std_dev (higher = more agreement)
                agreement      -- 1 - (max_prob - min_prob) among successful votes
        """
        prompt = PROMPT_TEMPLATE.format(
            context=context if context else "No additional context provided.",
            question=question,
        )

        model_votes = []
        successful_probs = []
        successful_weights = []

        for name, cfg in self.models.items():
            entry = {
                "model_name": name,
                "model_id": cfg["model"],
                "weight": cfg["weight"],
                "probability": None,
                "status": "pending",
                "error": None,
                "elapsed_s": 0.0,
            }

            print(f"  [QUERY] {name} ({cfg['model']}) ...", end=" ", flush=True)
            t0 = time.time()

            try:
                prob = self._query_model(name, prompt)
                elapsed = time.time() - t0
                entry["probability"] = round(prob, 4)
                entry["status"] = "ok"
                entry["elapsed_s"] = round(elapsed, 2)
                successful_probs.append(prob)
                successful_weights.append(cfg["weight"])
                print(f"{prob:.1%} ({elapsed:.1f}s)")
            except requests.Timeout:
                elapsed = time.time() - t0
                entry["status"] = "timeout"
                entry["error"] = f"Timed out after {self.timeout}s"
                entry["elapsed_s"] = round(elapsed, 2)
                print(f"TIMEOUT ({elapsed:.1f}s)")
            except requests.RequestException as exc:
                elapsed = time.time() - t0
                entry["status"] = "error"
                entry["error"] = str(exc)
                entry["elapsed_s"] = round(elapsed, 2)
                print(f"ERROR: {exc}")
            except ValueError as exc:
                elapsed = time.time() - t0
                entry["status"] = "parse_error"
                entry["error"] = str(exc)
                entry["elapsed_s"] = round(elapsed, 2)
                print(f"PARSE ERROR: {exc}")

            model_votes.append(entry)

        # -- Aggregate --------------------------------------------------
        if not successful_probs:
            return {
                "ensemble_prob": None,
                "model_votes": model_votes,
                "confidence": 0.0,
                "agreement": 0.0,
                "error": "All models failed",
            }

        # Renormalize weights
        weight_sum = sum(successful_weights)
        norm_weights = [w / weight_sum for w in successful_weights]

        ensemble_prob = sum(p * w for p, w in zip(successful_probs, norm_weights))

        # Agreement: 1 - spread (range of votes)
        spread = max(successful_probs) - min(successful_probs)
        agreement = 1.0 - spread

        # Confidence: 1 - weighted std deviation (capped at 0..1)
        if len(successful_probs) > 1:
            variance = sum(
                w * (p - ensemble_prob) ** 2
                for p, w in zip(successful_probs, norm_weights)
            )
            std_dev = math.sqrt(variance)
            # Max possible std is 0.5 (one model says 0, another says 1)
            confidence = max(0.0, 1.0 - 2.0 * std_dev)
        else:
            # Single model -- no basis for confidence from agreement
            confidence = 0.5

        return {
            "ensemble_prob": round(ensemble_prob, 4),
            "model_votes": model_votes,
            "confidence": round(confidence, 4),
            "agreement": round(agreement, 4),
        }
    
    def vote_with_context(self, market_title: str, condition_id: str = "", 
                          base_context: str = "") -> dict:
        """
        Vote with automatic context injection from whale data + news.
        
        Enriches the prompt with:
        - Whale activity on this market
        - Insider flags
        - News context (if available)
        - Sports data (for sports markets)
        
        Args:
            market_title: The market title (used for context building)
            condition_id: Polymarket condition ID (for whale lookup)
            base_context: Any additional context to include
        
        Returns:
            Same as vote(), but with enriched context.
        """
        enriched_context = base_context or ""
        
        if HAS_CONTEXT_INJECTOR:
            try:
                injector = ContextInjector()
                context_data = injector.build_context(market_title, condition_id)
                
                # Build enriched context string
                sections = []
                
                # Add whale summary
                whale_ctx = context_data.get("whale_context", {})
                if whale_ctx.get("summary"):
                    sections.append(f"WHALE DATA: {whale_ctx['summary']}")
                
                # Add news
                news = context_data.get("news_context", [])
                if news:
                    headlines = [n["headline"] for n in news[:3]]
                    sections.append(f"NEWS CONTEXT: {'; '.join(headlines)}")
                
                # Add sports factors
                sports = context_data.get("sports_context")
                if sports and sports.get("key_factors"):
                    sections.append(f"SPORTS FACTORS: {'; '.join(sports['key_factors'])}")
                
                if sections:
                    enriched_context = "\n".join(sections)
                    if base_context:
                        enriched_context = f"{enriched_context}\n{base_context}"
                
                injector.close()
                
            except Exception as e:
                print(f"  [WARN] Context injection failed: {e}")
        
        return self.vote(market_title, enriched_context)


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------

def main():
    """Run the ensemble voter from the command line."""
    parser = argparse.ArgumentParser(
        description="Multi-model ensemble voting for probability estimation.",
    )
    parser.add_argument(
        "question",
        help="The prediction question to evaluate.",
    )
    parser.add_argument(
        "--context",
        default="",
        help="Optional context/background information for the models.",
    )
    parser.add_argument(
        "--host",
        default="localhost:11434",
        help="Ollama API host:port (default: localhost:11434).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Per-model timeout in seconds (default: 60).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output raw JSON instead of formatted text.",
    )
    args = parser.parse_args()

    voter = EnsembleVoter(ollama_host=args.host, timeout=args.timeout)

    print("=" * 60)
    print("ENSEMBLE VOTER -- Multi-Model Probability Estimator")
    print("=" * 60)
    print(f"Question: {args.question}")
    if args.context:
        print(f"Context:  {args.context}")
    print(f"Models:   {len(voter.models)}")
    print("-" * 60)

    result = voter.vote(args.question, context=args.context)

    print("-" * 60)

    if args.json_output:
        print(json.dumps(result, indent=2))
        return

    if result["ensemble_prob"] is None:
        print("[FAIL] All models failed. No ensemble probability available.")
        for v in result["model_votes"]:
            print(f"  {v['model_name']}: {v['status']} -- {v.get('error', '')}")
        sys.exit(1)

    prob_pct = result["ensemble_prob"] * 100
    print(f"ENSEMBLE PROBABILITY: {prob_pct:.1f}%")
    print(f"CONFIDENCE:           {result['confidence']:.1%}")
    print(f"AGREEMENT:            {result['agreement']:.1%}")
    print()

    ok_count = sum(1 for v in result["model_votes"] if v["status"] == "ok")
    total = len(result["model_votes"])
    if ok_count < total:
        failed = total - ok_count
        print(f"NOTE: {failed}/{total} model(s) failed; weights renormalized.")

    print("=" * 60)


if __name__ == "__main__":
    main()
