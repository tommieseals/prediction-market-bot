"""
Domain-Specific Simulation Manager for MiroFish v2.0

Manages domain-specific swarm simulations across sports, politics, and markets.
Each domain has its own seed prompt template, data sources, and refresh schedule.
Uses AutoResearcher for real-world data and MiroFishClient for sim operations.

Usage:
    python domain_sim_manager.py --run sports
    python domain_sim_manager.py --run all
    python domain_sim_manager.py --status
    python domain_sim_manager.py --query sports "Will the Lakers win tonight?"
    python domain_sim_manager.py --refresh
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Sibling imports
from auto_researcher import AutoResearcher
from mirofish_client import MiroFishClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain definitions
# ---------------------------------------------------------------------------

DOMAINS: Dict[str, Dict[str, Any]] = {
    "sports": {
        "seed_prompt": (
            "You are analyzing tonight's professional sports games. "
            "Consider team records, recent performance trends, injury reports, "
            "head-to-head matchups, home/away splits, and momentum. "
            "Evaluate how the betting public and sharp money might view each game. "
            "Discuss likely outcomes, upset potential, and key factors that could "
            "swing results. Use the real-time data below to ground your analysis."
        ),
        "data_sources": ["ESPN scoreboard", "injury reports"],
        "research_queries": [
            ("NBA games tonight", "sports"),
            ("NFL games this week", "sports"),
        ],
        "refresh_hours": 4,
    },
    "politics": {
        "seed_prompt": (
            "You are analyzing current political events and their implications "
            "for prediction markets. Consider recent legislation, executive actions, "
            "polling data, geopolitical developments, and institutional dynamics. "
            "Evaluate how political actors are likely to respond, what coalitions "
            "may form, and what outcomes are most probable. Use the real-time "
            "headlines below to anchor your analysis."
        ),
        "data_sources": ["NewsAPI headlines"],
        "research_queries": [
            ("US politics latest developments", "politics"),
            ("geopolitical news today", "politics"),
        ],
        "refresh_hours": 6,
    },
    "markets": {
        "seed_prompt": (
            "You are analyzing financial and cryptocurrency markets. "
            "Consider current prices, trading volumes, technical indicators, "
            "macroeconomic data (Fed rates, CPI, unemployment), yield curves, "
            "and market sentiment. Evaluate short-term and medium-term "
            "price trajectories, risk factors, and catalysts. Use the real-time "
            "market data below for your analysis."
        ),
        "data_sources": ["CoinGecko prices", "FRED data"],
        "research_queries": [
            ("Bitcoin price prediction", "crypto"),
            ("Federal Reserve rate decision", "macro"),
        ],
        "refresh_hours": 4,
    },
}

# ---------------------------------------------------------------------------
# Database path
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"


# ---------------------------------------------------------------------------
# DomainSimManager
# ---------------------------------------------------------------------------

class DomainSimManager:
    """Manages domain-specific MiroFish swarm simulations.

    Coordinates data gathering (via AutoResearcher), simulation execution
    (via MiroFishClient), and agent interviews for domain-specific queries.
    Tracks simulation state in SQLite so stale domains can be refreshed.
    """

    def __init__(self, mirofish_url: str = "http://localhost:5001"):
        """Initialize the manager.

        Args:
            mirofish_url: Base URL for the MiroFish backend API.
        """
        self.mirofish_url = mirofish_url
        self.client = MiroFishClient(
            base_url=mirofish_url,
            poll_timeout=1800.0,
            request_timeout=180.0,
        )
        self.researcher = AutoResearcher()
        self._init_db()

    def _init_db(self) -> None:
        """Create the domain_sims table if it does not exist."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS domain_sims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL,
                    sim_id TEXT NOT NULL,
                    project_id TEXT,
                    status TEXT NOT NULL DEFAULT 'running',
                    seed_text_preview TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    error_msg TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_domain_sims_domain
                ON domain_sims (domain, created_at DESC)
            """)
            conn.commit()

    # ------------------------------------------------------------------
    # Data gathering
    # ------------------------------------------------------------------

    def _gather_domain_data(self, domain: str) -> str:
        """Use AutoResearcher to fetch fresh real-world data for a domain.

        Args:
            domain: One of the keys in DOMAINS ('sports', 'politics', 'markets').

        Returns:
            Concatenated research text from all configured queries for the domain.
        """
        config = DOMAINS.get(domain)
        if not config:
            raise ValueError(f"Unknown domain: {domain}")

        queries = config.get("research_queries", [])
        sections: List[str] = []

        for market_title, market_type in queries:
            try:
                logger.info("Researching: %s (%s)", market_title, market_type)
                text = self.researcher.research(market_title, market_type)
                if text:
                    sections.append(text)
            except Exception as exc:
                logger.warning(
                    "Research failed for '%s' (%s): %s",
                    market_title, market_type, exc,
                )
                sections.append(f"[Research unavailable: {market_title}]\n")

        if not sections:
            return f"[No research data available for domain '{domain}']\n"

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Simulation lifecycle
    # ------------------------------------------------------------------

    def run_domain_sim(self, domain: str, max_rounds: int = 3) -> str:
        """Run a domain-specific simulation end-to-end.

        Steps:
            1. Gather fresh real-world data via AutoResearcher
            2. Build a rich seed text combining the domain prompt and live data
            3. Call MiroFishClient.run_dual_platform() for the full pipeline
            4. Store the sim_id, domain, and timestamp in SQLite
            5. Return the sim_id

        Args:
            domain: One of 'sports', 'politics', 'markets'.
            max_rounds: Number of simulation rounds (default 3).

        Returns:
            The simulation ID string.

        Raises:
            ValueError: If domain is not recognized.
            RuntimeError: If the MiroFish backend is unreachable.
        """
        config = DOMAINS.get(domain)
        if not config:
            raise ValueError(
                f"Unknown domain '{domain}'. Valid: {list(DOMAINS.keys())}"
            )

        # Health check
        if not self.client.health_check():
            raise RuntimeError(
                f"MiroFish backend not reachable at {self.mirofish_url}"
            )

        print(f"[{domain}] Gathering real-world data...")
        research_data = self._gather_domain_data(domain)
        preview = research_data[:500]

        # Build seed text
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        seed_text = (
            f"DOMAIN: {domain.upper()}\n"
            f"TIMESTAMP: {timestamp}\n"
            f"DATA SOURCES: {', '.join(config['data_sources'])}\n\n"
            f"CONTEXT:\n{config['seed_prompt']}\n\n"
            f"REAL-TIME DATA:\n{research_data}\n"
        )

        sim_requirement = (
            f"Simulate a diverse group of analysts, traders, and domain experts "
            f"discussing {domain} markets. They should debate probabilities, "
            f"share insights from the provided real-time data, challenge each "
            f"other's assumptions, and converge toward consensus predictions."
        )

        project_name = f"DomainSim-{domain}-{timestamp[:10]}"

        # Record start in DB
        created_at = datetime.now(timezone.utc).isoformat()
        row_id = self._insert_sim_record(domain, "pending", "", None, preview, created_at)

        try:
            print(f"[{domain}] Starting MiroFish pipeline (max_rounds={max_rounds})...")
            result = self.client.run_dual_platform(
                simulation_requirement=sim_requirement,
                seed_text=seed_text,
                project_name=project_name,
                max_rounds=max_rounds,
                skip_graph=True,  # Skip Zep graph for speed
            )

            sim_id = result.get("simulation_id", "")
            project_id = result.get("project_id", "")
            status = result.get("status", "unknown")

            # Update DB record
            completed_at = datetime.now(timezone.utc).isoformat()
            self._update_sim_record(row_id, sim_id, project_id, status, completed_at)

            print(f"[{domain}] Simulation complete: {sim_id} (status={status})")
            return sim_id

        except Exception as exc:
            error_msg = str(exc)[:500]
            logger.error("Domain sim failed for '%s': %s", domain, exc)
            self._update_sim_record(
                row_id, "", None, "failed",
                datetime.now(timezone.utc).isoformat(), error_msg,
            )
            raise

    # ------------------------------------------------------------------
    # Agent interviews
    # ------------------------------------------------------------------

    def interview_agents(self, sim_id: str, question: str) -> Dict[str, Any]:
        """Query a completed simulation's agents about a specific question.

        Posts to /api/simulation/interview/all and parses responses for
        probability estimates and confidence levels.

        Args:
            sim_id: The simulation ID to interview.
            question: The question to ask agents.

        Returns:
            Dict with keys:
                probability (float): Aggregate probability estimate 0-1.
                confidence (float): Aggregate confidence 0-1.
                agent_opinions (list): Individual agent responses.
                raw_response (dict): The full API response.
        """
        url = f"{self.mirofish_url}/api/simulation/interview/all"
        payload = {
            "simulation_id": sim_id,
            "question": question,
        }

        try:
            resp = requests.post(url, json=payload, timeout=1800)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as exc:
            logger.error("Interview request failed for sim %s: %s", sim_id, exc)
            return {
                "probability": 0.0,
                "confidence": 0.0,
                "agent_opinions": [],
                "raw_response": {"error": str(exc)},
            }

        # Extract agent opinions from response
        agent_opinions = self._parse_agent_responses(data)
        probability = self._extract_aggregate_probability(agent_opinions)
        confidence = self._extract_aggregate_confidence(agent_opinions)

        return {
            "probability": probability,
            "confidence": confidence,
            "agent_opinions": agent_opinions,
            "raw_response": data,
        }

    def _parse_agent_responses(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract individual agent opinions from interview API response.

        Args:
            data: Raw JSON response from the interview endpoint.

        Returns:
            List of dicts with agent_name, response_text, probability, confidence.
        """
        opinions: List[Dict[str, Any]] = []
        responses = data.get("data", {}).get("responses", [])

        if not responses:
            # Try alternate response shapes
            responses = data.get("responses", [])
        if not responses and isinstance(data.get("data"), list):
            responses = data["data"]

        for resp in responses:
            agent_name = resp.get("agent_name", resp.get("agent", "Unknown"))
            text = resp.get("response", resp.get("text", resp.get("answer", "")))
            prob = self._extract_probability_from_text(text)
            conf = self._extract_confidence_from_text(text)

            opinions.append({
                "agent_name": agent_name,
                "response_text": text,
                "probability": prob,
                "confidence": conf,
            })

        return opinions

    def _extract_probability_from_text(self, text: str) -> Optional[float]:
        """Parse a probability value from free-form agent text.

        Looks for patterns like '65%', '0.65', 'probability: 0.65'.

        Args:
            text: The agent's response text.

        Returns:
            Probability as float 0-1, or None if not found.
        """
        if not text:
            return None

        # Pattern: "probability: 0.XX" or "probability of 0.XX"
        m = re.search(r'probability[:\s]+(?:of\s+)?(\d+(?:\.\d+)?)\s*%?', text, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            return val / 100.0 if val > 1.0 else val

        # Pattern: "XX% chance" or "XX percent"
        m = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:chance|probability|likely|likelihood)?', text, re.IGNORECASE)
        if m:
            return float(m.group(1)) / 100.0

        # Pattern: standalone decimal like "0.65"
        m = re.search(r'\b(0\.\d+)\b', text)
        if m:
            return float(m.group(1))

        return None

    def _extract_confidence_from_text(self, text: str) -> Optional[float]:
        """Parse a confidence value from free-form agent text.

        Args:
            text: The agent's response text.

        Returns:
            Confidence as float 0-1, or None if not found.
        """
        if not text:
            return None

        m = re.search(r'confidence[:\s]+(\d+(?:\.\d+)?)\s*%?', text, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            return val / 100.0 if val > 1.0 else val

        return None

    def _extract_aggregate_probability(self, opinions: List[Dict[str, Any]]) -> float:
        """Compute average probability across all agents that provided one.

        Args:
            opinions: List of parsed agent opinion dicts.

        Returns:
            Average probability (0-1), or 0.0 if no agents provided one.
        """
        probs = [o["probability"] for o in opinions if o.get("probability") is not None]
        if not probs:
            return 0.0
        return round(sum(probs) / len(probs), 4)

    def _extract_aggregate_confidence(self, opinions: List[Dict[str, Any]]) -> float:
        """Compute average confidence across all agents that provided one.

        Args:
            opinions: List of parsed agent opinion dicts.

        Returns:
            Average confidence (0-1), or 0.0 if no agents provided one.
        """
        confs = [o["confidence"] for o in opinions if o.get("confidence") is not None]
        if not confs:
            return 0.0
        return round(sum(confs) / len(confs), 4)

    # ------------------------------------------------------------------
    # Domain queries
    # ------------------------------------------------------------------

    def query_domain(self, domain: str, question: str) -> Dict[str, Any]:
        """Find the latest completed sim for a domain and interview its agents.

        Args:
            domain: One of 'sports', 'politics', 'markets'.
            question: The question to ask the swarm agents.

        Returns:
            Dict with probability, confidence, agent_opinions, sim_id, domain,
            and sim_age_hours.
        """
        sim_record = self._get_latest_sim(domain)
        if not sim_record:
            return {
                "error": f"No completed simulation found for domain '{domain}'",
                "domain": domain,
                "question": question,
            }

        sim_id = sim_record["sim_id"]
        created_at = sim_record["created_at"]

        # Calculate sim age
        try:
            created_dt = datetime.fromisoformat(created_at)
            age_hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600
        except (ValueError, TypeError):
            age_hours = -1.0

        print(f"[{domain}] Interviewing agents in sim {sim_id} (age: {age_hours:.1f}h)...")
        result = self.interview_agents(sim_id, question)
        result["sim_id"] = sim_id
        result["domain"] = domain
        result["sim_age_hours"] = round(age_hours, 2)

        return result

    # ------------------------------------------------------------------
    # Refresh logic
    # ------------------------------------------------------------------

    def refresh_all(self) -> Dict[str, str]:
        """Run simulations for all domains that are stale (past refresh_hours).

        Returns:
            Dict mapping domain name to result string ('refreshed:<sim_id>',
            'fresh', or 'error:<msg>').
        """
        results: Dict[str, str] = {}

        for domain, config in DOMAINS.items():
            refresh_hours = config["refresh_hours"]
            latest = self._get_latest_sim(domain)

            if latest:
                try:
                    created_dt = datetime.fromisoformat(latest["created_at"])
                    age_hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600
                except (ValueError, TypeError):
                    age_hours = float("inf")

                if age_hours < refresh_hours:
                    print(
                        f"[{domain}] Still fresh ({age_hours:.1f}h < {refresh_hours}h). Skipping."
                    )
                    results[domain] = "fresh"
                    continue

            print(f"[{domain}] Stale or missing. Running new simulation...")
            try:
                sim_id = self.run_domain_sim(domain)
                results[domain] = f"refreshed:{sim_id}"
            except Exception as exc:
                logger.error("Refresh failed for '%s': %s", domain, exc)
                results[domain] = f"error:{exc}"

        return results

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Return the status of all domains.

        Returns:
            Dict mapping domain name to status info including last_run,
            sim_id, age_hours, status, and refresh_hours.
        """
        status: Dict[str, Dict[str, Any]] = {}

        for domain, config in DOMAINS.items():
            latest = self._get_latest_sim(domain)
            if latest:
                try:
                    created_dt = datetime.fromisoformat(latest["created_at"])
                    age_hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600
                except (ValueError, TypeError):
                    age_hours = -1.0

                status[domain] = {
                    "last_run": latest["created_at"],
                    "sim_id": latest["sim_id"],
                    "project_id": latest.get("project_id", ""),
                    "status": latest["status"],
                    "age_hours": round(age_hours, 2),
                    "refresh_hours": config["refresh_hours"],
                    "stale": age_hours > config["refresh_hours"],
                }
            else:
                status[domain] = {
                    "last_run": None,
                    "sim_id": None,
                    "project_id": None,
                    "status": "never_run",
                    "age_hours": None,
                    "refresh_hours": config["refresh_hours"],
                    "stale": True,
                }

        return status

    # ------------------------------------------------------------------
    # SQLite helpers
    # ------------------------------------------------------------------

    def _insert_sim_record(
        self,
        domain: str,
        status: str,
        sim_id: str,
        project_id: Optional[str],
        preview: str,
        created_at: str,
    ) -> int:
        """Insert a new simulation record and return its row ID.

        Args:
            domain: Domain name.
            status: Initial status string.
            sim_id: Simulation ID (may be empty initially).
            project_id: Project ID (may be None initially).
            preview: Preview of the seed text.
            created_at: ISO timestamp.

        Returns:
            The row ID of the inserted record.
        """
        with sqlite3.connect(str(DB_PATH)) as conn:
            cur = conn.execute(
                """
                INSERT INTO domain_sims
                    (domain, sim_id, project_id, status, seed_text_preview, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (domain, sim_id, project_id, status, preview, created_at),
            )
            conn.commit()
            return cur.lastrowid

    def _update_sim_record(
        self,
        row_id: int,
        sim_id: str,
        project_id: Optional[str],
        status: str,
        completed_at: str,
        error_msg: Optional[str] = None,
    ) -> None:
        """Update an existing simulation record.

        Args:
            row_id: The row ID to update.
            sim_id: The simulation ID.
            project_id: The project ID.
            status: New status string.
            completed_at: ISO timestamp of completion.
            error_msg: Error message if the sim failed.
        """
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.execute(
                """
                UPDATE domain_sims
                SET sim_id = ?, project_id = ?, status = ?,
                    completed_at = ?, error_msg = ?
                WHERE id = ?
                """,
                (sim_id, project_id, status, completed_at, error_msg, row_id),
            )
            conn.commit()

    def _get_latest_sim(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get the most recent simulation record for a domain.

        Args:
            domain: Domain name.

        Returns:
            Dict with sim record fields, or None if no records exist.
        """
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM domain_sims
                WHERE domain = ? AND status IN ('success', 'partial')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (domain,),
            ).fetchone()

            if row:
                return dict(row)
        return None

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close underlying HTTP sessions."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_status(manager: DomainSimManager) -> None:
    """Print domain status table to stdout."""
    status = manager.get_status()
    print("\n--- Domain Simulation Status ---")
    print(f"{'Domain':<12} {'Status':<12} {'Sim ID':<40} {'Age (h)':<10} {'Stale?':<8}")
    print("-" * 90)
    for domain, info in status.items():
        sim_id = info["sim_id"] or "(none)"
        age = f"{info['age_hours']:.1f}" if info["age_hours"] is not None else "N/A"
        stale = "YES" if info["stale"] else "no"
        st = info["status"]
        print(f"{domain:<12} {st:<12} {sim_id:<40} {age:<10} {stale:<8}")
    print()


def _print_query_result(result: Dict[str, Any]) -> None:
    """Print interview query result to stdout."""
    if "error" in result:
        print(f"\n[ERROR] {result['error']}")
        return

    print(f"\n--- Query Result ---")
    print(f"Domain:      {result.get('domain', '?')}")
    print(f"Sim ID:      {result.get('sim_id', '?')}")
    print(f"Sim Age:     {result.get('sim_age_hours', '?')}h")
    print(f"Probability: {result.get('probability', 0.0):.1%}")
    print(f"Confidence:  {result.get('confidence', 0.0):.1%}")

    opinions = result.get("agent_opinions", [])
    if opinions:
        print(f"\nAgent Opinions ({len(opinions)} agents):")
        for i, op in enumerate(opinions, 1):
            name = op.get("agent_name", "Agent")
            prob = op.get("probability")
            prob_str = f"{prob:.1%}" if prob is not None else "N/A"
            text = op.get("response_text", "")
            # Truncate long responses for display
            if len(text) > 300:
                text = text[:297] + "..."
            print(f"  {i}. [{name}] (prob={prob_str})")
            print(f"     {text}")
    print()


def main() -> None:
    """CLI entry point for the Domain Simulation Manager."""
    parser = argparse.ArgumentParser(
        description="MiroFish Domain Simulation Manager v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python domain_sim_manager.py --run sports\n"
            "  python domain_sim_manager.py --run all\n"
            "  python domain_sim_manager.py --status\n"
            '  python domain_sim_manager.py --query sports "Will the Lakers win?"\n'
            "  python domain_sim_manager.py --refresh\n"
        ),
    )
    parser.add_argument(
        "--run",
        type=str,
        metavar="DOMAIN",
        help="Run a simulation for a domain (sports, politics, markets, or 'all').",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="Number of simulation rounds (default: 3).",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show status of all domain simulations.",
    )
    parser.add_argument(
        "--query",
        nargs=2,
        metavar=("DOMAIN", "QUESTION"),
        help="Query a domain's latest sim with a question.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh all stale domain simulations.",
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:5001",
        help="MiroFish backend URL (default: http://localhost:5001).",
    )

    args = parser.parse_args()

    # Require at least one action
    if not any([args.run, args.status, args.query, args.refresh]):
        parser.print_help()
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    with DomainSimManager(mirofish_url=args.url) as manager:

        if args.status:
            _print_status(manager)

        if args.run:
            domain = args.run.lower().strip()
            if domain == "all":
                for d in DOMAINS:
                    try:
                        print(f"\n{'='*60}")
                        print(f"Running domain: {d}")
                        print(f"{'='*60}")
                        sim_id = manager.run_domain_sim(d, max_rounds=args.rounds)
                        print(f"[{d}] Done. sim_id={sim_id}")
                    except Exception as exc:
                        print(f"[{d}] FAILED: {exc}")
                        logger.exception("Domain sim failed: %s", d)
            elif domain in DOMAINS:
                try:
                    sim_id = manager.run_domain_sim(domain, max_rounds=args.rounds)
                    print(f"[{domain}] Done. sim_id={sim_id}")
                except Exception as exc:
                    print(f"[{domain}] FAILED: {exc}")
                    logger.exception("Domain sim failed: %s", domain)
                    sys.exit(1)
            else:
                print(f"Unknown domain: '{domain}'. Valid: {list(DOMAINS.keys())} or 'all'")
                sys.exit(1)

        if args.query:
            domain, question = args.query
            domain = domain.lower().strip()
            if domain not in DOMAINS:
                print(f"Unknown domain: '{domain}'. Valid: {list(DOMAINS.keys())}")
                sys.exit(1)
            result = manager.query_domain(domain, question)
            _print_query_result(result)

        if args.refresh:
            print("\nRefreshing stale domains...")
            results = manager.refresh_all()
            print("\nRefresh results:")
            for d, outcome in results.items():
                print(f"  {d}: {outcome}")
            print()


if __name__ == "__main__":
    main()
