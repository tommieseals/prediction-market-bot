#!/usr/bin/env python3
"""
Arbitrage Scanner — Find mispriced Polymarket markets.

Scans active Polymarket markets for arbitrage opportunities where
YES + NO prices don't sum to ~$1.00, indicating potential profit.

Types of arbitrage detected:
  - BUY BOTH:  YES + NO < 0.97  (buy both sides, guaranteed profit on resolution)
  - SELL BOTH: YES + NO > 1.03  (rare, sell both sides)
  - Cross-market: same event at different prices on different condition_ids

Usage:
    python arbitrage_scanner.py              # Scan for arb (default 3% min)
    python arbitrage_scanner.py --min 3      # Min spread % (default 3)
    python arbitrage_scanner.py --alert      # Send Telegram for big spreads
"""

import argparse
import json
import os
import time
from collections import defaultdict

import requests

# ── Config ────────────────────────────────────────────────────

GAMMA_API = "https://gamma-api.polymarket.com"
DEFAULT_MIN_SPREAD = 3.0        # Minimum spread % to report
TELEGRAM_ALERT_SPREAD = 5.0     # Send Telegram alert above this %
FETCH_LIMIT = 100               # Markets per API page

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN", "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU"
)
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "939543801")


def send_telegram_alert(message: str) -> bool:
    """Send alert to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, data=data, timeout=10)
        return resp.ok
    except Exception:
        return False


def fetch_active_markets(offset: int = 0) -> list[dict]:
    """Fetch a page of active (open) markets from Polymarket."""
    try:
        resp = requests.get(
            f"{GAMMA_API}/markets",
            params={
                "closed": "false",
                "limit": FETCH_LIMIT,
                "offset": offset,
            },
            timeout=20,
        )
        if resp.ok:
            data = resp.json()
            return data if isinstance(data, list) else []
    except requests.RequestException as e:
        print(f"API error fetching markets (offset={offset}): {e}")
    return []


def parse_prices(market: dict) -> tuple[float, float] | None:
    """Extract (yes_price, no_price) from a market object."""
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
            yes_p = float(prices[0])
            no_p = float(prices[1])
            if yes_p > 0 and no_p > 0:
                return yes_p, no_p
        except (ValueError, TypeError):
            pass
    return None


def scan_single_market_arb(
    markets: list[dict], min_spread: float
) -> list[dict]:
    """
    Find markets where YES + NO prices don't sum to ~$1.00.

    Returns list of arb opportunities sorted by spread size.
    """
    opportunities = []

    for market in markets:
        prices = parse_prices(market)
        if not prices:
            continue

        yes_price, no_price = prices
        total = yes_price + no_price
        spread = abs(1.0 - total)
        spread_pct = spread * 100

        if spread_pct < min_spread:
            continue

        question = market.get("question") or market.get("title") or "Unknown"
        condition_id = market.get("conditionId", "")
        volume = float(market.get("volume", 0) or 0)
        liquidity = float(market.get("liquidity", 0) or 0)

        if total < 1.0:
            arb_type = "BUY BOTH"
            profit_per_dollar = 1.0 - total
        else:
            arb_type = "SELL BOTH"
            profit_per_dollar = total - 1.0

        opportunities.append({
            "type": arb_type,
            "question": question,
            "condition_id": condition_id,
            "yes_price": yes_price,
            "no_price": no_price,
            "total": total,
            "spread_pct": spread_pct,
            "profit_per_dollar": profit_per_dollar,
            "volume": volume,
            "liquidity": liquidity,
        })

    opportunities.sort(key=lambda x: x["spread_pct"], reverse=True)
    return opportunities


def scan_cross_market_arb(
    markets: list[dict], min_spread: float
) -> list[dict]:
    """
    Find cross-market arbitrage: same event described differently
    with different prices across condition_ids.

    Groups markets by their grouping slug (same event), then checks
    if YES prices diverge across condition_ids within the group.
    """
    # Group by event slug
    groups: dict[str, list[dict]] = defaultdict(list)
    for market in markets:
        slug = market.get("groupSlug") or market.get("slug", "")
        if not slug:
            continue
        prices = parse_prices(market)
        if not prices:
            continue
        groups[slug].append(market)

    opportunities = []

    for slug, group_markets in groups.items():
        if len(group_markets) < 2:
            continue

        # Compare all pairs within the group
        for i in range(len(group_markets)):
            for j in range(i + 1, len(group_markets)):
                m1 = group_markets[i]
                m2 = group_markets[j]

                p1 = parse_prices(m1)
                p2 = parse_prices(m2)
                if not p1 or not p2:
                    continue

                # Check if YES prices diverge significantly
                yes_diff = abs(p1[0] - p2[0])
                diff_pct = yes_diff * 100

                if diff_pct < min_spread:
                    continue

                q1 = m1.get("question") or m1.get("title") or "Unknown"
                q2 = m2.get("question") or m2.get("title") or "Unknown"

                opportunities.append({
                    "type": "CROSS-MARKET",
                    "question": f"{q1[:50]} vs {q2[:50]}",
                    "condition_id": f"{m1.get('conditionId', '')[:16]} / "
                                    f"{m2.get('conditionId', '')[:16]}",
                    "yes_price": p1[0],
                    "no_price": p2[0],
                    "total": 0,
                    "spread_pct": diff_pct,
                    "profit_per_dollar": yes_diff,
                    "volume": float(m1.get("volume", 0) or 0)
                             + float(m2.get("volume", 0) or 0),
                    "liquidity": float(m1.get("liquidity", 0) or 0)
                                 + float(m2.get("liquidity", 0) or 0),
                })

    opportunities.sort(key=lambda x: x["spread_pct"], reverse=True)
    return opportunities


def print_opportunities(opps: list[dict], label: str) -> None:
    """Print a table of arbitrage opportunities."""
    if not opps:
        print(f"\n  No {label} opportunities found.\n")
        return

    print(f"\n{'=' * 70}")
    print(f"  {label} ({len(opps)} found)")
    print(f"{'=' * 70}")

    for i, opp in enumerate(opps, 1):
        print(f"\n  #{i}  [{opp['type']}]  Spread: {opp['spread_pct']:.1f}%")
        print(f"      {opp['question'][:65]}")
        if opp["type"] == "CROSS-MARKET":
            print(f"      Market A YES: ${opp['yes_price']:.3f}  |  "
                  f"Market B YES: ${opp['no_price']:.3f}")
        else:
            print(f"      YES: ${opp['yes_price']:.3f}  |  "
                  f"NO: ${opp['no_price']:.3f}  |  "
                  f"Sum: ${opp['total']:.3f}")
        print(f"      Profit/dollar: ${opp['profit_per_dollar']:.3f}  |  "
              f"Vol: ${opp['volume']:,.0f}  |  "
              f"Liq: ${opp['liquidity']:,.0f}")


def build_alert_message(opps: list[dict]) -> str:
    """Build a Telegram alert message for big spreads."""
    big = [o for o in opps if o["spread_pct"] >= TELEGRAM_ALERT_SPREAD]
    if not big:
        return ""

    lines = [f"<b>ARB ALERT</b> ({len(big)} opportunities)\n"]
    for opp in big[:5]:  # Cap at 5 to keep message short
        lines.append(
            f"  [{opp['type']}] {opp['spread_pct']:.1f}%\n"
            f"  {opp['question'][:50]}\n"
            f"  YES=${opp['yes_price']:.3f} NO=${opp['no_price']:.3f}\n"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Scan Polymarket for arbitrage opportunities"
    )
    parser.add_argument(
        "--min", type=float, default=DEFAULT_MIN_SPREAD,
        help=f"Minimum spread %% to report (default: {DEFAULT_MIN_SPREAD})"
    )
    parser.add_argument(
        "--alert", action="store_true",
        help=f"Send Telegram alert for spreads > {TELEGRAM_ALERT_SPREAD}%%"
    )
    parser.add_argument(
        "--pages", type=int, default=3,
        help="Number of API pages to fetch (default: 3, each = 100 markets)"
    )
    args = parser.parse_args()

    min_spread = args.min

    print(f"Scanning Polymarket for arbitrage (min spread: {min_spread}%)...")
    print(f"Fetching up to {args.pages * FETCH_LIMIT} active markets...\n")

    # Fetch markets across multiple pages
    all_markets = []
    for page in range(args.pages):
        offset = page * FETCH_LIMIT
        markets = fetch_active_markets(offset=offset)
        if not markets:
            break
        all_markets.extend(markets)
        print(f"  Fetched page {page + 1}: {len(markets)} markets")
        time.sleep(0.5)

    print(f"\nTotal markets fetched: {len(all_markets)}")

    # Single-market arb (YES + NO != $1.00)
    single_opps = scan_single_market_arb(all_markets, min_spread)
    print_opportunities(single_opps, "SINGLE-MARKET ARBITRAGE")

    # Cross-market arb (same event, different prices)
    cross_opps = scan_cross_market_arb(all_markets, min_spread)
    print_opportunities(cross_opps, "CROSS-MARKET ARBITRAGE")

    # Summary
    total = len(single_opps) + len(cross_opps)
    print(f"\n{'=' * 70}")
    print(f"  TOTAL: {total} arbitrage opportunities found")
    print(f"{'=' * 70}")

    # Telegram alert
    if args.alert:
        all_opps = single_opps + cross_opps
        msg = build_alert_message(all_opps)
        if msg:
            print("\nSending Telegram alert...")
            if send_telegram_alert(msg):
                print("  Alert sent.")
            else:
                print("  Failed to send alert.")
        else:
            print(f"\nNo spreads above {TELEGRAM_ALERT_SPREAD}%, no alert sent.")


if __name__ == "__main__":
    main()
