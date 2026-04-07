"""
Project Legion → MiroFish Connector

Reads job application data from Legion v3 on the Mac Mini (via SSH),
runs MiroFish swarm simulations to analyze job market sentiment
and optimize application strategy.

Usage:
    python legion_connector.py                      # Health check
    python legion_connector.py --test               # Test with sample data
    python legion_connector.py --scan               # Simulate top job categories
    python legion_connector.py --job "IT Admin"     # Simulate specific job type
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Paths
MAC_MINI = "tommie@100.88.105.106"
LEGION_DB = "~/legion-v3/legion.db"
LEGION_STATS = "~/legion-v3/claude-stats.json"
PREDICTIONS_LOG = Path(__file__).parent / "legion_predictions.jsonl"

sys.path.insert(0, str(Path(__file__).parent))
from mirofish_client import MiroFishClient
from simulation_configs import LEGION_CONFIG


def ssh_command(cmd: str, timeout: int = 15) -> str:
    """Execute a command on Mac Mini via SSH."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", MAC_MINI, cmd],
            capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, Exception) as e:
        return f"SSH ERROR: {e}"


def get_legion_stats() -> dict:
    """Get Legion system stats from Mac Mini."""
    raw = ssh_command(f"cat {LEGION_STATS} 2>/dev/null")
    if raw.startswith("SSH ERROR") or not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def get_jobs_from_db(status: str = "all", limit: int = 20) -> list[dict]:
    """
    Read jobs from Legion's SQLite database on Mac Mini.

    Returns list of dicts with: job_id, title, company, location, url,
    platform, match_score, salary_range, status
    """
    # Sanitize inputs to prevent SQL injection via SSH
    safe_status = "".join(c for c in status if c.isalnum() or c == "_")
    safe_limit = int(limit)

    where_clause = ""
    if safe_status != "all":
        where_clause = f"WHERE status = '{safe_status}'"

    query = (
        f"SELECT job_id, title, company, location, url, platform, "
        f"match_score, salary_range, status, created_at "
        f"FROM jobs {where_clause} "
        f"ORDER BY created_at DESC LIMIT {safe_limit}"
    )

    raw = ssh_command(f'sqlite3 -json {LEGION_DB} "{query}" 2>/dev/null')
    if raw.startswith("SSH ERROR") or not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def get_completed_jobs() -> list[dict]:
    """Get list of completed job applications from COMPLETE directory."""
    raw = ssh_command("ls ~/legion-v3/COMPLETE/ 2>/dev/null")
    if raw.startswith("SSH ERROR") or not raw:
        return []
    files = [f for f in raw.split("\n") if f.endswith(".json")]
    return [{"file": f} for f in files]


def get_job_categories(jobs: list[dict]) -> dict[str, int]:
    """Categorize jobs by title keywords."""
    categories = {}
    for job in jobs:
        title = (job.get("title") or "").lower()
        if any(kw in title for kw in ["it ", "system", "admin", "helpdesk", "support"]):
            cat = "IT Administration"
        elif any(kw in title for kw in ["python", "developer", "engineer", "software"]):
            cat = "Software Development"
        elif any(kw in title for kw in ["data", "analyst", "analytics"]):
            cat = "Data & Analytics"
        elif any(kw in title for kw in ["remote", "work from home"]):
            cat = "Remote Work"
        elif any(kw in title for kw in ["manager", "director", "lead"]):
            cat = "Management"
        else:
            cat = "General"
        categories[cat] = categories.get(cat, 0) + 1
    return categories


def build_seed_text(job_focus: dict, stats: dict, all_jobs: list[dict],
                    completed_count: int = 0) -> str:
    """Build seed text for MiroFish from Legion data."""
    categories = get_job_categories(all_jobs)
    total_submitted = stats.get("total_sent", 0)
    total_completed = completed_count

    # Determine market trends based on data
    trends = [
        "Remote work opportunities stabilizing after post-pandemic correction",
        "AI/automation skills commanding 20-30% salary premium",
        "IT administration roles shifting toward cloud-first (AWS/Azure)",
    ]

    industry = "Technology & IT"
    market_state = "competitive with strong demand for skilled practitioners"

    return LEGION_CONFIG.seed_text_template.format(
        job_title=job_focus.get("title", "IT Systems Administrator"),
        company=job_focus.get("company", "Various"),
        location=job_focus.get("location", "Houston, TX / Remote"),
        salary_range=job_focus.get("salary_range", "$60,000 - $90,000"),
        platform=job_focus.get("platform", "Indeed"),
        match_score=job_focus.get("match_score", 75),
        total_jobs=len(all_jobs),
        total_submitted=total_submitted,
        success_rate=total_completed / max(total_submitted, 1),
        pipeline_count=len([j for j in all_jobs if j.get("status") == "pending"]),
        industry=industry,
        market_state=market_state,
        trend_1=trends[0],
        trend_2=trends[1],
        trend_3=trends[2],
    )


def simulate_job_market(
    client: MiroFishClient,
    job_focus: dict,
    stats: dict,
    all_jobs: list[dict],
    max_rounds: int = 24,
    skip_graph: bool = False,
    completed_count: int = 0,
) -> dict:
    """Run a MiroFish dual-platform simulation for job market analysis."""
    title = job_focus.get("title", "IT Role")
    seed_text = build_seed_text(job_focus, stats, all_jobs, completed_count=completed_count)

    sim_req = (
        f"Simulate social media discourse about the job market for '{title}' roles. "
        f"Generate recruiters, hiring managers, job seekers, career coaches, and "
        f"industry insiders discussing: hiring trends, salary expectations, "
        f"resume optimization, ATS strategies, and the impact of AI on hiring. "
        f"Model how job market sentiment shifts and identify actionable patterns "
        f"for someone applying to {job_focus.get('company', 'multiple companies')}."
    )

    print(f"\nSimulating: {title}")
    print(f"  Company: {job_focus.get('company', '?')}")
    print(f"  Location: {job_focus.get('location', '?')}")

    result = client.run_dual_platform(
        simulation_requirement=sim_req,
        seed_text=seed_text,
        project_name=f"Legion: {title[:50]}",
        max_rounds=max_rounds,
        skip_graph=skip_graph,
    )

    prediction = {
        "connector": "legion",
        "job_title": title,
        "company": job_focus.get("company"),
        "location": job_focus.get("location"),
        "match_score": job_focus.get("match_score"),
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

    print(f"\nChecking Legion on Mac Mini ({MAC_MINI})...")
    stats = get_legion_stats()
    if stats:
        print(f"  Legion: ONLINE")
        print(f"  Total Sent: {stats.get('total_sent', 0)}")
        print(f"  Last Updated: {stats.get('last_updated', 'N/A')}")
    else:
        print("  Legion: UNREACHABLE (Mac Mini SSH failed)")

    jobs = get_jobs_from_db(limit=100)
    if jobs:
        print(f"  Jobs in DB: {len(jobs)}")
        cats = get_job_categories(jobs)
        for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
            print(f"    {cat}: {count}")
    completed = get_completed_jobs()
    print(f"  Completed Applications: {len(completed)}")


def cmd_test(client: MiroFishClient) -> None:
    """Run test simulation with sample data."""
    sample_job = {
        "title": "IT Systems Administrator",
        "company": "Tech Corp Houston",
        "location": "Houston, TX (Hybrid)",
        "salary_range": "$65,000 - $85,000",
        "platform": "Indeed",
        "match_score": 85,
    }
    prediction = simulate_job_market(
        client, sample_job, {"total_sent": 11}, [],
        max_rounds=5, skip_graph=True, completed_count=0,
    )
    log_prediction(prediction)
    print("\nTest complete!")
    print(json.dumps(prediction, indent=2))


def cmd_scan(client: MiroFishClient, top_n: int = 3) -> None:
    """Simulate top job categories."""
    print("Fetching jobs from Mac Mini...")
    all_jobs = get_jobs_from_db(limit=200)
    stats = get_legion_stats()
    completed_count = len(get_completed_jobs())

    if not all_jobs:
        print("No jobs found. Using sample categories...")
        categories = ["IT Systems Administrator", "Python Developer", "Data Analyst"]
    else:
        cats = get_job_categories(all_jobs)
        categories = sorted(cats.keys(), key=lambda k: cats[k], reverse=True)[:top_n]

    for i, cat in enumerate(categories[:top_n], 1):
        print(f"\n{'=' * 60}")
        print(f"Category {i}/{min(top_n, len(categories))}: {cat}")

        # Find a representative job for this category
        representative = {"title": cat, "company": "Various", "location": "Houston, TX / Remote",
                          "platform": "Indeed", "match_score": 75, "salary_range": "Market Rate"}
        for j in all_jobs:
            title = (j.get("title") or "").lower()
            if cat.lower().split()[0] in title:
                representative = j
                break

        try:
            prediction = simulate_job_market(client, representative, stats, all_jobs,
                                                   skip_graph=False, completed_count=completed_count)
            log_prediction(prediction)
        except Exception as e:
            print(f"  FAILED: {e}")

    print(f"\nDone! Predictions logged to {PREDICTIONS_LOG}")


def cmd_job(client: MiroFishClient, search: str) -> None:
    """Simulate a specific job type."""
    all_jobs = get_jobs_from_db(limit=200)
    stats = get_legion_stats()
    completed_count = len(get_completed_jobs())

    job_focus = {
        "title": search,
        "company": "Various",
        "location": "Houston, TX / Remote",
        "platform": "Indeed",
        "match_score": 75,
        "salary_range": "Market Rate",
    }

    # Try to find a real match
    matches = [j for j in all_jobs if search.lower() in (j.get("title") or "").lower()]
    if matches:
        job_focus = matches[0]
        print(f"Found {len(matches)} matching jobs. Using: {job_focus.get('title')}")

    prediction = simulate_job_market(client, job_focus, stats, all_jobs,
                                     skip_graph=False, completed_count=completed_count)
    log_prediction(prediction)
    print(json.dumps(prediction, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Project Legion → MiroFish Connector")
    parser.add_argument("--test", action="store_true", help="Run test simulation")
    parser.add_argument("--scan", action="store_true", help="Simulate top job categories")
    parser.add_argument("--job", type=str, help="Simulate specific job type")
    parser.add_argument("--url", default="http://localhost:5001", help="MiroFish URL")
    parser.add_argument("--api-key", default=None, help="MiroFish API key")
    parser.add_argument("--top", type=int, default=3, help="Number of categories to simulate")
    args = parser.parse_args()

    client = MiroFishClient(base_url=args.url, api_key=args.api_key,
                            poll_timeout=1800)

    if args.test:
        cmd_test(client)
    elif args.scan:
        cmd_scan(client, top_n=args.top)
    elif args.job:
        cmd_job(client, args.job)
    else:
        cmd_health(client)
