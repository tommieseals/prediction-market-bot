"""
TerminatorBot → MiroFish Connector

Reads high-edge markets from TerminatorBot's SQLite cache,
runs MiroFish dual-platform swarm simulations to predict crowd sentiment,
and returns actionable predictions for position sizing.

Usage:
    python terminator_connector.py                    # Health check
    python terminator_connector.py --test             # Run test simulation with sample data
    python terminator_connector.py --scan             # Scan markets and simulate top opportunities
    python terminator_connector.py --market "title"   # Simulate a specific market by title search
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Paths
TERMINATOR_DIR = Path(r"C:\Users\USER\clawd\TerminatorBot")
MARKET_DB = TERMINATOR_DIR / "data" / "market_cache.db"
PREDICTIONS_LOG = Path(__file__).parent / "terminator_predictions.jsonl"

# Add mirofish-hub to path
sys.path.insert(0, str(Path(__file__).parent))
from mirofish_client import MiroFishClient
from simulation_configs import TERMINATOR_CONFIG


def get_markets_from_db(
    min_volume: float = 1000,
    limit: int = 20,
    platform: str = "kalshi",
    status: str = "open",
) -> list[dict]:
    """
    Read markets directly from TerminatorBot's SQLite cache.

    Returns list of dicts with: market_id, title, yes_price, no_price,
    volume, category, close_date, platform
    """
    if not MARKET_DB.exists():
        print(f"Market database not found: {MARKET_DB}")
        return []

    conn = sqlite3.connect(str(MARKET_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT market_id, title, yes_price, no_price, volume,
                   category, close_date, platform, status
            FROM markets
            WHERE platform = ?
              AND status = ?
              AND volume >= ?
            ORDER BY volume DESC
            LIMIT ?
            """,
            (platform, status, min_volume, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def count_markets() -> int:
    """Count total markets in the database without loading them all."""
    if not MARKET_DB.exists():
        return 0
    conn = sqlite3.connect(str(MARKET_DB))
    try:
        row = conn.execute("SELECT COUNT(*) FROM markets").fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def find_high_edge_markets(
    min_edge: float = 0.05,
    limit: int = 10,
) -> list[dict]:
    """
    Find markets where price deviates significantly from 50/50,
    suggesting potential crowd prediction opportunity.

    High-edge = price very close to 0 or 1 (extreme conviction),
    OR price near 0.5 (maximum uncertainty — good for swarm prediction).
    """
    markets = get_markets_from_db(min_volume=500, limit=200)
    scored = []
    for m in markets:
        yes = m.get("yes_price", 0.5) or 0.5
        # Uncertainty score: how close to 50/50 (higher = more uncertain)
        uncertainty = 1.0 - abs(yes - 0.5) * 2
        # Volume weight
        vol = m.get("volume", 0) or 0
        score = uncertainty * (1 + min(vol / 100000, 1))
        m["uncertainty_score"] = uncertainty
        m["swarm_score"] = score
        scored.append(m)

    scored.sort(key=lambda x: x["swarm_score"], reverse=True)
    return scored[:limit]


def build_seed_text(market: dict) -> str:
    """Build seed text for MiroFish from a market using the config template."""
    yes_price = market.get("yes_price", 0.5) or 0.5
    volume = market.get("volume", 0) or 0

    return TERMINATOR_CONFIG.seed_text_template.format(
        title=market.get("title", "Unknown"),
        platform=market.get("platform", "Unknown"),
        yes_price=yes_price,
        yes_price_pct=f"{yes_price * 100:.1f}",
        no_price=market.get("no_price", "N/A"),
        volume=volume,
        category=market.get("category", "N/A"),
        close_date=market.get("close_date", "N/A"),
    )


def simulate_market(
    client: MiroFishClient,
    market: dict,
    max_rounds: int = 24,
    skip_graph: bool = False,
) -> dict:
    """
    Run a MiroFish dual-platform swarm simulation for a prediction market.

    Args:
        client: MiroFish API client
        market: Market dict from TerminatorBot DB
        max_rounds: Max simulation rounds (24 = full day cycle)
        skip_graph: Skip Zep graph build

    Returns:
        Prediction dict with simulation results
    """
    title = market.get("title", "Unknown Market")
    seed_text = build_seed_text(market)

    sim_requirement = (
        f"Simulate public discourse about the prediction market question: "
        f"'{title}'. Generate diverse agents representing retail bettors, "
        f"political junkies, data scientists, professional traders, news "
        f"commentators, and contrarian thinkers. Have them discuss and debate "
        f"the question as they would on Twitter and Reddit simultaneously. "
        f"Track how opinions shift during the discussion, identify consensus "
        f"and dissent patterns, and surface information asymmetries."
    )

    print(f"\nSimulating: {title}")
    print(f"  Current price: YES={market.get('yes_price', '?')} NO={market.get('no_price', '?')}")
    print(f"  Volume: {market.get('volume', '?')}")

    result = client.run_dual_platform(
        simulation_requirement=sim_requirement,
        seed_text=seed_text,
        project_name=f"TerminatorBot: {title[:50]}",
        max_rounds=max_rounds,
        skip_graph=skip_graph,
    )

    prediction = {
        "connector": "terminator",
        "market_id": market.get("market_id"),
        "market_title": title,
        "market_yes_price": market.get("yes_price"),
        "market_no_price": market.get("no_price"),
        "market_volume": market.get("volume"),
        "market_category": market.get("category"),
        "simulation_id": result.get("simulation_id"),
        "project_id": result.get("project_id"),
        "report_id": result.get("report_id"),
        "steps": result.get("steps"),
        "timestamp": datetime.now().isoformat(),
    }

    return prediction


def log_prediction(prediction: dict) -> None:
    """Append prediction to JSONL log for backtesting."""
    with open(PREDICTIONS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(prediction, ensure_ascii=False) + "\n")
    print(f"  Logged to {PREDICTIONS_LOG}")


def cmd_health(client: MiroFishClient) -> None:
    """Check connectivity."""
    print("Checking MiroFish...")
    if client.health_check():
        print("  MiroFish: ONLINE")
    else:
        print("  MiroFish: OFFLINE (start with: cd mirofish-secure && python backend/run.py)")

    print(f"\nChecking TerminatorBot DB at {MARKET_DB}...")
    if MARKET_DB.exists():
        total = count_markets()
        print(f"  Market DB: {total} markets cached")
        high_edge = find_high_edge_markets(limit=5)
        if high_edge:
            print(f"\n  Top 5 by Swarm Score:")
            for m in high_edge:
                print(f"    {m['swarm_score']:.2f} — {m.get('title', '?')[:60]} "
                      f"(YES={m.get('yes_price', '?')})")
    else:
        print("  Market DB: NOT FOUND")


def cmd_test(client: MiroFishClient) -> None:
    """Run a test simulation with sample data."""
    print("Running test simulation...")
    sample_market = {
        "market_id": "test_001",
        "title": "Will AI regulation be passed in the US by 2027?",
        "yes_price": 0.35,
        "no_price": 0.65,
        "volume": 50000,
        "category": "politics",
        "close_date": "2027-12-31",
        "platform": "test",
    }

    prediction = simulate_market(
        client, sample_market, max_rounds=5, skip_graph=True
    )
    log_prediction(prediction)
    print("\nTest simulation complete!")
    print(json.dumps(prediction, indent=2))


def cmd_scan(client: MiroFishClient, top_n: int = 3) -> None:
    """Scan markets and simulate top opportunities."""
    print(f"Finding top {top_n} high-uncertainty markets...")
    markets = find_high_edge_markets(limit=top_n)

    if not markets:
        print("No markets found in database.")
        return

    for i, market in enumerate(markets, 1):
        print(f"\n{'=' * 60}")
        print(f"Market {i}/{len(markets)}: {market['title'][:80]}")
        print(f"  Uncertainty: {market['uncertainty_score']:.2f}")
        print(f"  Swarm Score: {market['swarm_score']:.2f}")

        try:
            prediction = simulate_market(client, market, skip_graph=False)
            log_prediction(prediction)
        except Exception as e:
            print(f"  FAILED: {e}")

    print(f"\nDone! Predictions logged to {PREDICTIONS_LOG}")


def search_markets_by_title(search: str, limit: int = 20) -> list[dict]:
    """Search markets by title using SQL LIKE (avoids loading all rows)."""
    if not MARKET_DB.exists():
        return []
    conn = sqlite3.connect(str(MARKET_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT market_id, title, yes_price, no_price, volume,
                      category, close_date, platform, status
               FROM markets
               WHERE title LIKE ?
               ORDER BY volume DESC
               LIMIT ?""",
            (f"%{search}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def cmd_market(client: MiroFishClient, search: str) -> None:
    """Simulate a specific market by title search."""
    matches = search_markets_by_title(search)

    if not matches:
        print(f"No markets matching '{search}'")
        return

    print(f"Found {len(matches)} matching markets:")
    for i, m in enumerate(matches[:5], 1):
        print(f"  {i}. {m['title'][:80]} (YES={m.get('yes_price', '?')})")

    market = matches[0]
    prediction = simulate_market(client, market, skip_graph=False)
    log_prediction(prediction)
    print(json.dumps(prediction, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TerminatorBot → MiroFish Connector")
    parser.add_argument("--test", action="store_true", help="Run test simulation")
    parser.add_argument("--scan", action="store_true", help="Scan markets and simulate")
    parser.add_argument("--market", type=str, help="Simulate specific market by title")
    parser.add_argument("--url", default="http://localhost:5001", help="MiroFish URL")
    parser.add_argument("--api-key", default=None, help="MiroFish API key")
    parser.add_argument("--top", type=int, default=3, help="Number of markets to simulate")
    args = parser.parse_args()

    client = MiroFishClient(base_url=args.url, api_key=args.api_key,
                            poll_timeout=1800)

    if args.test:
        cmd_test(client)
    elif args.scan:
        cmd_scan(client, top_n=args.top)
    elif args.market:
        cmd_market(client, args.market)
    else:
        cmd_health(client)
