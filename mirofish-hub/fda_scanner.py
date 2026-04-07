#!/usr/bin/env python3
"""
FDA Daily Scanner — Automated catalyst monitoring and alert system.

Scans FDA calendar for approaching PDUFA dates, runs MiroFish simulations
at key windows (T-14, T-7, T-3, T-1), parses swarm reports for consensus
probability, calculates edge vs live market prices, and sends alerts.

Pipeline:
  1. Scan FDA_CALENDAR for catalysts in window
  2. Run MiroFish simulation (or re-use cached report)
  3. Parse report → extract consensus probability
  4. Fetch prediction market price (or use demo)
  5. Calculate edge + Kelly size
  6. Alert if edge >= 15%
  7. Log everything to outcome tracker

Scheduling:
  Option A: Run manually or via orchestrator
    python fda_scanner.py --once
  Option B: Run every N hours
    python fda_scanner.py --loop 6
  Option C: System cron / Windows Task Scheduler
    0 8 * * * cd /path/to/mirofish-hub && python fda_scanner.py --once

Usage:
    python fda_scanner.py                  # Dry run — show what would happen
    python fda_scanner.py --once           # Run one scan cycle
    python fda_scanner.py --loop 6         # Repeat every 6 hours
    python fda_scanner.py --parse-only     # Parse existing reports, no new sims
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from mirofish_client import MiroFishClient
from outcome_tracker import OutcomeTracker
from report_parser import extract_consensus_from_report, parse_report, format_report
from pharma_fda_connector import (
    FDA_CALENDAR, FDACatalyst, TradeSignal,
    get_upcoming_catalysts, days_until, get_market,
    simulate_catalyst, build_seed_text, log_prediction,
    select_strategy, kelly_size, persist_signal,
    get_active_signals, MIN_EDGE, DEMO_MARKETS, PredictionMarket,
)

import logging
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fda_scanner")

# ── Paths ────────────────────────────────────────────────────
SCAN_LOG = Path(__file__).parent / "logs" / "fda_scanner.log"
CACHE_DIR = Path(__file__).parent / "data" / "fda_cache"
ALERTS_LOG = Path(__file__).parent / "logs" / "fda_alerts.jsonl"

# ── Alert Config ─────────────────────────────────────────────
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")

# Scan windows: run fresh simulation if in these ranges
# (ranges account for scanner not running every hour)
FRESH_SIM_RANGES = [(13, 15), (6, 8), (2, 4)]  # T-14±1, T-7±1, T-3±1
RECHECK_DAYS = range(1, 15)    # T-14 through T-1 → check edge daily


# ── Cached Results ──────────────────────────────────────────

def _cache_path(ticker: str, catalyst_date: str) -> Path:
    """Path to cached simulation result for a catalyst."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{ticker}_{catalyst_date}.json"


def get_cached_result(ticker: str, catalyst_date: str) -> Optional[Dict]:
    """Load cached simulation result if fresh enough (< 24h)."""
    path = _cache_path(ticker, catalyst_date)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
        if datetime.now() - cached_at > timedelta(hours=24):
            return None  # Stale
        return data
    except Exception:
        return None


def cache_result(ticker: str, catalyst_date: str, result: Dict) -> None:
    """Cache simulation result."""
    result["cached_at"] = datetime.now().isoformat()
    path = _cache_path(ticker, catalyst_date)
    path.write_text(json.dumps(result, default=str), encoding="utf-8")


# ── Alerting ────────────────────────────────────────────────

def format_alert(catalyst: FDACatalyst, consensus: Dict,
                 market: Optional[PredictionMarket],
                 signal: Optional[TradeSignal]) -> str:
    """Format alert message for Discord/console."""
    d = days_until(catalyst.target_date)
    prob = consensus.get("consensus_probability")
    ci = consensus.get("confidence_interval", (0, 100))
    market_price = market.yes_price * 100 if market else None

    lines = []
    if signal:
        edge_pct = signal.edge * 100
        lines.append(f"[TARGET] **FDA SIGNAL — ${catalyst.ticker} {catalyst.drug_name}**")
        lines.append(f"```")
        lines.append(f"Swarm:    {prob:.0f}% ({ci[0]:.0f}-{ci[1]:.0f}%)")
        if market_price is not None:
            lines.append(f"Market:   {market_price:.0f}% ({market.platform})")
            lines.append(f"Edge:     {edge_pct:+.0f}%")
        lines.append(f"Strategy: {signal.strategy}")
        lines.append(f"Direction:{signal.direction}")
        lines.append(f"Size:     ${signal.position_size:,.0f} "
                      f"(Kelly {signal.kelly_fraction:.1%})")
        lines.append(f"Horizon:  {signal.horizon_days}d")
        lines.append(f"PDUFA:    {catalyst.target_date} ({d}d)")
        lines.append(f"Convict.: {signal.conviction:.0%}")
        if signal.reasoning:
            lines.append(f"")
            for r in signal.reasoning:
                lines.append(f"  • {r}")
        lines.append(f"```")
    else:
        lines.append(f"[LIST] **FDA Monitor — ${catalyst.ticker} {catalyst.drug_name}**")
        lines.append(f"```")
        lines.append(f"Swarm:  {prob:.0f}% ({ci[0]:.0f}-{ci[1]:.0f}%)")
        if market_price is not None:
            edge = prob - market_price
            lines.append(f"Market: {market_price:.0f}%")
            lines.append(f"Edge:   {edge:+.0f}% (below {MIN_EDGE*100:.0f}% threshold)")
        lines.append(f"PDUFA:  {catalyst.target_date} ({d}d)")
        risk = consensus.get("risk_flags", [])
        if risk:
            lines.append(f"Risks:  {', '.join(risk)}")
        lines.append(f"```")

    return "\n".join(lines)


def send_discord_alert(message: str) -> bool:
    """Send alert to Discord webhook."""
    if not DISCORD_WEBHOOK:
        return False
    try:
        resp = requests.post(
            DISCORD_WEBHOOK,
            json={"content": message},
            timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception as e:
        logger.error(f"Discord alert failed: {e}")
        return False


def log_alert(catalyst: FDACatalyst, consensus: Dict,
              signal: Optional[TradeSignal]) -> None:
    """Persist alert to JSONL log."""
    ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "ticker": catalyst.ticker,
        "drug": catalyst.drug_name,
        "catalyst_type": catalyst.catalyst_type,
        "target_date": catalyst.target_date,
        "days_to": days_until(catalyst.target_date),
        "consensus": consensus.get("consensus_probability"),
        "confidence_interval": consensus.get("confidence_interval"),
        "risk_flags": consensus.get("risk_flags", []),
        "has_signal": signal is not None,
        "signal_strategy": signal.strategy if signal else None,
        "signal_direction": signal.direction if signal else None,
        "signal_size": signal.position_size if signal else None,
        "signal_edge": signal.edge if signal else None,
    }
    with open(ALERTS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Core Scanner ────────────────────────────────────────────

def scan_cycle(client: MiroFishClient, dry_run: bool = False,
               parse_only: bool = False) -> List[Dict]:
    """
    Run one complete scan cycle.

    1. Find catalysts in T-14 window
    2. For T-14/T-7/T-3: run fresh simulation
    3. For others: reuse cached report
    4. Parse report → consensus probability
    5. Compare to market → edge calc
    6. Alert if edge >= threshold
    """
    logger.info("=" * 60)
    logger.info("FDA SCANNER — Starting cycle")
    logger.info("=" * 60)

    upcoming = get_upcoming_catalysts(days_ahead=30)
    if not upcoming:
        # Expand to 90 days if nothing near-term
        upcoming = get_upcoming_catalysts(days_ahead=90)

    logger.info(f"Found {len(upcoming)} catalysts in window")

    results = []
    tracker = OutcomeTracker()

    for catalyst in upcoming:
        d = days_until(catalyst.target_date)
        logger.info(f"\n{'─' * 50}")
        logger.info(f"${catalyst.ticker} — {catalyst.drug_name}")
        logger.info(f"  {catalyst.catalyst_type} on {catalyst.target_date} ({d}d)")

        # Decide: fresh simulation or cached?
        cached = get_cached_result(catalyst.ticker, catalyst.target_date or "")
        need_fresh = (
            any(lo <= d <= hi for lo, hi in FRESH_SIM_RANGES)
            and not parse_only
        )
        have_report = cached and cached.get("report_id")

        if need_fresh and not dry_run:
            logger.info(f"  T-{d}: Running FRESH simulation")
            try:
                prediction = simulate_catalyst(
                    client, catalyst,
                    max_rounds=24 if d <= 7 else 12,  # Full cycle for near-term
                    skip_graph=(d > 7),  # Skip graph for early scans
                )
                log_prediction(prediction)
                cache_result(catalyst.ticker, catalyst.target_date or "", prediction)
                cached = prediction
            except Exception as e:
                logger.error(f"  Simulation failed: {e}")
                if not cached:
                    results.append({
                        "ticker": catalyst.ticker, "status": "sim_failed",
                        "error": str(e),
                    })
                    continue
        elif need_fresh and dry_run:
            logger.info(f"  T-{d}: Would run fresh simulation (dry run)")
            results.append({
                "ticker": catalyst.ticker, "status": "dry_run",
                "action": "fresh_simulation",
            })
            continue
        elif have_report:
            logger.info(f"  Using cached report: {cached.get('report_id')}")
        else:
            logger.info(f"  No cached report — skipping (not a sim day)")
            continue

        # Parse report for consensus
        report_id = cached.get("report_id") if cached else None
        if not report_id:
            logger.warning(f"  No report_id in cached result")
            continue

        consensus = extract_consensus_from_report(report_id)
        if consensus.get("consensus_probability") is None:
            logger.warning(f"  Report parsing failed: {consensus.get('error')}")
            # Fall back to base rate
            consensus = {
                "consensus_probability": catalyst.base_approval_prob * 100,
                "confidence_interval": (
                    catalyst.base_approval_prob * 100 - 10,
                    catalyst.base_approval_prob * 100 + 10,
                ),
                "confidence_spread": 0.5,
                "risk_flags": [],
                "bullish_ratio": 0.5,
            }
            logger.info(f"  Using base rate: {catalyst.base_approval_prob:.0%}")

        prob = consensus["consensus_probability"]
        logger.info(f"  Swarm consensus: {prob:.1f}%")

        # Get prediction market price
        market = get_market(catalyst.ticker)
        if market:
            market_pct = market.yes_price * 100
            edge_pct = prob - market_pct
            logger.info(f"  Market: {market_pct:.0f}% ({market.platform}) | "
                        f"Edge: {edge_pct:+.1f}%")
        else:
            market_pct = None
            edge_pct = None
            logger.info(f"  No market data available")

        # Generate trade signal
        signal = None
        if market:
            model_prob_decimal = prob / 100.0
            signal = select_strategy(catalyst, model_prob_decimal, market.yes_price)

        # Build result
        result = {
            "ticker": catalyst.ticker,
            "drug": catalyst.drug_name,
            "days_to": d,
            "consensus": prob,
            "market": market_pct,
            "edge": edge_pct,
            "signal": signal.strategy if signal else None,
            "status": "signal" if signal else "monitoring",
        }
        results.append(result)

        # Alert + log
        if signal:
            persist_signal(signal, cached.get("simulation_id", ""))

            # Track in outcome DB
            tracker.record_prediction(
                prediction_id=cached.get("simulation_id", f"scan_{catalyst.ticker}"),
                market_id=f"{catalyst.ticker}_{catalyst.catalyst_type}",
                connector="pharma_fda",
                market_title=f"{catalyst.drug_name} FDA Approval",
                predicted_probability=model_prob_decimal,
                market_price=market.yes_price,
                predicted_direction="YES" if signal.direction == "LONG" else "NO",
                model_version="pharma_fda_v2_scanner",
                agent_count=20,
                metadata={
                    "consensus": prob,
                    "edge": edge_pct,
                    "strategy": signal.strategy,
                    "kelly_size": signal.position_size,
                },
            )

        alert_msg = format_alert(catalyst, consensus, market, signal)
        print(alert_msg)

        if signal or (d <= 3):  # Always alert for T-3 or less
            log_alert(catalyst, consensus, signal)
            if DISCORD_WEBHOOK:
                sent = send_discord_alert(alert_msg)
                logger.info(f"  Discord alert: {'sent' if sent else 'failed'}")

    # Summary
    logger.info(f"\n{'=' * 60}")
    signals = [r for r in results if r.get("signal")]
    logger.info(f"Scan complete: {len(results)} catalysts checked, "
                f"{len(signals)} signals generated")

    # Show active signals
    active = get_active_signals()
    if active:
        logger.info(f"\nActive signals ({len(active)}):")
        for s in active:
            logger.info(f"  {s['direction']} ${s['ticker']} | "
                        f"{s['strategy']} | ${s['position_size']:,.0f} | "
                        f"Edge: {s['edge']:+.0%}")

    return results


# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="FDA Daily Scanner — automated catalyst alerts"
    )
    parser.add_argument("--once", action="store_true",
                        help="Run one scan cycle")
    parser.add_argument("--loop", type=int, metavar="HOURS",
                        help="Run every N hours continuously")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without running sims")
    parser.add_argument("--parse-only", action="store_true",
                        help="Only parse existing reports, no new sims")
    parser.add_argument("--url", default="http://localhost:5001",
                        help="MiroFish URL")
    parser.add_argument("--api-key", default=None, help="MiroFish API key")
    args = parser.parse_args()

    client = MiroFishClient(
        base_url=args.url, api_key=args.api_key,
        poll_timeout=1800, request_timeout=300,
    )

    if args.dry_run:
        print("\n=== DRY RUN — no simulations will execute ===\n")
        scan_cycle(client, dry_run=True)

    elif args.once:
        scan_cycle(client, parse_only=args.parse_only)

    elif args.loop:
        interval = args.loop * 3600
        logger.info(f"Starting continuous scan — every {args.loop}h")
        while True:
            try:
                scan_cycle(client, parse_only=args.parse_only)
            except Exception as e:
                logger.error(f"Scan cycle failed: {e}")
            logger.info(f"Next scan in {args.loop}h")
            time.sleep(interval)

    else:
        # Default: dry run
        print("=== FDA Scanner — Dry Run ===")
        print("Use --once to run, --loop N to repeat every N hours\n")
        scan_cycle(client, dry_run=True)


if __name__ == "__main__":
    main()
