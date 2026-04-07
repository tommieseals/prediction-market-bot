#!/usr/bin/env python3
"""
NARRATIVE SQUEEZE DETECTOR -- Find overblown market narratives to fade.

Adapted from Shkreli's squeeze scanner + @itslirrato's fade strategy.
When media hype drives market prices above true probability, we FADE.

Score = (media_hype x 25%) + (days_to_resolution x 20%) +
        (liquidity x 20%) + (swarm_vs_market_gap x 15%) +
        (social_sentiment x 20%)

High score + swarm < market = FADE the narrative.

Usage:
    python narrative_detector.py                    # Scan all consensus picks
    python narrative_detector.py --market "Iran"    # Check specific market
"""

import argparse
import json
import math
import requests
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"
POLYMARKET_GAMMA = "https://gamma-api.polymarket.com"


def get_market_data(condition_id: str) -> Optional[Dict]:
    """Fetch market metadata from Polymarket Gamma API."""
    try:
        r = requests.get(
            f"{POLYMARKET_GAMMA}/markets",
            params={"clob_token_ids": condition_id},
            timeout=15,
        )
        if r.ok:
            data = r.json()
            if data and isinstance(data, list):
                return data[0]
    except Exception:
        pass
    return None


def calculate_hype_score(market_title: str, volume_24h: float,
                          price_change_24h: float) -> float:
    """
    Estimate media/narrative hype level (0-1).

    High hype indicators:
    - Large 24h volume relative to market size
    - Big price swings in 24h
    - Politically charged keywords
    """
    score = 0.0

    # Volume spike (high volume = lots of attention)
    if volume_24h > 100000:
        score += 0.3
    elif volume_24h > 50000:
        score += 0.2
    elif volume_24h > 10000:
        score += 0.1

    # Price movement (big swings = narrative-driven)
    abs_change = abs(price_change_24h)
    if abs_change > 0.20:
        score += 0.4
    elif abs_change > 0.10:
        score += 0.25
    elif abs_change > 0.05:
        score += 0.1

    # Narrative keywords (politically/emotionally charged)
    hype_keywords = [
        "iran", "trump", "war", "strike", "regime", "invasion",
        "nuclear", "ceasefire", "crash", "moon", "surge", "collapse",
        "emergency", "crisis", "breaking", "shocking",
    ]
    t = market_title.lower()
    keyword_hits = sum(1 for kw in hype_keywords if kw in t)
    score += min(0.3, keyword_hits * 0.1)

    return min(1.0, score)


def calculate_resolution_score(end_date_str: str) -> float:
    """
    Score based on days until resolution (0-1).

    Far deadline = more time for narrative to deflate = better fade.
    Close deadline = less time, riskier fade.
    """
    if not end_date_str:
        return 0.5  # Unknown

    try:
        end = datetime.fromisoformat(end_date_str.replace("Z", ""))
        days = (end - datetime.now()).total_seconds() / 86400
        if days <= 0:
            return 0.0  # Already expired
        elif days <= 1:
            return 0.2  # Too close
        elif days <= 7:
            return 0.5  # Medium
        elif days <= 30:
            return 0.8  # Good fade window
        else:
            return 1.0  # Plenty of time
    except Exception:
        return 0.5


def calculate_liquidity_score(volume: float) -> float:
    """
    Score based on market liquidity (0-1).

    Higher liquidity = easier to enter/exit = better trade.
    """
    if volume <= 0:
        return 0.0
    # Log scale: $1K = 0.2, $10K = 0.4, $100K = 0.6, $1M = 0.8
    return min(1.0, math.log10(max(volume, 1)) / 7)


def calculate_gap_score(swarm_prob: float, market_price: float) -> float:
    """
    Score based on gap between swarm consensus and market price (0-1).

    Bigger gap = more mispricing = better opportunity.
    """
    if swarm_prob is None or market_price is None:
        return 0.0
    gap = abs(swarm_prob - market_price)
    # 5% gap = 0.25, 10% = 0.5, 20% = 1.0
    return min(1.0, gap / 0.20)


def narrative_squeeze_score(
    market_title: str,
    market_price: float,
    swarm_prob: Optional[float],
    volume: float = 0,
    volume_24h: float = 0,
    price_change_24h: float = 0,
    end_date: str = "",
) -> Dict:
    """
    Compute narrative squeeze score (0-100).

    Returns dict with score, components, and recommendation.
    """
    hype = calculate_hype_score(market_title, volume_24h, price_change_24h)
    resolution = calculate_resolution_score(end_date)
    liquidity = calculate_liquidity_score(volume)
    gap = calculate_gap_score(swarm_prob, market_price)

    # Sentiment placeholder (would need Twitter/news API)
    sentiment = hype * 0.8  # Proxy: hype correlates with sentiment

    # Weighted composite
    score = (
        hype * 0.25
        + resolution * 0.20
        + liquidity * 0.20
        + gap * 0.15
        + sentiment * 0.20
    ) * 100

    # Determine recommendation
    recommendation = "HOLD"
    if swarm_prob is not None:
        if score >= 60 and swarm_prob < market_price - 0.08:
            recommendation = "FADE"  # Bet AGAINST the narrative
        elif score >= 40 and swarm_prob > market_price + 0.08:
            recommendation = "FOLLOW"  # Narrative underpriced
        elif score < 30:
            recommendation = "SKIP"  # Not enough signal

    return {
        "score": round(score, 1),
        "recommendation": recommendation,
        "components": {
            "hype": round(hype, 3),
            "resolution_window": round(resolution, 3),
            "liquidity": round(liquidity, 3),
            "swarm_gap": round(gap, 3),
            "sentiment": round(sentiment, 3),
        },
        "market_price": market_price,
        "swarm_prob": swarm_prob,
        "edge": round((swarm_prob or 0) - market_price, 4),
    }


def scan_consensus_picks() -> List[Dict]:
    """Scan all pending consensus picks for narrative squeeze opportunities."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row

    picks = conn.execute("""
        SELECT market_title, condition_id, side, confidence,
               avg_entry_price, end_date, whale_count
        FROM consensus_picks
        WHERE outcome = 'pending'
        ORDER BY confidence DESC
    """).fetchall()

    results = []
    for pick in picks:
        price = pick["avg_entry_price"] or 0.5

        # Try to get MiroFish swarm probability
        mf = conn.execute(
            "SELECT swarm_prob FROM mirofish_results WHERE condition_id = ? LIMIT 1",
            (pick["condition_id"],),
        ).fetchone()
        swarm_prob = mf[0] / 100.0 if mf and mf[0] else None

        result = narrative_squeeze_score(
            market_title=pick["market_title"] or "",
            market_price=price,
            swarm_prob=swarm_prob,
            end_date=pick["end_date"] or "",
        )
        result["market_title"] = pick["market_title"]
        result["side"] = pick["side"]
        result["confidence"] = pick["confidence"]
        result["whale_count"] = pick["whale_count"]
        results.append(result)

    conn.close()

    # Sort by score descending
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Narrative Squeeze Detector -- find overblown markets to fade"
    )
    parser.add_argument("--market", type=str, help="Search for specific market")
    parser.add_argument("--min-score", type=float, default=40,
                        help="Minimum squeeze score to display (default: 40)")
    args = parser.parse_args()

    print("=" * 60)
    print("NARRATIVE SQUEEZE DETECTOR")
    print("=" * 60)

    results = scan_consensus_picks()

    if args.market:
        keyword = args.market.lower()
        results = [r for r in results if keyword in r["market_title"].lower()]

    shown = 0
    for r in results:
        if r["score"] < args.min_score:
            continue
        shown += 1
        rec_label = {
            "FADE": "[FADE]",
            "FOLLOW": "[FOLLOW]",
            "HOLD": "[HOLD]",
            "SKIP": "[SKIP]",
        }.get(r["recommendation"], "[?]")

        print(f"\n{rec_label} {r['market_title'][:55]}")
        print(f"  Score: {r['score']:.0f}/100 | "
              f"Market: {r['market_price']:.0%} | "
              f"Swarm: {r['swarm_prob']:.0%}" if r["swarm_prob"] else
              f"  Score: {r['score']:.0f}/100 | Market: {r['market_price']:.0%} | Swarm: N/A")
        print(f"  Hype: {r['components']['hype']:.0%} | "
              f"Liquidity: {r['components']['liquidity']:.0%} | "
              f"Gap: {r['components']['swarm_gap']:.0%} | "
              f"Resolution: {r['components']['resolution_window']:.0%}")
        print(f"  Whales: {r['whale_count']} | Confidence: {r['confidence']}%")

    if shown == 0:
        print(f"\n  No narrative squeezes found above score {args.min_score}")

    print(f"\n{'=' * 60}")
    print(f"Scanned {len(results)} picks, {shown} above threshold")
    print("=" * 60)


if __name__ == "__main__":
    main()
