"""
Arbitrage Pharma → MiroFish Connector

Reads biotech opportunities from Arbitrage Pharma's pipeline,
runs MiroFish swarm simulations to gauge industry sentiment
on distressed orphan drug acquisitions.

Usage:
    python pharma_connector.py                     # Health check
    python pharma_connector.py --test              # Test with sample data
    python pharma_connector.py --scan              # Simulate top opportunities
    python pharma_connector.py --asset "NNZ-2591"  # Simulate specific asset
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Paths
PHARMA_DIR = Path(r"C:\Users\USER\clawd\arbitrage-pharma")
OPPORTUNITIES_FILE = PHARMA_DIR / "data" / "opportunities.json"
LATEST_SCAN_FILE = PHARMA_DIR / "latest_scan.json"
PREDICTIONS_LOG = Path(__file__).parent / "pharma_predictions.jsonl"

sys.path.insert(0, str(Path(__file__).parent))
from mirofish_client import MiroFishClient
from simulation_configs import PHARMA_CONFIG


def load_opportunities() -> list[dict]:
    """Load opportunities from Arbitrage Pharma's data."""
    if OPPORTUNITIES_FILE.exists():
        with open(OPPORTUNITIES_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("opportunities", [data])
    return []


def load_latest_scan() -> dict:
    """Load the latest pipeline scan data."""
    if LATEST_SCAN_FILE.exists():
        with open(LATEST_SCAN_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data:
            # If it's a list, try to find a dict with pipeline info
            for item in data:
                if isinstance(item, dict) and "total_pipeline_value" in item:
                    return item
            return data[0] if isinstance(data[0], dict) else {}
    return {}


def get_top_opportunities(limit: int = 5, min_score: float = 7.0) -> list[dict]:
    """Get top opportunities ranked by arbitrage score."""
    opps = load_opportunities()
    scored = [o for o in opps if (o.get("arbitrage_score") or 0) >= min_score]
    scored.sort(key=lambda x: x.get("arbitrage_score", 0), reverse=True)
    return scored[:limit]


def build_seed_text(opp: dict, pipeline_count: int = 0) -> str:
    """Build seed text for MiroFish from an opportunity."""
    scan = load_latest_scan()
    pipeline_value = scan.get("total_pipeline_value", {})

    # Competitive intel
    comp = opp.get("competitive_intel", {})
    comp_text = "None available"
    if comp:
        comp_text = (
            f"Date: {comp.get('date', 'N/A')}\n"
            f"Event: {comp.get('event', 'N/A')}\n"
            f"Impact: {comp.get('impact', 'N/A')}\n"
            f"Source: {comp.get('source', 'N/A')}"
        )

    market_est = opp.get("market_estimate", {})
    acq_est = opp.get("acquisition_cost_estimate", {})

    return PHARMA_CONFIG.seed_text_template.format(
        asset_name=opp.get("asset_name", "Unknown"),
        company=opp.get("company", "Unknown"),
        indication=opp.get("indication", "Unknown"),
        phase=opp.get("phase", "Unknown"),
        trial_id=opp.get("trial_id", "N/A"),
        status=opp.get("status", "Unknown"),
        why_stopped=opp.get("why_stopped", "Unknown"),
        market_low=market_est.get("low", 0),
        market_high=market_est.get("high", 0),
        acq_low=acq_est.get("low", 0),
        acq_high=acq_est.get("high", 0),
        success_prob=opp.get("success_probability", 0),
        weighted_value=opp.get("weighted_value", 0),
        arb_score=opp.get("arbitrage_score", 0),
        competitive_intel=comp_text,
        pipeline_count=pipeline_count,
        pipeline_value=pipeline_value.get("probability_weighted", 0),
        priority=opp.get("priority", "unknown"),
        outreach_status=opp.get("action_status", "unknown"),
    )


def simulate_opportunity(
    client: MiroFishClient,
    opp: dict,
    max_rounds: int = 24,
    skip_graph: bool = False,
    pipeline_count: int = 0,
) -> dict:
    """Run a MiroFish dual-platform simulation for a pharma opportunity."""
    title = opp.get("asset_name", "Unknown")
    company = opp.get("company", "Unknown")
    seed_text = build_seed_text(opp, pipeline_count=pipeline_count)

    sim_req = (
        f"Simulate industry discourse about acquiring the distressed drug asset "
        f"'{title}' from {company}. The drug was {opp.get('status', 'terminated')} "
        f"for indication: {opp.get('indication', 'unknown')}. "
        f"Generate pharma BD executives, biotech analysts, regulatory experts, "
        f"patient advocates, and investors discussing the deal viability, regulatory "
        f"pathway, competitive landscape, and fair valuation."
    )

    print(f"\nSimulating: {title} ({company})")
    print(f"  Indication: {opp.get('indication', '?')}")
    print(f"  Arbitrage Score: {opp.get('arbitrage_score', '?')}/10")
    print(f"  Weighted Value: ${opp.get('weighted_value', 0):,.0f}")

    result = client.run_dual_platform(
        simulation_requirement=sim_req,
        seed_text=seed_text,
        project_name=f"Pharma: {title} ({company})",
        max_rounds=max_rounds,
        skip_graph=skip_graph,
    )

    prediction = {
        "connector": "pharma",
        "asset_name": title,
        "company": company,
        "indication": opp.get("indication"),
        "arbitrage_score": opp.get("arbitrage_score"),
        "weighted_value": opp.get("weighted_value"),
        "simulation_id": result.get("simulation_id"),
        "project_id": result.get("project_id"),
        "report_id": result.get("report_id"),
        "steps": result.get("steps"),
        "timestamp": datetime.now().isoformat(),
    }
    return prediction


def log_prediction(prediction: dict) -> None:
    """Append prediction to JSONL log."""
    with open(PREDICTIONS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(prediction, ensure_ascii=False) + "\n")
    print(f"  Logged to {PREDICTIONS_LOG}")


def cmd_health(client: MiroFishClient) -> None:
    """Check connectivity."""
    print("Checking MiroFish...")
    if client.health_check():
        print("  MiroFish: ONLINE")
    else:
        print("  MiroFish: OFFLINE")

    print(f"\nChecking Arbitrage Pharma data...")
    opps = load_opportunities()
    print(f"  Opportunities: {len(opps)}")
    scan = load_latest_scan()
    pipeline = scan.get("total_pipeline_value", {})
    print(f"  Pipeline Value: ${pipeline.get('probability_weighted', 0):,.0f}")
    top = get_top_opportunities(limit=5)
    if top:
        print(f"\n  Top 5 by Arbitrage Score:")
        for o in top:
            print(f"    {o.get('arbitrage_score', 0)}/10 — {o.get('asset_name')} "
                  f"({o.get('company')}) — {o.get('indication')}")


def cmd_test(client: MiroFishClient) -> None:
    """Run test simulation with sample data."""
    sample = {
        "asset_name": "TEST-DRUG-001",
        "company": "TestPharma Inc",
        "indication": "Rare Autoimmune Disorder",
        "phase": "Phase 2",
        "trial_id": "NCT00000001",
        "status": "terminated",
        "why_stopped": "Sponsor strategic reprioritization (not safety)",
        "arbitrage_score": 8.5,
        "market_estimate": {"low": 2_000_000_000, "high": 5_000_000_000},
        "acquisition_cost_estimate": {"low": 5_000_000, "high": 15_000_000},
        "success_probability": 0.15,
        "weighted_value": 750_000_000,
        "priority": "high",
        "action_status": "research",
        "competitive_intel": {
            "date": "2026-03-01",
            "event": "Competitor trial paused for safety concerns",
            "impact": "POSITIVE - competitive landscape cleared",
            "source": "BioPharma Dive",
        },
    }
    prediction = simulate_opportunity(client, sample, max_rounds=5, skip_graph=True,
                                      pipeline_count=1)
    log_prediction(prediction)
    print("\nTest complete!")
    print(json.dumps(prediction, indent=2))


def cmd_scan(client: MiroFishClient, top_n: int = 3) -> None:
    """Scan opportunities and simulate top assets."""
    print(f"Finding top {top_n} opportunities by arbitrage score...")
    opps = get_top_opportunities(limit=top_n)
    all_opps_count = len(load_opportunities())

    if not opps:
        print("No opportunities found.")
        return

    for i, opp in enumerate(opps, 1):
        print(f"\n{'=' * 60}")
        print(f"Opportunity {i}/{len(opps)}: {opp.get('asset_name')} ({opp.get('company')})")
        try:
            prediction = simulate_opportunity(client, opp, skip_graph=False,
                                                  pipeline_count=all_opps_count)
            log_prediction(prediction)
        except Exception as e:
            print(f"  FAILED: {e}")

    print(f"\nDone! Predictions logged to {PREDICTIONS_LOG}")


def cmd_asset(client: MiroFishClient, search: str) -> None:
    """Simulate a specific asset by name search."""
    opps = load_opportunities()
    pipeline_count = len(opps)
    matches = [o for o in opps if search.lower() in (o.get("asset_name", "") + " " + o.get("company", "")).lower()]

    if not matches:
        print(f"No assets matching '{search}'")
        return

    print(f"Found {len(matches)} matching assets:")
    for i, o in enumerate(matches[:5], 1):
        print(f"  {i}. {o.get('asset_name')} ({o.get('company')}) — Score: {o.get('arbitrage_score', '?')}/10")

    prediction = simulate_opportunity(client, matches[0], skip_graph=False,
                                      pipeline_count=pipeline_count)
    log_prediction(prediction)
    print(json.dumps(prediction, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Arbitrage Pharma → MiroFish Connector")
    parser.add_argument("--test", action="store_true", help="Run test simulation")
    parser.add_argument("--scan", action="store_true", help="Simulate top opportunities")
    parser.add_argument("--asset", type=str, help="Simulate specific asset by name")
    parser.add_argument("--url", default="http://localhost:5001", help="MiroFish URL")
    parser.add_argument("--api-key", default=None, help="MiroFish API key")
    parser.add_argument("--top", type=int, default=3, help="Number of assets to simulate")
    args = parser.parse_args()

    client = MiroFishClient(base_url=args.url, api_key=args.api_key,
                            poll_timeout=1800)

    if args.test:
        cmd_test(client)
    elif args.scan:
        cmd_scan(client, top_n=args.top)
    elif args.asset:
        cmd_asset(client, args.asset)
    else:
        cmd_health(client)
