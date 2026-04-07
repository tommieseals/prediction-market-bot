#!/usr/bin/env python3
"""
Resolve Predictions -- Check Polymarket outcomes and settle the ledger.

Reads unresolved predictions from outcomes.db, queries Polymarket Gamma API
to see if markets have resolved, calculates P&L, and updates the tracker.

Usage:
    python resolve_predictions.py           # Resolve all pending
    python resolve_predictions.py --report  # Just show accuracy report
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from outcome_tracker import OutcomeTracker

# -- Config ----------------------------------------------------------------

GAMMA_API = "https://gamma-api.polymarket.com"
WHALE_DB = Path(__file__).parent / "data" / "whale_hunter.db"
BET_SIZE = 100.0  # Standard unit bet in dollars
WIN_THRESHOLD = 0.95  # Price above this = clear winner


def lookup_token_id(condition_id):
    """Look up a CLOB token_id from whale_hunter.db by condition_id."""
    if not WHALE_DB.exists():
        return None
    try:
        with sqlite3.connect(str(WHALE_DB)) as conn:
            row = conn.execute(
                "SELECT token_id FROM whale_positions "
                "WHERE condition_id = ? AND token_id IS NOT NULL "
                "LIMIT 1",
                (condition_id,),
            ).fetchone()
            return row[0] if row else None
    except Exception:
        return None


def fetch_market(token_id):
    """Fetch market data from Polymarket Gamma API by CLOB token ID."""
    try:
        resp = requests.get(
            GAMMA_API + "/markets",
            params={"clob_token_ids": token_id},
            timeout=15,
        )
        if resp.ok:
            markets = resp.json()
            if isinstance(markets, list) and markets:
                return markets[0]
            elif isinstance(markets, dict) and markets:
                return markets
    except requests.RequestException as e:
        print("  API error for token: %s" % e)
    return None


def fetch_market_by_condition(condition_id):
    """Fallback: fetch market by condition_id."""
    try:
        resp = requests.get(
            GAMMA_API + "/markets",
            params={"condition_id": condition_id},
            timeout=15,
        )
        if resp.ok:
            markets = resp.json()
            if isinstance(markets, list) and markets:
                return markets[0]
            elif isinstance(markets, dict) and markets:
                return markets
    except requests.RequestException as e:
        print("  API error for condition: %s" % e)
    return None


def parse_outcome_prices(market):
    """Extract (yes_price, no_price) from market data."""
    prices = market.get("outcomePrices")
    if not prices:
        return None
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except (json.JSONDecodeError, TypeError):
            return None
    if isinstance(prices, list) and len(prices) >= 2:
        try:
            return float(prices[0]), float(prices[1])
        except (ValueError, TypeError):
            return None
    return None


def calculate_pnl(predicted_direction, resolved_yes, entry_price):
    """
    Calculate P&L for a standard $100 unit bet.

    If we predicted YES and bought YES tokens at entry_price:
      - Win:  profit = (1 - entry_price) * BET_SIZE
      - Lose: loss   = -entry_price * BET_SIZE

    If we predicted NO and bought NO tokens at (1 - entry_price):
      - Win:  profit = entry_price * BET_SIZE
      - Lose: loss   = -(1 - entry_price) * BET_SIZE
    """
    pred_yes = predicted_direction.upper() == "YES"
    correct = pred_yes == resolved_yes

    if pred_yes:
        if correct:
            return (1.0 - entry_price) * BET_SIZE
        else:
            return -entry_price * BET_SIZE
    else:
        no_price = 1.0 - entry_price
        if correct:
            return (1.0 - no_price) * BET_SIZE
        else:
            return -no_price * BET_SIZE


def resolve_all(ot):
    """Check all unresolved predictions against Polymarket outcomes."""
    unresolved = ot.get_unresolved()
    if not unresolved:
        print("No unresolved predictions found.")
        return

    print("Checking %d unresolved prediction(s)...\n" % len(unresolved))
    resolved_count = 0
    skipped_count = 0

    for pred in unresolved:
        pid = pred["prediction_id"]
        market_id = pred["market_id"]
        direction = pred.get("predicted_direction", "YES")
        entry_price = pred.get("market_price_at_prediction", 0.5)
        title = pred.get("market_title", "Unknown")

        print("  [%s] %s" % (pid[:12], title[:60]))

        # Try to fetch market data -- three strategies
        market = fetch_market(market_id)
        if not market:
            token_id = lookup_token_id(market_id)
            if token_id:
                market = fetch_market(token_id)
        if not market:
            market = fetch_market_by_condition(market_id)

        if not market:
            print("    -> Could not find market on Polymarket, skipping")
            skipped_count += 1
            time.sleep(0.3)
            continue

        is_closed = market.get("closed", False)
        if isinstance(is_closed, str):
            is_closed = is_closed.lower() == "true"
        if not is_closed:
            print("    -> Market still open")
            skipped_count += 1
            time.sleep(0.3)
            continue

        prices = parse_outcome_prices(market)
        if not prices:
            print("    -> No outcome prices available, skipping")
            skipped_count += 1
            time.sleep(0.3)
            continue

        yes_price, no_price = prices
        if yes_price > WIN_THRESHOLD:
            resolved_yes = True
        elif no_price > WIN_THRESHOLD:
            resolved_yes = False
        else:
            print("    -> No clear winner yet (YES=%.2f, NO=%.2f)" % (yes_price, no_price))
            skipped_count += 1
            time.sleep(0.3)
            continue

        pnl = calculate_pnl(direction, resolved_yes, entry_price)
        outcome_str = "YES" if resolved_yes else "NO"
        correct = (direction.upper() == "YES") == resolved_yes
        result_str = "WIN" if correct else "LOSS"

        print("    -> Resolved %s | We predicted %s | %s | P&L: $%+.2f" % (
            outcome_str, direction, result_str, pnl))

        ot.resolve(pid, resolved_yes=resolved_yes, pnl=pnl)
        resolved_count += 1
        time.sleep(0.3)

    print("\nDone: %d resolved, %d skipped/pending" % (resolved_count, skipped_count))


def print_report(ot):
    """Print the accuracy/calibration report."""
    report = ot.get_accuracy_report()

    print("=" * 55)
    print("  MIROFISH PREDICTION ACCURACY REPORT")
    print("=" * 55)
    print("  Total predictions: %d" % report["total_predictions"])
    print("  Resolved:          %d" % report["resolved"])
    print("  Unresolved:        %d" % report["unresolved"])
    print()

    bs = report["brier_score"]
    if bs is not None:
        print("  Brier Score:       %.4f  (0=perfect, 0.25=random)" % bs)
    da = report["directional_accuracy"]
    if da is not None:
        print("  Direction Acc:     %.1f%%" % (da * 100))
    wr = report["win_rate"]
    if wr is not None:
        print("  Win Rate:          %.1f%%  (%dW / %dL)" % (
            wr * 100, report["wins"], report["losses"]))
    print("  Total P&L:         $%+,.2f" % report["total_pnl"])
    print()

    cal = report.get("calibration", {})
    if cal:
        print("  Calibration:")
        print("  %-12s %10s %10s %8s %5s" % ("Bucket", "Predicted", "Actual", "Gap", "N"))
        print("  " + "-" * 47)
        for bucket, data in sorted(cal.items()):
            print("  %-12s %10.3f %10.3f %8.3f %5d" % (
                bucket, data["avg_predicted"], data["avg_actual"],
                data["gap"], data["sample_size"]))
    print("=" * 55)


def main():
    parser = argparse.ArgumentParser(
        description="Resolve MiroFish predictions against Polymarket outcomes"
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Just show accuracy report without resolving"
    )
    args = parser.parse_args()

    ot = OutcomeTracker()

    if args.report:
        print_report(ot)
    else:
        resolve_all(ot)
        print()
        print_report(ot)


if __name__ == "__main__":
    main()
