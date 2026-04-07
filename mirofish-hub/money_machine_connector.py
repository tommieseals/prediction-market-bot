"""
Money Machine → MiroFish Connector

Reads freelance income stream data from the Money Machine tracker,
runs MiroFish swarm simulations to analyze freelance market demand,
pricing dynamics, and optimal service positioning.

Usage:
    python money_machine_connector.py                        # Health check
    python money_machine_connector.py --test                 # Test with sample data
    python money_machine_connector.py --scan                 # Simulate top income streams
    python money_machine_connector.py --service "automation" # Simulate specific service
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Paths
MEMORY_DIR = Path(r"C:\Users\USER\clawd\memory")
TRACKER_FILE = MEMORY_DIR / "money-machine-tracker.md"
FIVERR_DIR = Path(r"C:\Users\USER\clawd\fiverr")
GIG_DESCRIPTIONS = FIVERR_DIR / "GIG_DESCRIPTIONS.md"
PREDICTIONS_LOG = Path(__file__).parent / "money_machine_predictions.jsonl"

sys.path.insert(0, str(Path(__file__).parent))
from mirofish_client import MiroFishClient
from simulation_configs import MONEY_MACHINE_CONFIG

# Structured income streams (derived from tracker analysis)
INCOME_STREAMS = [
    {
        "name": "AI-Powered Business Automation",
        "platforms": ["Fiverr", "Upwork", "Direct"],
        "price_range": "$150-$500/project",
        "hourly_equiv": "$75-150/hr",
        "category": "automation",
        "skills": ["Python", "APIs", "OpenAI/Claude", "Selenium", "Zapier"],
        "demand": "high",
        "competition": "medium",
    },
    {
        "name": "Python Scripts & Data Analysis",
        "platforms": ["Fiverr", "Upwork", "Freelancer"],
        "price_range": "$50-$200/project",
        "hourly_equiv": "$50-100/hr",
        "category": "development",
        "skills": ["Python", "Pandas", "Web Scraping", "ML", "Data Viz"],
        "demand": "very_high",
        "competition": "high",
    },
    {
        "name": "Research Reports & Market Analysis",
        "platforms": ["Fiverr", "Upwork", "Direct"],
        "price_range": "$100-$500/report",
        "hourly_equiv": "$50-100/hr",
        "category": "research",
        "skills": ["Research", "Writing", "Data Analysis", "Due Diligence"],
        "demand": "high",
        "competition": "medium",
    },
    {
        "name": "Trading Bot & Crypto Automation",
        "platforms": ["Fiverr", "Upwork", "Direct"],
        "price_range": "$300-$1000/project",
        "hourly_equiv": "$100-200/hr",
        "category": "trading",
        "skills": ["Python", "Tradier/Alpaca API", "Backtesting", "Risk Mgmt"],
        "demand": "high",
        "competition": "low",
    },
    {
        "name": "AI Training Data (Scale/Outlier/Prolific)",
        "platforms": ["Scale AI", "Outlier", "Remotasks", "Prolific"],
        "price_range": "$15-30/hr",
        "hourly_equiv": "$15-30/hr",
        "category": "microtask",
        "skills": ["AI Evaluation", "Data Labeling", "Quality Assurance"],
        "demand": "very_high",
        "competition": "medium",
    },
    {
        "name": "Bug Bounty Hunting",
        "platforms": ["HackerOne", "Bugcrowd", "Intigriti"],
        "price_range": "$50-$500+/bug",
        "hourly_equiv": "Variable",
        "category": "security",
        "skills": ["Web Security", "Pentesting", "Burp Suite", "OWASP"],
        "demand": "high",
        "competition": "high",
    },
    {
        "name": "Discord/Telegram Bot Services",
        "platforms": ["Fiverr", "Upwork", "Direct"],
        "price_range": "$100-$500/bot",
        "hourly_equiv": "$50-100/hr",
        "category": "automation",
        "skills": ["Python", "Discord.py", "Telegram Bot API", "Webhooks"],
        "demand": "high",
        "competition": "medium",
    },
    {
        "name": "Technical Document Writing",
        "platforms": ["Upwork", "Direct"],
        "price_range": "$50-$200/doc, $500-$1500 full docs",
        "hourly_equiv": "$50-100/hr",
        "category": "writing",
        "skills": ["Technical Writing", "API Docs", "Markdown", "Diagrams"],
        "demand": "medium",
        "competition": "low",
    },
]


def load_tracker() -> str:
    """Load the money machine tracker markdown."""
    if TRACKER_FILE.exists():
        return TRACKER_FILE.read_text(encoding="utf-8")
    return ""


def get_streams_by_category(category: str) -> list[dict]:
    """Filter income streams by category."""
    return [s for s in INCOME_STREAMS if s["category"] == category]


def get_top_streams(limit: int = 5) -> list[dict]:
    """Get top streams by estimated demand/competition ratio."""
    demand_score = {"very_high": 4, "high": 3, "medium": 2, "low": 1}
    comp_score = {"low": 3, "medium": 2, "high": 1}

    scored = []
    for s in INCOME_STREAMS:
        d = demand_score.get(s["demand"], 2)
        c = comp_score.get(s["competition"], 2)
        entry = dict(s)
        entry["opportunity_score"] = d * c
        scored.append(entry)

    scored.sort(key=lambda x: x["opportunity_score"], reverse=True)
    return scored[:limit]


def format_streams_text(streams: list[dict]) -> str:
    """Format income streams for seed text."""
    lines = []
    for i, s in enumerate(streams, 1):
        lines.append(
            f"{i}. {s['name']}\n"
            f"   Platforms: {', '.join(s['platforms'])}\n"
            f"   Pricing: {s['price_range']}\n"
            f"   Demand: {s['demand'].replace('_', ' ').title()} | "
            f"Competition: {s['competition'].title()}\n"
            f"   Skills: {', '.join(s['skills'])}"
        )
    return "\n".join(lines)


def build_seed_text(focus_stream: dict) -> str:
    """Build seed text for MiroFish from Money Machine data."""
    all_streams = get_top_streams(limit=8)
    streams_text = format_streams_text(all_streams)

    trends = [
        "AI automation services seeing 300% demand increase YoY on Upwork",
        "Clients willing to pay premium for 'AI + human oversight' workflows",
        "Micro-task platforms (Scale AI, Outlier) paying $25-40/hr for AI evaluation",
    ]

    return MONEY_MACHINE_CONFIG.seed_text_template.format(
        stream_count=len(INCOME_STREAMS),
        current_status="ACTIVE — Building pipeline across all platforms",
        streams_text=streams_text,
        market_state="rapidly expanding with AI tools creating new service categories",
        trend_1=trends[0],
        trend_2=trends[1],
        trend_3=trends[2],
    )


def simulate_service(
    client: MiroFishClient,
    stream: dict,
    max_rounds: int = 24,
    skip_graph: bool = False,
) -> dict:
    """Run a MiroFish dual-platform simulation for a service niche."""
    name = stream["name"]
    seed_text = build_seed_text(stream)

    sim_req = (
        f"Simulate discourse about the freelance market for '{name}'. "
        f"Generate freelancers, clients, agency owners, platform moderators, "
        f"and career coaches discussing: pricing strategies, platform algorithms, "
        f"client acquisition, AI tool impact on rates, and market saturation. "
        f"Model demand dynamics and identify underserved niches."
    )

    print(f"\nSimulating: {name}")
    print(f"  Pricing: {stream['price_range']}")
    print(f"  Demand: {stream['demand']} | Competition: {stream['competition']}")

    result = client.run_dual_platform(
        simulation_requirement=sim_req,
        seed_text=seed_text,
        project_name=f"Money Machine: {name[:40]}",
        max_rounds=max_rounds,
        skip_graph=skip_graph,
    )

    prediction = {
        "connector": "money_machine",
        "service_name": name,
        "category": stream["category"],
        "price_range": stream["price_range"],
        "demand": stream["demand"],
        "competition": stream["competition"],
        "simulation_id": result.get("simulation_id"),
        "project_id": result.get("project_id"),
        "report_id": result.get("report_id"),
        "steps": result.get("steps"),
        "timestamp": datetime.now().isoformat(),
    }
    return prediction


def log_prediction(prediction: dict) -> None:
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

    print(f"\nMoney Machine Status:")
    print(f"  Income Streams Configured: {len(INCOME_STREAMS)}")
    print(f"  Tracker: {'FOUND' if TRACKER_FILE.exists() else 'NOT FOUND'}")
    print(f"  Fiverr Gigs: {'FOUND' if GIG_DESCRIPTIONS.exists() else 'NOT FOUND'}")

    print(f"\n  Top Opportunities (demand/competition ratio):")
    for s in get_top_streams(limit=5):
        print(f"    Score {s['opportunity_score']}: {s['name']} — {s['price_range']}")


def cmd_test(client: MiroFishClient) -> None:
    """Run test simulation."""
    stream = INCOME_STREAMS[0]  # AI Automation
    prediction = simulate_service(client, stream, max_rounds=5, skip_graph=True)
    log_prediction(prediction)
    print("\nTest complete!")
    print(json.dumps(prediction, indent=2))


def cmd_scan(client: MiroFishClient, top_n: int = 3) -> None:
    """Simulate top service niches."""
    streams = get_top_streams(limit=top_n)

    for i, stream in enumerate(streams, 1):
        print(f"\n{'=' * 60}")
        print(f"Service {i}/{len(streams)}: {stream['name']}")
        try:
            prediction = simulate_service(client, stream, skip_graph=False)
            log_prediction(prediction)
        except Exception as e:
            print(f"  FAILED: {e}")

    print(f"\nDone! Predictions logged to {PREDICTIONS_LOG}")


def cmd_service(client: MiroFishClient, search: str) -> None:
    """Simulate a specific service."""
    matches = [s for s in INCOME_STREAMS if search.lower() in s["name"].lower()
               or search.lower() in s["category"].lower()]

    if not matches:
        print(f"No services matching '{search}'")
        print(f"Available: {', '.join(s['name'] for s in INCOME_STREAMS)}")
        return

    print(f"Found {len(matches)} matches. Using: {matches[0]['name']}")
    prediction = simulate_service(client, matches[0], skip_graph=False)
    log_prediction(prediction)
    print(json.dumps(prediction, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Money Machine → MiroFish Connector")
    parser.add_argument("--test", action="store_true", help="Run test simulation")
    parser.add_argument("--scan", action="store_true", help="Simulate top services")
    parser.add_argument("--service", type=str, help="Simulate specific service")
    parser.add_argument("--url", default="http://localhost:5001", help="MiroFish URL")
    parser.add_argument("--api-key", default=None, help="MiroFish API key")
    parser.add_argument("--top", type=int, default=3, help="Number of services to simulate")
    args = parser.parse_args()

    client = MiroFishClient(base_url=args.url, api_key=args.api_key,
                            poll_timeout=1800)

    if args.test:
        cmd_test(client)
    elif args.scan:
        cmd_scan(client, top_n=args.top)
    elif args.service:
        cmd_service(client, args.service)
    else:
        cmd_health(client)
