"""
Oil Prediction Engine → MiroFish Connector

Reads oil/energy markets from TerminatorBot's market cache,
enriches with EIA petroleum data, runs specialized 20-agent
oil simulations, and tracks outcomes for model improvement.

Usage:
    python oil_connector.py                  # Health check
    python oil_connector.py --test           # Run test with sample oil market
    python oil_connector.py --scan           # Scan & simulate top oil markets
    python oil_connector.py --scan --top 5   # Simulate top 5 oil markets
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Paths
TERMINATOR_DIR = Path(r"C:\Users\USER\clawd\TerminatorBot")
MARKET_DB = TERMINATOR_DIR / "data" / "market_cache.db"
PREDICTIONS_LOG = Path(__file__).parent / "oil_predictions.jsonl"
EIA_CACHE = Path(__file__).parent / "data" / "eia_cache.json"

sys.path.insert(0, str(Path(__file__).parent))
from mirofish_client import MiroFishClient
from outcome_tracker import OutcomeTracker

# ── Oil market keywords ─────────────────────────────────────

OIL_KEYWORDS = [
    "oil", "crude", "wti", "brent", "petroleum", "gasoline", "diesel",
    "barrel", "opec", "energy price", "gas price", "fuel",
    "strait of hormuz", "oil embargo", "oil sanction",
]

ENERGY_CATEGORIES = ["oil", "energy", "commodities", "oil-and-energy"]


# ── EIA Data ────────────────────────────────────────────────

def fetch_eia_data(api_key: Optional[str] = None) -> Dict:
    """
    Fetch latest EIA Weekly Petroleum Status Report.
    Returns crude inventory levels + weekly change.
    Free API key: https://www.eia.gov/opendata/register.php
    """
    if not api_key:
        api_key = os.getenv("EIA_API_KEY")

    if not api_key:
        return _eia_fallback()

    try:
        # Weekly US Crude Oil Stocks (excl. SPR)
        url = (
            f"https://api.eia.gov/v2/petroleum/stoc/wstk/data/"
            f"?api_key={api_key}"
            f"&frequency=weekly"
            f"&data[0]=value"
            f"&facets[product][]=EPC0"
            f"&sort[0][column]=period"
            f"&sort[0][direction]=desc"
            f"&length=4"
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        entries = data.get("response", {}).get("data", [])
        if len(entries) >= 2:
            latest = float(entries[0]["value"])
            prior = float(entries[1]["value"])
            change = latest - prior
            return {
                "crude_inventory_mb": round(latest, 1),
                "weekly_change_mb": round(change, 1),
                "period": entries[0].get("period", "unknown"),
                "source": "eia_api",
            }
    except Exception as e:
        print(f"  EIA API error: {e}")

    return _eia_fallback()


def _eia_fallback() -> Dict:
    """Fallback when no API key or API fails."""
    # Try cached data first
    if EIA_CACHE.exists():
        try:
            cached = json.loads(EIA_CACHE.read_text(encoding="utf-8"))
            cached["source"] = "cache"
            return cached
        except Exception:
            pass

    return {
        "crude_inventory_mb": 440.0,
        "weekly_change_mb": -2.1,
        "period": "estimate",
        "source": "fallback",
    }


def fetch_oil_price() -> Dict[str, float]:
    """Fetch current WTI & Brent prices. Best-effort."""
    try:
        # Yahoo Finance chart endpoint (free, no key)
        headers = {"User-Agent": "Mozilla/5.0"}
        wti_resp = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/CL=F",
            headers=headers, timeout=10,
        )
        wti_data = wti_resp.json()
        wti = wti_data["chart"]["result"][0]["meta"]["regularMarketPrice"]

        brent_resp = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/BZ=F",
            headers=headers, timeout=10,
        )
        brent_data = brent_resp.json()
        brent = brent_data["chart"]["result"][0]["meta"]["regularMarketPrice"]

        return {"wti": round(wti, 2), "brent": round(brent, 2), "source": "yahoo"}
    except Exception as e:
        print(f"  Price fetch failed: {e}")
        return {"wti": 108.0, "brent": 112.0, "source": "fallback"}


# ── Market Selection ────────────────────────────────────────

def get_oil_markets(limit: int = 20) -> List[Dict]:
    """
    Filter TerminatorBot's market DB for oil/energy markets.
    Uses keyword matching on title + category filtering.
    """
    if not MARKET_DB.exists():
        print(f"  Market DB not found: {MARKET_DB}")
        return []

    conn = sqlite3.connect(str(MARKET_DB))
    conn.row_factory = sqlite3.Row
    try:
        # Get all open markets with decent volume
        rows = conn.execute(
            """
            SELECT market_id, title, yes_price, no_price, volume,
                   category, close_date, platform, status
            FROM markets
            WHERE status = 'open'
              AND volume >= 500
            ORDER BY volume DESC
            LIMIT 500
            """,
        ).fetchall()

        markets = []
        for row in rows:
            m = dict(row)
            title_lower = m.get("title", "").lower()
            category_lower = (m.get("category") or "").lower()

            # Check if oil/energy related
            is_oil = any(kw in title_lower for kw in OIL_KEYWORDS)
            is_energy_cat = any(cat in category_lower for cat in ENERGY_CATEGORIES)

            if is_oil or is_energy_cat:
                # Score: combine volume + uncertainty
                yes = m.get("yes_price", 0.5) or 0.5
                uncertainty = 1.0 - abs(yes - 0.5) * 2
                vol = m.get("volume", 0) or 0
                m["oil_score"] = uncertainty * (1 + min(vol / 100000, 2))
                m["uncertainty"] = round(uncertainty, 3)
                markets.append(m)

        markets.sort(key=lambda x: x["oil_score"], reverse=True)
        return markets[:limit]
    finally:
        conn.close()


def extract_price_threshold(title: str) -> Optional[float]:
    """Extract dollar price from market title like '$120 or above'."""
    match = re.search(r"\$(\d+(?:\.\d+)?)", title)
    return float(match.group(1)) if match else None


# ── Seed Text Builder ───────────────────────────────────────

OIL_SEED_TEMPLATE = """OIL MARKET INTELLIGENCE — {timestamp}
============================================================

PREDICTION TARGET:
  Market: {title}
  Platform: {platform}
  Current Odds: YES {yes_price_pct}% / NO {no_price_pct}%
  Volume: ${volume:,.0f}
  Closes: {close_date}

LIVE MARKET DATA:
  WTI Crude: ${wti_price:.2f}/barrel
  Brent Crude: ${brent_price:.2f}/barrel
  Spread: ${spread:.2f}
  Weekly Inventory Change: {inventory_change:+.1f}M barrels ({inventory_signal})
  Crude Stocks: {crude_stocks:.1f}M barrels
  Data Source: {data_source}

GEOPOLITICAL CONTEXT:
  Iran conflict active — Strait of Hormuz supply risk elevated
  OPEC+ production discipline holding
  US shale response limited by capital discipline

AGENT ROSTER (20 Specialized Oil Analysts):
  1-2.  Petroleum Geologist + Shale Production Expert
  3-4.  Geopolitical Risk Analyst + Middle East Specialist
  5-6.  Macro Strategist + Currency/Dollar Analyst
  7-8.  Technical Trader (Momentum) + Options Market Maker
  9-10. Refinery Operations + Pipeline Infrastructure Expert
  11-12. OPEC Watcher + Emerging Market Demand Analyst
  13-14. EIA Inventory Specialist + Commodity Quant
  15-16. Energy Policy Advisor + Alt Energy Analyst
  17-18. Shipping/Tanker Tracker + Weather Forecaster
  19-20. Hedge Fund Positioning Analyst + Risk Aggregator

SIMULATION INSTRUCTIONS:
  Agents debate this oil market question across Twitter and Reddit.
  Track consensus formation, identify dissent, surface asymmetries.
  Final output: probability estimate + confidence level + key drivers.
"""


def build_oil_seed_text(market: Dict, prices: Dict, eia: Dict) -> str:
    """Build enriched seed text for oil simulation."""
    yes = market.get("yes_price", 0.5) or 0.5
    no = market.get("no_price", 0.5) or 0.5
    volume = market.get("volume", 0) or 0
    wti = prices.get("wti", 108.0)
    brent = prices.get("brent", 112.0)
    inv_change = eia.get("weekly_change_mb", 0)

    if inv_change < -2:
        inv_signal = "BULLISH — large draw"
    elif inv_change < 0:
        inv_signal = "mildly bullish — draw"
    elif inv_change > 2:
        inv_signal = "BEARISH — large build"
    elif inv_change > 0:
        inv_signal = "mildly bearish — build"
    else:
        inv_signal = "neutral"

    return OIL_SEED_TEMPLATE.format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        title=market.get("title", "Unknown"),
        platform=market.get("platform", "kalshi"),
        yes_price_pct=f"{yes * 100:.1f}",
        no_price_pct=f"{no * 100:.1f}",
        volume=volume,
        close_date=market.get("close_date", "N/A"),
        wti_price=wti,
        brent_price=brent,
        spread=brent - wti,
        inventory_change=inv_change,
        inventory_signal=inv_signal,
        crude_stocks=eia.get("crude_inventory_mb", 440),
        data_source=eia.get("source", "unknown"),
    )


OIL_SIM_REQUIREMENT = (
    "Simulate expert oil market discourse about the prediction: '{title}'. "
    "Generate 20 specialized agents: petroleum geologists, geopolitical "
    "risk analysts, macro strategists, technical traders, refinery managers, "
    "OPEC watchers, inventory specialists, shipping trackers, and quant "
    "analysts. Have them debate on Twitter and Reddit simultaneously, "
    "tracking consensus formation and identifying information asymmetries "
    "in the oil market."
)


# ── Simulation ──────────────────────────────────────────────

def simulate_oil_market(
    client: MiroFishClient,
    market: Dict,
    prices: Dict,
    eia_data: Dict,
    max_rounds: int = 24,
    skip_graph: bool = False,
) -> Dict:
    """Run MiroFish simulation for an oil market."""
    title = market.get("title", "Unknown Oil Market")
    seed_text = build_oil_seed_text(market, prices, eia_data)

    sim_req = OIL_SIM_REQUIREMENT.format(title=title[:200])

    print(f"\n  Simulating: {title[:70]}")
    print(f"  Odds: YES={market.get('yes_price', '?')} "
          f"NO={market.get('no_price', '?')} "
          f"Vol=${market.get('volume', 0):,.0f}")
    print(f"  WTI=${prices.get('wti', '?')} Brent=${prices.get('brent', '?')} "
          f"Inventory={eia_data.get('weekly_change_mb', '?'):+.1f}M bbl")

    result = client.run_dual_platform(
        simulation_requirement=sim_req,
        seed_text=seed_text,
        project_name=f"Oil: {title[:50]}",
        max_rounds=max_rounds,
        skip_graph=skip_graph,
    )

    prediction = {
        "connector": "oil",
        "market_id": market.get("market_id"),
        "market_title": title,
        "market_yes_price": market.get("yes_price"),
        "market_no_price": market.get("no_price"),
        "market_volume": market.get("volume"),
        "market_category": market.get("category"),
        "price_threshold": extract_price_threshold(title),
        "wti_at_prediction": prices.get("wti"),
        "brent_at_prediction": prices.get("brent"),
        "eia_inventory_change": eia_data.get("weekly_change_mb"),
        "simulation_id": result.get("simulation_id"),
        "project_id": result.get("project_id"),
        "report_id": result.get("report_id"),
        "steps": result.get("steps"),
        "timestamp": datetime.now().isoformat(),
    }

    return prediction


def log_prediction(prediction: Dict) -> None:
    """Append prediction to JSONL log."""
    with open(PREDICTIONS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(prediction, ensure_ascii=False) + "\n")
    print(f"  Logged to {PREDICTIONS_LOG}")


# ── Commands ────────────────────────────────────────────────

def cmd_health(client: MiroFishClient) -> None:
    """Check connectivity + show oil market summary."""
    print("=== Oil Prediction Engine — Health Check ===\n")

    # MiroFish
    print("MiroFish Backend:")
    if client.health_check():
        print("  Status: ONLINE")
    else:
        print("  Status: OFFLINE")

    # Market DB
    print(f"\nTerminatorBot Market DB ({MARKET_DB}):")
    oil_markets = get_oil_markets(limit=10)
    if oil_markets:
        print(f"  Oil/Energy markets found: {len(oil_markets)}")
        print(f"\n  Top Oil Markets by Score:")
        for i, m in enumerate(oil_markets[:5], 1):
            print(f"    {i}. {m['title'][:65]}")
            print(f"       YES={m.get('yes_price', '?')} "
                  f"Vol=${m.get('volume', 0):,.0f} "
                  f"Score={m['oil_score']:.2f}")
    else:
        print("  No oil markets found (is TerminatorBot DB populated?)")

    # Prices
    print("\nLive Prices:")
    prices = fetch_oil_price()
    print(f"  WTI: ${prices['wti']:.2f} ({prices['source']})")
    print(f"  Brent: ${prices['brent']:.2f}")

    # EIA
    print("\nEIA Inventory Data:")
    eia = fetch_eia_data()
    print(f"  Crude Stocks: {eia['crude_inventory_mb']:.1f}M barrels")
    print(f"  Weekly Change: {eia['weekly_change_mb']:+.1f}M barrels")
    print(f"  Source: {eia['source']}")

    # Outcomes
    print("\nOutcome Tracker:")
    tracker = OutcomeTracker()
    print(tracker.summary())


def cmd_test(client: MiroFishClient) -> None:
    """Run test simulation with a sample oil market."""
    print("Running oil test simulation...\n")

    sample_market = {
        "market_id": "oil_test_001",
        "title": "Will WTI crude oil close above $120 this week?",
        "yes_price": 0.45,
        "no_price": 0.55,
        "volume": 250000,
        "category": "oil-and-energy",
        "close_date": "2026-03-27",
        "platform": "kalshi",
    }

    prices = fetch_oil_price()
    eia = fetch_eia_data()

    prediction = simulate_oil_market(
        client, sample_market, prices, eia,
        max_rounds=5, skip_graph=True,
    )
    log_prediction(prediction)

    # Track in outcome DB
    tracker = OutcomeTracker()
    tracker.record_prediction(
        prediction_id=prediction.get("simulation_id", "test"),
        market_id=sample_market["market_id"],
        connector="oil",
        market_title=sample_market["title"],
        predicted_probability=sample_market["yes_price"],
        market_price=sample_market["yes_price"],
        model_version="oil_v1_test",
        agent_count=5,
        metadata={"wti": prices["wti"], "brent": prices["brent"]},
    )

    print("\nTest complete!")
    print(json.dumps(prediction, indent=2, default=str))


def cmd_scan(client: MiroFishClient, top_n: int = 3) -> None:
    """Scan oil markets and simulate top opportunities."""
    print(f"Scanning for top {top_n} oil markets...\n")

    markets = get_oil_markets(limit=top_n)
    if not markets:
        print("No oil markets found in TerminatorBot DB.")
        print("Run TerminatorBot first to populate the market cache.")
        return

    prices = fetch_oil_price()
    eia = fetch_eia_data()
    tracker = OutcomeTracker()

    print(f"Live: WTI=${prices['wti']:.2f} Brent=${prices['brent']:.2f} "
          f"Inv={eia['weekly_change_mb']:+.1f}M bbl\n")

    for i, market in enumerate(markets, 1):
        print(f"{'=' * 60}")
        print(f"Oil Market {i}/{len(markets)}: {market['title'][:70]}")
        print(f"  Score: {market['oil_score']:.2f} "
              f"Uncertainty: {market['uncertainty']:.1%}")

        try:
            prediction = simulate_oil_market(
                client, market, prices, eia, skip_graph=False,
            )
            log_prediction(prediction)

            # Track outcome
            tracker.record_prediction(
                prediction_id=prediction.get("simulation_id", f"oil_{i}"),
                market_id=market["market_id"],
                connector="oil",
                market_title=market["title"],
                predicted_probability=market.get("yes_price", 0.5),
                market_price=market.get("yes_price", 0.5),
                model_version="oil_v1",
                agent_count=20,
                metadata={
                    "wti": prices["wti"],
                    "brent": prices["brent"],
                    "eia_change": eia["weekly_change_mb"],
                },
            )
        except Exception as e:
            print(f"  FAILED: {e}")

    print(f"\n{'=' * 60}")
    print(f"Done! {len(markets)} oil predictions logged.")
    print(f"Predictions: {PREDICTIONS_LOG}")
    print(f"\n{tracker.summary()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Oil Prediction Engine → MiroFish Connector"
    )
    parser.add_argument("--test", action="store_true", help="Run test simulation")
    parser.add_argument("--scan", action="store_true", help="Scan & simulate oil markets")
    parser.add_argument("--url", default="http://localhost:5001", help="MiroFish URL")
    parser.add_argument("--api-key", default=None, help="MiroFish API key")
    parser.add_argument("--top", type=int, default=3, help="Number of markets")
    args = parser.parse_args()

    client = MiroFishClient(
        base_url=args.url, api_key=args.api_key,
        poll_timeout=1800, request_timeout=300,
    )

    if args.test:
        cmd_test(client)
    elif args.scan:
        cmd_scan(client, top_n=args.top)
    else:
        cmd_health(client)
