#!/usr/bin/env python3
"""
WHALE SCORER — Elite Trader Scoring with Proper Statistical Methods

Replaces naive "90% win rate" with:
  - Brier scores (proper scoring rules)
  - Difficulty-adjusted accuracy
  - Bayesian win rate shrinkage
  - Risk-adjusted returns (simplified Calmar)
  - Insider pattern detection
  - Composite elite score (0-100)
"""

import math
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Database for insider flags
WHALE_DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"

logger = logging.getLogger("whale_scorer")


# ── Data Models ────────────────────────────────────────────────

@dataclass
class WhaleProfile:
    """Institutional-grade trader profile with proper scoring."""
    address: str
    display_name: str
    pnl: float
    volume: float
    num_trades: int

    # Proper scoring metrics
    win_rate_raw: float            # Raw wins / total (for reference only)
    brier_score: float             # Lower = better (0=perfect, 0.25=random)
    brier_skill: float             # 1 - brier/0.25 (higher = better)
    difficulty_adjusted_acc: float  # Hard trade accuracy weighted 2x
    bayesian_win_rate: float       # Shrunk toward 0.5

    # Risk metrics
    realized_roi: float            # PnL / total invested
    max_drawdown: float            # Worst peak-to-trough (negative)
    calmar_ratio: float            # ROI / |max_drawdown|

    # Composite
    elite_score: float             # 0-100 composite
    categories: List[str] = field(default_factory=list)
    avg_position_size: float = 0.0

    # Insider detection
    insider_flags: List[str] = field(default_factory=list)
    insider_score: float = 0.0     # 0-100


@dataclass
class WhalePosition:
    """A tracked whale position."""
    market_title: str
    condition_id: str
    token_id: str                  # asset ID for CLOB
    side: str                      # "YES" or "NO"
    size: float                    # Number of shares
    size_usd: float                # Dollar value
    entry_price: float             # avgPrice
    current_price: float
    unrealized_pnl: float
    market_end_date: str = ""
    is_new: bool = False           # First time seeing this position


# ── Brier Score Calculator ─────────────────────────────────────

def calculate_brier_score(closed_positions: List[Dict]) -> Tuple[float, float]:
    """
    Proper scoring rule: Brier score = mean((prediction - outcome)^2)

    Each trade is scored as:
      - Entry price = implied probability (e.g., 0.65 = 65% chance of YES)
      - Outcome = 1 if position won (positive PnL), 0 if lost

    Returns: (brier_score, brier_skill)
      - brier_score: 0 = perfect, 0.25 = random, 0.5 = perfectly wrong
      - brier_skill: 1 - (brier / 0.25), where >0 is better than random
    """
    scores = []

    for pos in closed_positions:
        entry_price = float(pos.get("avgPrice", 0.5) or 0.5)
        realized_pnl = float(pos.get("realizedPnl", 0) or 0)

        # Clamp entry price to valid probability range
        entry_price = max(0.01, min(0.99, entry_price))

        # Infer outcome from PnL
        if realized_pnl > 0:
            outcome = 1  # Won
        elif realized_pnl < 0:
            outcome = 0  # Lost
        else:
            continue  # Skip unresolved or zero PnL

        brier = (entry_price - outcome) ** 2
        scores.append(brier)

    if not scores:
        return 0.25, 0.0  # Random baseline

    mean_brier = sum(scores) / len(scores)
    # Skill: 1 = perfect, 0 = random, negative = worse than random
    skill = 1 - (mean_brier / 0.25)

    return round(mean_brier, 4), round(max(-1.0, skill), 4)


def calculate_difficulty_adjusted_accuracy(
    closed_positions: List[Dict]
) -> Tuple[float, float, float]:
    """
    Separate accuracy by prediction difficulty.

    Easy trades (price 0.80+):
      Buying high-probability outcomes. Anyone can get 90%+ here.
      Weighted 0.5x in composite.

    Hard trades (price 0.45-0.70):
      Genuine prediction skill required. Close to coin flip.
      Weighted 2.0x in composite.

    Returns: (easy_accuracy, hard_accuracy, combined_score)
    """
    easy_correct, easy_total = 0, 0
    hard_correct, hard_total = 0, 0

    for pos in closed_positions:
        price = float(pos.get("avgPrice", 0.5) or 0.5)
        pnl = float(pos.get("realizedPnl", 0) or 0)
        won = pnl > 0

        if price >= 0.80 or price <= 0.20:  # Easy (high or low prob)
            easy_total += 1
            if won:
                easy_correct += 1
        elif 0.35 <= price <= 0.70:  # Hard (near 50/50)
            hard_total += 1
            if won:
                hard_correct += 1

    easy_acc = easy_correct / easy_total if easy_total > 0 else 0.5
    hard_acc = hard_correct / hard_total if hard_total > 0 else 0.5

    # Combined: hard trades weighted 3x (that's where skill shows)
    if easy_total + hard_total == 0:
        combined = 0.5
    else:
        combined = (easy_acc * 0.25) + (hard_acc * 0.75)

    return round(easy_acc, 4), round(hard_acc, 4), round(combined, 4)


def bayesian_shrinkage(raw_rate: float, n: int, prior: float = 0.5,
                        prior_strength: int = 20) -> float:
    """
    Bayesian shrinkage for win rate estimates.

    With small samples, shrink toward the population mean (0.5).
    As n increases, trust the raw rate more.

    Formula: adjusted = (n * raw + k * prior) / (n + k)
    Where k = prior_strength (20 = moderate, 50 = strong)
    """
    adjusted = (n * raw_rate + prior_strength * prior) / (n + prior_strength)
    return round(adjusted, 4)


# ── Risk Metrics ───────────────────────────────────────────────

def calculate_risk_metrics(
    closed_positions: List[Dict], total_invested: float
) -> Tuple[float, float, float]:
    """
    Calculate risk-adjusted returns.

    Returns: (roi, max_drawdown, calmar_ratio)
    """
    total_pnl = sum(float(p.get("realizedPnl", 0) or 0) for p in closed_positions)
    roi = total_pnl / max(total_invested, 1.0)

    # Estimate drawdown from sequential PnL
    # (Rough: real drawdown needs equity curve from /value endpoint)
    running_pnl = 0.0
    peak_pnl = 0.0
    max_dd = 0.0

    for pos in closed_positions:
        pnl = float(pos.get("realizedPnl", 0) or 0)
        running_pnl += pnl
        peak_pnl = max(peak_pnl, running_pnl)
        drawdown = running_pnl - peak_pnl
        max_dd = min(max_dd, drawdown)

    # Calmar = annualized return / max drawdown
    calmar = roi / abs(max_dd) if max_dd != 0 else roi * 10  # Cap if no drawdown

    return round(roi, 4), round(max_dd, 2), round(min(calmar, 50.0), 4)


# ── Insider Detection ─────────────────────────────────────────

def detect_insider_patterns(
    address: str,
    activity: List[Dict],
    closed_positions: List[Dict],
    num_trades: int = 0
) -> Tuple[List[str], float]:
    """
    Flag suspicious trading patterns.

    Returns: (flags: list[str], insider_score: 0-100)
    """
    flags = []
    score = 0.0

    if not activity:
        return flags, score

    # 1. Account activity concentration (proxy for age)
    timestamps = []
    for a in activity:
        ts = a.get("timestamp")
        if ts:
            try:
                if isinstance(ts, (int, float)):
                    timestamps.append(ts)
                else:
                    timestamps.append(float(ts))
            except (ValueError, TypeError):
                pass

    if timestamps:
        span_days = (max(timestamps) - min(timestamps)) / 86400
        # NOTE: /activity endpoint only returns recent data (~days), so
        # span_days < 7 is true for almost ALL accounts regardless of age.
        # Only flag truly extreme cases: all activity in < 1 day with 50+ trades
        if span_days < 1 and num_trades > 50:
            flags.append("NEW_ACCOUNT_HIGH_ACTIVITY")
            score += 25

    # 2. Extreme position size concentration
    # NOTE: We're tracking top leaderboard traders — large trades are normal.
    # Only flag truly extreme outliers (20x median, 10+ occurrences).
    sizes = [float(a.get("usdcSize", 0) or a.get("size", 0) or 0)
             for a in activity if a.get("type") == "TRADE"]
    if sizes:
        median_size = sorted(sizes)[len(sizes) // 2]
        if median_size > 0:
            extreme_trades = [s for s in sizes if s > median_size * 20]
            if len(extreme_trades) > 10:
                flags.append("SIZE_ANOMALY")
                score += 20

    # 3. Cross-category outperformance
    # (Would need category data per market — approximate from titles)
    categories_won = set()
    for pos in closed_positions:
        pnl = float(pos.get("realizedPnl", 0) or 0)
        title = pos.get("title", "")
        if pnl > 0:
            # Simple category inference from title
            if any(w in title.lower() for w in ["president", "election", "vote"]):
                categories_won.add("politics")
            elif any(w in title.lower() for w in ["crypto", "bitcoin", "ethereum"]):
                categories_won.add("crypto")
            elif any(w in title.lower() for w in ["nfl", "nba", "game", "match"]):
                categories_won.add("sports")
            else:
                categories_won.add("other")

    if len(categories_won) >= 3:
        # Winning across 3+ unrelated categories is unusual
        # Check if Brier is very good
        brier, _ = calculate_brier_score(closed_positions)
        if brier < 0.10:
            flags.append("CROSS_CATEGORY_OUTPERFORMANCE")
            score += 30

    # 4. Concentrated near-resolution trading
    # (Would need resolution timestamps — skip for now, add when available)

    # 5. Pull enhanced flags from insider_detector database
    try:
        enhanced_flags, enhanced_score = get_enhanced_insider_flags(address)
        if enhanced_flags:
            # Merge flags, avoiding duplicates
            for ef in enhanced_flags:
                if ef not in flags:
                    flags.append(ef)
            # Take the higher score
            score = max(score, enhanced_score)
    except Exception:
        pass  # Silently fail if DB not available

    return flags, min(score, 100.0)


def get_enhanced_insider_flags(address: str) -> Tuple[List[str], float]:
    """
    Get insider flags from the insider_detector database.
    
    Returns (flags, score) or ([], 0) if not found.
    """
    if not WHALE_DB_PATH.exists():
        return [], 0.0
    
    try:
        conn = sqlite3.connect(WHALE_DB_PATH, timeout=10)
        rows = conn.execute("""
            SELECT flag_type, score FROM insider_flags WHERE address = ?
        """, (address,)).fetchall()
        conn.close()
        
        if not rows:
            return [], 0.0
        
        flags = [r[0] for r in rows]
        total_score = sum(r[1] * 10 for r in rows)  # Convert 1-3 to 10-30
        
        return flags, min(total_score, 100.0)
    except Exception:
        return [], 0.0


# ── Composite Elite Score ──────────────────────────────────────

def compute_elite_score(
    brier_skill: float,
    difficulty_acc: float,
    calmar: float,
    bayesian_wr: float,
    volume: float,
    num_trades: int
) -> float:
    """
    Compute composite elite score (0-100).

    Weights:
      25% — Brier skill (proper scoring rule)
      25% — Difficulty-adjusted accuracy (hard trades matter)
      25% — Risk-adjusted return (Calmar ratio)
      15% — Bayesian win rate (shrunk estimate)
      10% — Volume/activity bonus (consistent activity)
    """
    # Normalize each component to 0-100 scale
    brier_component = max(0, min(100, brier_skill * 100))
    diff_component = max(0, min(100, difficulty_acc * 100))
    calmar_component = max(0, min(100, calmar * 10))  # Calmar 10 = 100 score
    wr_component = max(0, min(100, bayesian_wr * 100))

    # Volume bonus: log scale, max at $1M+
    vol_bonus = min(100, math.log10(max(volume, 1)) * 20)

    # Trade count bonus: need at least 20 for full credit
    trade_bonus = min(1.0, num_trades / 20)

    score = (
        brier_component * 0.25 +
        diff_component * 0.25 +
        calmar_component * 0.25 +
        wr_component * 0.15 +
        vol_bonus * 0.10
    ) * trade_bonus  # Discount if too few trades

    return round(max(0, min(100, score)), 1)


def adjusted_elite_score(base_elite: float, tracked_bets: int,
                          tracked_accuracy: float) -> float:
    """
    Blend our own tracked performance into the elite score.

    As we accumulate tracked outcomes for a whale, their tracked win rate
    should increasingly influence the score.  This closes the feedback loop
    so that whales who lose on every tracked bet get down-ranked.

    Weight ramps linearly: 0% at <5 bets → 50% at 30+ bets.
    """
    if tracked_bets < 5:
        return base_elite  # Not enough tracked data yet

    # Weight increases with sample size (caps at 50% at 30+ tracked bets)
    track_weight = min(0.50, tracked_bets / 60)

    # tracked_accuracy on 0-100 scale
    tracked_component = tracked_accuracy * 100

    blended = base_elite * (1 - track_weight) + tracked_component * track_weight
    return round(max(0.0, min(100.0, blended)), 1)


def determine_signal_direction(tracked_bets: int,
                                tracked_accuracy: float) -> str:
    """
    Decide whether to FOLLOW, FADE, or SKIP a whale based on tracked
    performance.

    - FOLLOW: tracked accuracy > 55% (demonstrated edge)
    - FADE:   tracked accuracy < 35% with 10+ bets (consistently wrong)
    - SKIP:   inconclusive / not enough data
    """
    if tracked_bets < 10:
        return "FOLLOW"  # Default for new whales — benefit of the doubt

    if tracked_accuracy < 0.35:
        return "FADE"
    elif tracked_accuracy > 0.55:
        return "FOLLOW"
    else:
        return "SKIP"  # ~coin-flip territory, no edge either way


# ── Consensus Confidence Engine ───────────────────────────────

# Historical accuracy calibration: how often does N-whale consensus win?
# Fallback defaults — overridden by compute_dynamic_base_rates() when data exists.
_WHALE_COUNT_BASE_RATES = {
    1: 0.52, 2: 0.56, 3: 0.62, 4: 0.67, 5: 0.72,
    6: 0.76, 7: 0.79, 8: 0.81, 10: 0.84, 15: 0.87, 20: 0.89,
}

_CATEGORY_BASE_RATES = {
    "sports": 0.60, "politics": 0.56, "crypto": 0.48,
    "esports": 0.58, "soccer": 0.60, "other": 0.54,
}


def compute_dynamic_base_rates(db_path: str = None) -> None:
    """
    Recompute _CATEGORY_BASE_RATES from actual resolved positions.

    Called at startup or periodically. Falls back to defaults if < 20
    resolved positions exist for a category.
    """
    import sqlite3 as _sql
    from pathlib import Path as _Path

    global _CATEGORY_BASE_RATES

    if db_path is None:
        db_path = str(_Path(__file__).parent / "data" / "whale_hunter.db")

    try:
        conn = _sql.connect(db_path, timeout=10)
        rows = conn.execute("""
            SELECT market_title, outcome FROM whale_positions
            WHERE outcome IN ('won', 'lost')
        """).fetchall()
        conn.close()
    except Exception:
        return  # Keep defaults on any DB error

    from collections import defaultdict
    cat_wins = defaultdict(int)
    cat_total = defaultdict(int)

    for title, outcome in rows:
        cat = categorize_market(title or "")
        cat_total[cat] += 1
        if outcome == "won":
            cat_wins[cat] += 1

    updated = 0
    for cat, total in cat_total.items():
        if total >= 20:  # Need meaningful sample
            rate = cat_wins[cat] / total
            _CATEGORY_BASE_RATES[cat] = round(rate, 3)
            updated += 1

    if updated:
        logger.info(f"Dynamic base rates updated ({updated} categories): {_CATEGORY_BASE_RATES}")


def _interpolate_base_rate(whale_count: int) -> float:
    """Interpolate base rate for any whale count."""
    keys = sorted(_WHALE_COUNT_BASE_RATES.keys())
    if whale_count <= keys[0]:
        return _WHALE_COUNT_BASE_RATES[keys[0]]
    if whale_count >= keys[-1]:
        return _WHALE_COUNT_BASE_RATES[keys[-1]]
    for i in range(len(keys) - 1):
        if keys[i] <= whale_count <= keys[i + 1]:
            lo, hi = keys[i], keys[i + 1]
            frac = (whale_count - lo) / (hi - lo)
            return _WHALE_COUNT_BASE_RATES[lo] + frac * (
                _WHALE_COUNT_BASE_RATES[hi] - _WHALE_COUNT_BASE_RATES[lo]
            )
    return 0.55


def calculate_consensus_confidence(
    whale_count: int,
    avg_elite: float,
    agreement_pct: float,
    avg_entry_price: float,
    hours_since_first: float,
    unique_whales: int,
    category: str,
    mirofish_prob: float = 0.0,
    mirofish_status: str = "not_run",
) -> dict:
    """
    Bayesian confidence scoring for a consensus market.

    Returns dict with:
      confidence_pct  – continuous 0-100
      tier            – GREEN / YELLOW / RED
      kelly_fraction  – suggested Kelly bet size (fifth-Kelly)
      factors         – breakdown of each component
    """
    # 1. Base rate from whale count
    base = _interpolate_base_rate(whale_count)

    # 2. Elite score adjustment (0.8–1.2 range)
    elite_adj = 0.8 + 0.4 * (avg_elite / 100)

    # 3. Agreement multiplier (unanimous = 1.1, bare majority = 0.85)
    agreement_adj = 0.7 + 0.4 * agreement_pct

    # 4. Price efficiency: entry near 0.5 = max uncertainty (good entry),
    #    entry near 0 or 1 = expensive / obvious bet
    price_eff = 1.0 - abs(avg_entry_price - 0.5) * 0.6

    # 5. Freshness: recent consensus is stronger signal
    freshness = 1.0 / (1.0 + hours_since_first / 48)

    # 6. Whale diversity: more unique wallets = more independent signals
    diversity = min(unique_whales / 5, 1.0)

    # 7. Category base rate
    cat_rate = _CATEGORY_BASE_RATES.get(category.lower(), 0.54)

    # Combine multiplicatively and normalise to 0-1
    raw = base * elite_adj * agreement_adj * price_eff * freshness * (0.8 + 0.2 * diversity) * cat_rate
    # Scale so typical strong consensus lands around 70-85%
    # Empirically: 20+ whales with 85%+ agreement should hit GREEN (70%+)
    # 3 whales with moderate agreement should be YELLOW (~55-65%)
    confidence = min(max(raw / 0.45, 0.0), 1.0)

    # MiroFish boost/penalty
    if mirofish_status == "confirmed":
        confidence = min(confidence * 1.12, 1.0)  # +12% boost
    elif mirofish_status == "disagrees":
        confidence *= 0.75  # –25% penalty

    confidence_pct = round(confidence * 100, 1)

    # Tier classification
    if confidence_pct >= 70 and whale_count >= 3:
        tier = "GREEN"
    elif confidence_pct >= 50 and whale_count >= 2:
        tier = "YELLOW"
    else:
        tier = "RED"

    # Kelly sizing (fifth-Kelly, conservative)
    implied_edge = confidence - 0.5
    kelly = max(0.0, implied_edge / 5)  # fifth-Kelly

    return {
        "confidence_pct": confidence_pct,
        "tier": tier,
        "kelly_fraction": round(kelly, 4),
        "factors": {
            "base_rate": round(base, 3),
            "elite_adj": round(elite_adj, 3),
            "agreement_adj": round(agreement_adj, 3),
            "price_efficiency": round(price_eff, 3),
            "freshness": round(freshness, 3),
            "diversity": round(diversity, 3),
            "category_rate": round(cat_rate, 3),
            "mirofish_boost": mirofish_status,
        },
    }


def categorize_market(title: str) -> str:
    """Infer market category from title keywords."""
    t = title.lower()

    # ── Crypto ──
    if any(w in t for w in [
        "bitcoin", "btc", "ethereum", "eth ", "crypto", "solana", "sol ",
        "xrp", "dogecoin", "doge", "cardano", "polygon", "avalanche",
        "chainlink", "litecoin", "token", "defi", "nft", "binance",
        "coinbase",
    ]):
        return "crypto"

    # ── Politics / Geopolitics ──
    if any(w in t for w in [
        "president", "election", "vote", "governor", "senate", "trump",
        "biden", "congress", "republican", "democrat", "vance", "desantis",
        "supreme court", "impeach", "legislation", "bill pass",
        "iran", "israel", "ukraine", "russia", "ceasefire", "regime",
        "sanctions", "invasion", "military", "strike iran", "nato",
        "china", "taiwan", "north korea", "khamenei", "pahlavi",
        "maduro", "venezuela", "strait of hormuz",
        "tax pass", "tariff", "government shutdown", "debt ceiling",
        "fed chair", "nominate", "confirmation hearing",
    ]):
        return "politics"

    # ── Esports ──
    if any(w in t for w in [
        "lol:", "dota", "counter-strike", "valorant", "esport",
        "league of legends", "overwatch", "bo3)", "bo5)",
        "game 1 winner", "game 2 winner", "game 3 winner",
        "map 1 winner", "game handicap:",
    ]):
        return "esports"

    # ── Soccer ──
    if any(w in t for w in [
        "fc ", "fc)", " fc", "atletico", "calcio", "napoli",
        "leverkusen", "barcelona", "real madrid", "liverpool", "arsenal",
        "chelsea", "tottenham", "juventus", "bayern", "psg", "inter milan",
        "ac milan", "dortmund", "toulouse", "lorient", "brentford",
        "newcastle", "west ham", "kilmarnock", "parma", "coventry",
        "premier league", "la liga", "serie a", "bundesliga", "ligue 1",
        "champions league", "europa league", "end in a draw",
        "fiorentina", "mainz", "wolfsburg", "roma", "lazio", "sevilla",
        "benfica", "porto", "celtic", "rangers", "ajax", "feyenoord",
        "marseille", "lyon", "monaco", "fenerbahce", "galatasaray",
        "win on 2026", "win on 2025",
    ]):
        return "soccer"

    # ── Sports (general) ──
    if any(w in t for w in [
        "nba", "nfl", "nhl", "mlb", "ncaa", "spread:", "o/u ",
        "ufc", "boxing", "fight night", "mma", "welterweight",
        "middleweight", "lightweight", "heavyweight",
        "super bowl", "world series", "stanley cup", "march madness",
        "lakers", "celtics", "warriors", "nuggets", "bucks", "76ers",
        "knicks", "nets", "heat", "bulls", "rockets", "mavericks",
        "suns", "clippers", "pistons", "hawks", "jazz", "pacers",
        "raptors", "spurs", "magic", "hornets", "wizards", "pelicans",
        "timberwolves", "kings", "thunder", "grizzlies", "blazers",
        "cavaliers", "trail blazers",
        "chiefs", "eagles", "cowboys", "rams", "49ers", "ravens",
        "steelers", "packers", "bills", "dolphins", "bengals",
        "chargers", "patriots", "broncos", "colts", "saints",
        "panthers", "flames", "islanders", "canadiens", "bruins",
        "penguins", "capitals", "oilers", "canucks",
        "open:", "miami open", "grand slam", "atp", "wta",
        "gators", "wolverines", "bulldogs", "wildcats", "buckeyes",
        "crimson", "tigers", "longhorns", "seminoles", "huskies",
        "tournament",
    ]):
        return "sports"

    # ── Commodities / Macro ──
    if any(w in t for w in [
        "crude oil", "oil price", "wti", "brent", "opec", "natural gas",
        "gold price", "silver price", "copper", "wheat", "corn",
        "fed rate", "interest rate", "cpi", "inflation", "gdp",
        "unemployment", "fomc", "yield curve", "recession",
        "s&p 500", "nasdaq", "dow jones", "stock market",
    ]):
        return "macro"

    # ── Pop Culture / Tech ──
    if any(w in t for w in [
        "taylor swift", "oscar", "emmy", "grammy", "box office",
        "spotify", "youtube", "tiktok", "google", "apple",
        "tesla", "spacex", "elon musk", "self driv", "epstein",
    ]):
        return "culture"

    # ── Fallback: "vs." pattern likely sports ──
    if " vs." in t or " vs " in t:
        return "sports"

    return "other"


# ── Main Scoring Function ─────────────────────────────────────

def score_trader(
    address: str,
    display_name: str,
    pnl: float,
    volume: float,
    positions: List[Dict],
    closed_positions: List[Dict],
    activity: List[Dict]
) -> Optional[WhaleProfile]:
    """
    Score a trader using proper statistical methods.

    Returns WhaleProfile with elite_score, or None if insufficient data.
    """
    num_closed = len(closed_positions)
    if num_closed < 5:
        logger.debug(f"Skipping {display_name}: only {num_closed} closed positions")
        return None

    # 1. Brier score
    brier, skill = calculate_brier_score(closed_positions)

    # 2. Difficulty-adjusted accuracy
    easy_acc, hard_acc, diff_combined = calculate_difficulty_adjusted_accuracy(
        closed_positions
    )

    # 3. Win rate (raw + Bayesian)
    wins = sum(1 for p in closed_positions if float(p.get("realizedPnl", 0) or 0) > 0)
    raw_wr = wins / num_closed
    bayesian_wr = bayesian_shrinkage(raw_wr, num_closed)

    # 4. Risk metrics
    total_invested = sum(
        float(p.get("totalBought", 0) or p.get("initialValue", 0) or 0)
        for p in closed_positions
    )
    roi, max_dd, calmar = calculate_risk_metrics(closed_positions, total_invested)

    # 5. Elite score
    elite = compute_elite_score(
        skill, diff_combined, calmar, bayesian_wr, volume, num_closed
    )

    # 6. Insider detection
    insider_flags, insider_score = detect_insider_patterns(
        address, activity, closed_positions, num_closed
    )

    # 7. Categories traded
    categories = set()
    for pos in closed_positions:
        title = pos.get("title", "")
        if any(w in title.lower() for w in ["president", "election", "vote"]):
            categories.add("politics")
        elif any(w in title.lower() for w in ["crypto", "bitcoin"]):
            categories.add("crypto")
        elif any(w in title.lower() for w in ["nfl", "nba", "game"]):
            categories.add("sports")
        else:
            categories.add("other")

    # 8. Average position size
    avg_size = (
        sum(float(p.get("totalBought", 0) or 0) for p in closed_positions)
        / max(num_closed, 1)
    )

    return WhaleProfile(
        address=address,
        display_name=display_name,
        pnl=pnl,
        volume=volume,
        num_trades=num_closed,
        win_rate_raw=round(raw_wr, 4),
        brier_score=brier,
        brier_skill=skill,
        difficulty_adjusted_acc=diff_combined,
        bayesian_win_rate=bayesian_wr,
        realized_roi=roi,
        max_drawdown=max_dd,
        calmar_ratio=calmar,
        elite_score=elite,
        categories=sorted(categories),
        avg_position_size=round(avg_size, 2),
        insider_flags=insider_flags,
        insider_score=insider_score,
    )


def rank_traders(
    profiles: List[WhaleProfile],
    min_trades: int = 10,
    min_elite_score: float = 0.0,
    max_insider_flags: int = 2
) -> List[WhaleProfile]:
    """
    Filter and rank traders by elite score.
    Excludes wallets with too many insider flags or too few trades.
    """
    filtered = [
        p for p in profiles
        if p.num_trades >= min_trades
        and p.elite_score >= min_elite_score
        and len(p.insider_flags) <= max_insider_flags
    ]
    return sorted(filtered, key=lambda p: p.elite_score, reverse=True)


# Shared cache for market endDate data (populated by lookup_token_side)
_end_date_cache: Dict[str, str] = {}


def lookup_token_side(token_id: str, side_cache: Dict = None) -> Optional[str]:
    """
    Determine whether a token_id is the YES or NO token for its market.

    Looks up the market via Gamma API using clob_token_ids param.
    clobTokenIds[0] = YES, clobTokenIds[1] = NO.

    Uses side_cache dict to avoid repeated API calls for same token.
    Also caches endDate in _end_date_cache for freshness filtering.
    Returns "YES", "NO", or None if lookup fails.
    """
    import requests
    import json as _json

    if not token_id:
        return None

    # Check cache first
    if side_cache is not None and token_id in side_cache:
        return side_cache[token_id]

    try:
        resp = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"clob_token_ids": token_id},
            timeout=15,
        )
        if not resp.ok:
            return None

        data = resp.json()
        if not data:
            return None

        market = data[0] if isinstance(data, list) else data
        clob_ids = market.get("clobTokenIds", [])
        if isinstance(clob_ids, str):
            try:
                clob_ids = _json.loads(clob_ids)
            except Exception:
                clob_ids = []

        # Cache endDate for ALL tokens in this market
        end_date = market.get("endDate", "")
        if end_date:
            for cid in clob_ids:
                _end_date_cache[cid] = end_date

        side = None
        if len(clob_ids) >= 2:
            if token_id == clob_ids[0]:
                side = "YES"
            elif token_id == clob_ids[1]:
                side = "NO"

            # Cache BOTH tokens from this market
            if side_cache is not None:
                side_cache[clob_ids[0]] = "YES"
                side_cache[clob_ids[1]] = "NO"

        return side

    except Exception as e:
        logger.debug(f"Token side lookup failed for {token_id[:20]}: {e}")
        return None


def get_cached_end_date(token_id: str) -> str:
    """Get cached endDate for a token_id (populated by lookup_token_side)."""
    return _end_date_cache.get(token_id, "")


def batch_lookup_token_sides(token_ids: List[str], side_cache: Dict) -> None:
    """
    Batch lookup YES/NO sides for multiple token_ids in chunks.
    Populates side_cache in-place. Much faster than individual lookups.
    """
    import requests
    import json as _json
    
    # Filter to uncached tokens only
    uncached = [t for t in token_ids if t and t not in side_cache]
    if not uncached:
        return
    
    # Process in chunks of 20 (API may have limits)
    CHUNK_SIZE = 20
    for i in range(0, len(uncached), CHUNK_SIZE):
        chunk = uncached[i:i + CHUNK_SIZE]
        try:
            # Gamma API accepts comma-separated token_ids
            resp = requests.get(
                "https://gamma-api.polymarket.com/markets",
                params={"clob_token_ids": ",".join(chunk)},
                timeout=15,
            )
            if not resp.ok:
                continue
            
            data = resp.json()
            if not data:
                continue
            
            markets = data if isinstance(data, list) else [data]
            for market in markets:
                clob_ids = market.get("clobTokenIds", [])
                if isinstance(clob_ids, str):
                    try:
                        clob_ids = _json.loads(clob_ids)
                    except Exception:
                        clob_ids = []
                
                # Cache endDate
                end_date = market.get("endDate", "")
                if end_date:
                    for cid in clob_ids:
                        _end_date_cache[cid] = end_date
                
                # Cache YES/NO sides
                if len(clob_ids) >= 2:
                    side_cache[clob_ids[0]] = "YES"
                    side_cache[clob_ids[1]] = "NO"
        except Exception as e:
            logger.debug(f"Batch token lookup failed: {e}")
            continue


def extract_positions(
    address: str, raw_positions: List[Dict],
    side_cache: Dict = None,
    skip_side_lookup: bool = False
) -> List[WhalePosition]:
    """
    Convert raw API positions to WhalePosition objects.

    When skip_side_lookup=False (default): Uses Gamma API batch lookup to
    determine YES/NO side. Accurate but slow (5+ API calls per whale).

    When skip_side_lookup=True: Uses only cached values and price heuristic.
    Fast (no API calls) but ~10% side errors. Use for position DETECTION;
    correct side is determined later during RESOLUTION.

    Pass side_cache={} to enable caching across multiple calls.
    """
    if side_cache is None:
        side_cache = {}

    # Batch lookup all token_ids upfront — ONLY if not skipping
    if not skip_side_lookup:
        all_token_ids = [pos.get("asset", "") for pos in raw_positions]
        batch_lookup_token_sides(all_token_ids, side_cache)

    results = []
    for pos in raw_positions:
        size = float(pos.get("size", 0) or 0)
        entry = float(pos.get("avgPrice", 0.5) or 0.5)
        current = float(pos.get("curPrice", entry) or entry)
        initial_val = float(pos.get("initialValue", 0) or 0)
        current_val = float(pos.get("currentValue", 0) or 0)
        token_id = pos.get("asset", "")

        # Determine side: check cache first, then API (if not skipped), then heuristic
        side = None
        if token_id and token_id in (side_cache or {}):
            side = side_cache[token_id]
        elif token_id and not skip_side_lookup:
            side = lookup_token_side(token_id, side_cache)

        if side is None:
            # Fallback heuristic (may be wrong for ~50% of cases)
            side = "YES" if entry > 0.5 else "NO"
            logger.warning(
                f"Side heuristic fallback for {pos.get('title', '?')[:30]} "
                f"(no token_id or API miss)"
            )

        # endDate: try raw position data first, then cached from Gamma lookup
        end_date = pos.get("endDate", "") or get_cached_end_date(token_id)

        results.append(WhalePosition(
            market_title=pos.get("title", pos.get("market", "Unknown")),
            condition_id=pos.get("conditionId", ""),
            token_id=token_id,
            side=side,
            size=size,
            size_usd=initial_val,
            entry_price=entry,
            current_price=current,
            unrealized_pnl=current_val - initial_val,
            market_end_date=end_date,
            is_new=False,
        ))

    return results


# ── CLI Test ───────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("WHALE SCORER — Test with Live Data")
    print("=" * 60)

    from polymarket_api import PolymarketAPI

    api = PolymarketAPI(rate_limit=1.0)

    # Get top 5 from leaderboard
    print("\nFetching leaderboard...")
    leaders = api.get_leaderboard(limit=5)

    if not leaders:
        print("No leaderboard data. Exiting.")
        api.close()
        exit(1)

    profiles = []
    for entry in leaders:
        addr = entry.get("proxyWallet") or entry.get("address", "")
        name = entry.get("userName") or entry.get("username") or addr[:10]
        pnl = float(entry.get("pnl", 0) or 0)
        vol = float(entry.get("vol", 0) or entry.get("volume", 0) or 0)

        print(f"\n{'─' * 50}")
        print(f"Scoring {name} ({addr[:16]}...)  PnL: ${pnl:,.2f}")

        # Fetch wallet data
        positions = api.get_positions(addr)
        closed = api.get_closed_positions(addr)
        activity = api.get_activity(addr)

        print(f"  Open positions: {len(positions)}, "
              f"Closed: {len(closed)}, "
              f"Activity: {len(activity)}")

        profile = score_trader(addr, name, pnl, vol, positions, closed, activity)

        if profile:
            profiles.append(profile)
            print(f"  Elite Score:    {profile.elite_score}/100")
            print(f"  Brier Score:    {profile.brier_score:.4f} "
                  f"(skill: {profile.brier_skill:.4f})")
            print(f"  Win Rate:       {profile.win_rate_raw:.1%} raw → "
                  f"{profile.bayesian_win_rate:.1%} Bayesian")
            print(f"  Difficulty Adj: {profile.difficulty_adjusted_acc:.1%}")
            print(f"  ROI:            {profile.realized_roi:.1%}")
            print(f"  Max Drawdown:   ${profile.max_drawdown:,.2f}")
            print(f"  Calmar Ratio:   {profile.calmar_ratio:.2f}")
            print(f"  Categories:     {', '.join(profile.categories)}")
            if profile.insider_flags:
                print(f"  [WARN] Insider Flags: {', '.join(profile.insider_flags)}")
        else:
            print(f"  ⏩ Insufficient data")

    # Rank
    ranked = rank_traders(profiles, min_trades=5, min_elite_score=0)
    print(f"\n{'=' * 60}")
    print(f"RANKED TRADERS ({len(ranked)} qualified)")
    print(f"{'=' * 60}")
    for i, p in enumerate(ranked):
        insider = " [WARN]" if p.insider_flags else ""
        print(f"  #{i+1} {p.display_name:20s} "
              f"Score: {p.elite_score:5.1f}  "
              f"Brier: {p.brier_score:.3f}  "
              f"WR: {p.bayesian_win_rate:.0%}  "
              f"ROI: {p.realized_roi:+.0%}{insider}")

    api.close()
