"""
MiroFish Hub — Master Orchestrator

Runs dual-platform (Twitter + Reddit) swarm simulations across all 5 projects:
  1. TerminatorBot  — Prediction market crowd sentiment
  2. Arbitrage Pharma — Biotech deal intelligence
  3. Project Legion   — Job market sentiment
  4. Project Vault    — Stock market crowd psychology
  5. Money Machine    — Freelance market demand

Usage:
    python run_all.py                   # Health check all systems
    python run_all.py --test            # Quick test all connectors (5 rounds, no graph)
    python run_all.py --run             # Full production run (24 rounds, dual-platform)
    python run_all.py --run --only terminator,pharma  # Run specific projects
    python run_all.py --status          # Show all prediction logs

Configuration:
    All simulations use dual-platform (Twitter + Reddit) with 24 rounds
    to cover the full 24-hour agent activity cycle.
    Ollama qwen2.5:14b on RTX 3060 GPU for local inference.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mirofish_client import MiroFishClient
from simulation_configs import ALL_CONFIGS, get_config


def check_all_health(client: MiroFishClient) -> dict:
    """Check health of all systems."""
    status = {}

    # MiroFish backend
    print("=" * 60)
    print("MIROFISH HUB — SYSTEM HEALTH CHECK")
    print("=" * 60)

    mf_ok = client.health_check()
    status["mirofish"] = "ONLINE" if mf_ok else "OFFLINE"
    print(f"\n[FIX] MiroFish Backend: {'[OK] ONLINE' if mf_ok else '[FAIL] OFFLINE'}")

    # Ollama
    import requests
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        status["ollama"] = f"ONLINE ({len(models)} models)"
        print(f"[AI] Ollama LLM: [OK] {len(models)} models loaded")
        if "qwen2.5:14b" in " ".join(models):
            print(f"   qwen2.5:14b: [OK] Available")
        else:
            print(f"   qwen2.5:14b: [WARN] Not found (available: {', '.join(models[:5])})")
    except Exception:
        status["ollama"] = "OFFLINE"
        print("[AI] Ollama LLM: [FAIL] OFFLINE")

    # Each connector
    print(f"\n📡 Connectors:")
    connectors = {
        "oil": ("Oil Engine", r"C:\Users\USER\clawd\TerminatorBot\data\market_cache.db"),
        "terminator": ("TerminatorBot", r"C:\Users\USER\clawd\TerminatorBot\data\market_cache.db"),
        "pharma": ("Arbitrage Pharma", r"C:\Users\USER\clawd\arbitrage-pharma\data\opportunities.json"),
        "vault": ("Project Vault", r"C:\Users\USER\clawd\project-vault\data\dashboard_backup.json"),
        "money_machine": ("Money Machine", r"C:\Users\USER\clawd\memory\money-machine-tracker.md"),
    }

    for key, (name, data_path) in connectors.items():
        exists = Path(data_path).exists()
        status[key] = "DATA OK" if exists else "NO DATA"
        icon = "[OK]" if exists else "[FAIL]"
        print(f"   {icon} {name}: {'Data available' if exists else 'Data not found'}")

    # Legion (SSH)
    import subprocess
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=3", "tommie@100.88.105.106", "echo OK"],
            capture_output=True, text=True, timeout=8,
            stdin=subprocess.DEVNULL,
        )
        legion_ok = "OK" in result.stdout
        status["legion"] = "SSH OK" if legion_ok else "SSH FAIL"
        print(f"   {'[OK]' if legion_ok else '[FAIL]'} Project Legion (Mac Mini SSH): "
              f"{'Connected' if legion_ok else 'Failed'}")
    except Exception:
        status["legion"] = "SSH TIMEOUT"
        print("   [FAIL] Project Legion (Mac Mini SSH): Timeout")

    # Summary
    all_ok = all(v not in ("OFFLINE", "NO DATA", "SSH FAIL", "SSH TIMEOUT")
                 for v in status.values())
    print(f"\n{'=' * 60}")
    print(f"Overall: {'[OK] ALL SYSTEMS GO' if all_ok else '[WARN] SOME ISSUES — check above'}")
    print(f"{'=' * 60}")

    return status


def run_connector(connector_key: str, client: MiroFishClient,
                  test_mode: bool = False) -> dict:
    """Run a specific connector's simulation."""
    config = get_config(connector_key)
    max_rounds = 5 if test_mode else config.max_rounds
    skip_graph = test_mode

    print(f"\n{'=' * 60}")
    print(f"[LAUNCH] {config.project_name}")
    print(f"   Real Project: {config.real_project}")
    print(f"   Platform: {'parallel (Twitter + Reddit)' if config.platform == 'parallel' else config.platform}")
    print(f"   Rounds: {max_rounds}")
    print(f"   Graph: {'skip' if skip_graph else 'build with Zep'}")
    print(f"{'=' * 60}")

    start = time.time()

    try:
        if connector_key == "terminator":
            import terminator_connector as mod
        elif connector_key == "pharma":
            import pharma_connector as mod
        elif connector_key == "legion":
            import legion_connector as mod
        elif connector_key == "vault":
            import vault_connector as mod
        elif connector_key == "money_machine":
            import money_machine_connector as mod
        else:
            raise ValueError(f"No connector for key: {connector_key}")

        if test_mode:
            mod.cmd_test(client)
        else:
            mod.cmd_scan(client, top_n=2)

        elapsed = time.time() - start
        return {"status": "success", "elapsed_seconds": elapsed}

    except Exception as e:
        elapsed = time.time() - start
        print(f"\n  [FAIL] FAILED: {e}")
        return {"status": "failed", "error": str(e), "elapsed_seconds": elapsed}


def show_status() -> None:
    """Show prediction logs from all connectors."""
    print("=" * 60)
    print("MIROFISH HUB — PREDICTION LOGS")
    print("=" * 60)

    log_files = {
        "TerminatorBot": "terminator_predictions.jsonl",
        "Arbitrage Pharma": "pharma_predictions.jsonl",
        "Project Legion": "legion_predictions.jsonl",
        "Project Vault": "vault_predictions.jsonl",
        "Money Machine": "money_machine_predictions.jsonl",
    }

    hub_dir = Path(__file__).parent
    total = 0

    for name, filename in log_files.items():
        log_path = hub_dir / filename
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            count = len(lines)
            total += count

            if lines:
                last = json.loads(lines[-1])
                ts = last.get("timestamp", "?")
                print(f"\n[STATS] {name}: {count} predictions (last: {ts})")

                # Show last 3
                for line in lines[-3:]:
                    pred = json.loads(line)
                    sim_id = pred.get("simulation_id", "?")
                    label = (pred.get("market_title") or pred.get("asset_name") or
                             pred.get("job_title") or pred.get("symbol") or
                             pred.get("service_name") or "?")
                    print(f"   • {label[:50]} (sim: {sim_id})")
        else:
            print(f"\n[STATS] {name}: No predictions yet")

    print(f"\n{'=' * 60}")
    print(f"Total Predictions: {total}")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(
        description="MiroFish Hub — Master Orchestrator for 5 Money-Making Projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--test", action="store_true",
                        help="Quick test (5 rounds, no graph)")
    parser.add_argument("--run", action="store_true",
                        help="Full production run (24 rounds, dual-platform)")
    parser.add_argument("--status", action="store_true",
                        help="Show prediction logs")
    parser.add_argument("--only", type=str, default=None,
                        help="Comma-separated list of projects to run "
                             "(terminator,pharma,legion,vault,money_machine)")
    parser.add_argument("--url", default="http://localhost:5001",
                        help="MiroFish URL")
    parser.add_argument("--api-key", default=None, help="MiroFish API key")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    client = MiroFishClient(base_url=args.url, api_key=args.api_key,
                            poll_timeout=1800)  # 30 min timeout for full runs

    if not args.test and not args.run:
        check_all_health(client)
        return

    # Determine which projects to run
    if args.only:
        keys = [k.strip() for k in args.only.split(",")]
        invalid = [k for k in keys if k not in ALL_CONFIGS]
        if invalid:
            print(f"ERROR: Unknown project(s): {', '.join(invalid)}")
            print(f"Available: {', '.join(ALL_CONFIGS.keys())}")
            sys.exit(1)
    else:
        keys = list(ALL_CONFIGS.keys())

    print("\n" + "=" * 60)
    print(f"MIROFISH HUB — {'TEST RUN' if args.test else 'PRODUCTION RUN'}")
    print(f"Projects: {', '.join(keys)}")
    print(f"Mode: {'Quick test (5 rounds, no graph)' if args.test else 'Full (24 rounds, dual-platform, Zep graph)'}")
    print("=" * 60)

    results = {}
    total_start = time.time()

    for key in keys:
        if key not in ALL_CONFIGS:
            print(f"\n[WARN] Unknown project: {key}")
            continue
        results[key] = run_connector(key, client, test_mode=args.test)

    total_elapsed = time.time() - total_start

    # Summary
    print("\n" + "=" * 60)
    print("RUN SUMMARY")
    print("=" * 60)
    for key, res in results.items():
        config = get_config(key)
        status_icon = "[OK]" if res["status"] == "success" else "[FAIL]"
        print(f"  {status_icon} {config.project_name}: {res['status']} "
              f"({res['elapsed_seconds']:.0f}s)")
    print(f"\nTotal time: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
    print("=" * 60)


if __name__ == "__main__":
    main()
