#!/usr/bin/env python3
"""
WHALE HUNTER CONNECTOR — Polymarket Elite Trader Tracking + MiroFish Validation

Pipeline:
  1. Pull leaderboard from Polymarket Data API
  2. Score traders with Brier scores, difficulty-adjusted accuracy, Bayesian shrinkage
  3. Detect new positions from elite wallets
  4. Validate whale trades through MiroFish swarm simulation
  5. Generate Kelly-sized trade signals when edge >= 8%

Position Sizing:
  Fifth-Kelly criterion with $3K max per trade, 8% min edge.

Usage:
    python whale_hunter_connector.py                  # Health check
    python whale_hunter_connector.py --test           # Test sim on top whale's position
    python whale_hunter_connector.py --scan           # Full scan + simulate
    python whale_hunter_connector.py --scan --top 5   # Simulate top 5 whale positions
"""

import argparse
import json
import sqlite3
import sys
import uuid
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Telegram alerting
TELEGRAM_BOT_TOKEN = "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU"
TELEGRAM_CHAT_ID = "939543801"

def send_telegram_alert(message: str) -> bool:
    """Send alert to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, data=data, timeout=10)
        return resp.ok
    except Exception:
        return False

sys.path.insert(0, str(Path(__file__).parent))
from mirofish_client import MiroFishClient
from outcome_tracker import OutcomeTracker
from report_parser import extract_consensus_from_report
from polymarket_api import PolymarketAPI
from whale_scorer import (
    WhaleProfile, WhalePosition, score_trader, rank_traders,
    extract_positions, adjusted_elite_score, determine_signal_direction,
)
from whale_cluster import (
    build_wallet_behavior, build_similarity_graph, find_clusters,
    summarize_cluster, save_clusters, load_clusters
)


# ── Constants ──────────────────────────────────────────────────

PREDICTIONS_LOG = Path(__file__).parent / "whale_hunter_predictions.jsonl"
WHALE_DB = Path(__file__).parent / "data" / "whale_hunter.db"
TOP_LEADERBOARD = 100        # Score top N wallets per scan (expanded from 50)
MIN_ELITE_SCORE = 20         # Minimum elite score to track (starts low, raise with data)
MIN_EDGE = 0.08              # 8% edge for trade signal
MAX_POSITION = 3000          # $3K max per trade
KELLY_DIVISOR = 5            # Fifth-Kelly (conservative for whale-following)
MAX_INSIDER_FLAGS = 3        # Max insider flags before exclusion (was 1, blocked 95% of whales)
BANKROLL = 10_000            # Paper trading bankroll

# Alert priority thresholds
ALERT_URGENT_EDGE = 0.15     # 15%+ edge = 🚨 URGENT
ALERT_HIGH_EDGE = 0.10       # 10%+ edge = ⚠️ HIGH
# Below 10% = 📊 NORMAL


def sync_dashboard():
    """Export whale data and sync to Mac Mini dashboard.
    
    CRITICAL: This must run after every scan to prevent stale data!
    - Exports only fresh data (pending <7 days, resolved <3 days)
    - Syncs to Mac Mini immediately
    - Validates data freshness before upload
    """
    import subprocess
    from datetime import datetime
    
    try:
        print("\n[SYNC] Syncing dashboard...", flush=True)
        
        # Step 1: Run export script (creates fresh JSON)
        export_script = Path(__file__).parent / "export_whale_data.py"
        result = subprocess.run([sys.executable, str(export_script)], 
                      capture_output=True, timeout=60, text=True)
        if result.returncode != 0:
            print(f"[WARN] Export failed: {result.stderr}", flush=True)
            return
        print(f"  [OK] Export complete", flush=True)
        
        # Step 2: Verify the JSON is fresh (created in last 5 min)
        json_file = Path(__file__).parent / "data" / "whale_positions.json"
        if not json_file.exists():
            print(f"[WARN] JSON file not found at {json_file}", flush=True)
            return
        
        file_age_sec = (datetime.now().timestamp() - json_file.stat().st_mtime)
        if file_age_sec > 300:  # 5 minutes
            print(f"[WARN] JSON file is {file_age_sec:.0f}s old - regenerating", flush=True)
            subprocess.run([sys.executable, str(export_script)], 
                          capture_output=True, timeout=60)
        
        # Step 3: SCP to Mac Mini
        result = subprocess.run(
            ["scp", "-o", "ConnectTimeout=10", str(json_file), 
             "tommie@100.88.105.106:~/clawd/dashboard/data/whale_positions.json"],
            capture_output=True, timeout=30, text=True
        )
        if result.returncode == 0:
            print(f"  [OK] Dashboard synced to Mac Mini!", flush=True)
        else:
            print(f"  [WARN] SCP failed: {result.stderr}", flush=True)
            
    except subprocess.TimeoutExpired:
        print("[WARN] Dashboard sync timed out", flush=True)
    except Exception as e:
        print(f"[WARN] Dashboard sync error: {e}", flush=True)


def check_outcomes():
    """Check and resolve pending whale positions."""
    try:
        print("\n[TARGET] Checking bet outcomes...", flush=True)
        from whale_outcome_tracker import WhaleOutcomeTracker
        tracker = WhaleOutcomeTracker()
        result = tracker.check_and_resolve_all(limit=30)
        print(f"  Checked: {result['checked']}, Resolved: {result['resolved']} "
              f"([OK]{result['won']} / [FAIL]{result['lost']})", flush=True)
    except Exception as e:
        print(f"[WARN] Outcome check error: {e}", flush=True)


# ── Database ───────────────────────────────────────────────────

def _init_db():
    """Initialize whale hunter database."""
    WHALE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(WHALE_DB), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tracked_whales (
            address TEXT PRIMARY KEY,
            display_name TEXT,
            elite_score REAL,
            pnl REAL,
            volume REAL,
            brier_score REAL,
            brier_skill REAL,
            win_rate_raw REAL,
            bayesian_win_rate REAL,
            difficulty_adj_acc REAL,
            realized_roi REAL,
            max_drawdown REAL,
            calmar_ratio REAL,
            num_trades INTEGER,
            avg_position_size REAL,
            insider_flags TEXT,
            insider_score REAL,
            cluster_id TEXT,
            categories TEXT,
            first_seen TEXT,
            last_updated TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS whale_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT,
            condition_id TEXT,
            token_id TEXT,
            market_title TEXT,
            side TEXT,
            size REAL,
            size_usd REAL,
            entry_price REAL,
            current_price REAL,
            unrealized_pnl REAL,
            detected_at TEXT,
            signal_generated INTEGER DEFAULT 0,
            UNIQUE(address, condition_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_signals (
            signal_id TEXT PRIMARY KEY,
            whale_address TEXT,
            whale_name TEXT,
            whale_elite_score REAL,
            market_title TEXT,
            condition_id TEXT,
            direction TEXT,
            position_size REAL,
            kelly_fraction REAL,
            model_prob REAL,
            market_price REAL,
            edge REAL,
            whale_entry_price REAL,
            slippage_estimate REAL,
            simulation_id TEXT,
            report_id TEXT,
            status TEXT DEFAULT 'PAPER',
            created_at TEXT,
            resolved_at TEXT,
            pnl REAL
        )
    """)

    conn.commit()
    conn.close()


# ── Kelly Sizing ───────────────────────────────────────────────

def kelly_size(model_prob: float, market_prob: float,
               bankroll: float = BANKROLL) -> Tuple[float, float]:
    """
    Kelly criterion position sizing (fifth-Kelly for safety).

    Returns: (kelly_fraction, dollar_amount)
    """
    if model_prob <= market_prob:
        return 0.0, 0.0  # No edge

    # Binary outcome: p = model prob, b = payoff odds
    # Payoff: buy at market_prob, win $1 - market_prob
    b = (1 - market_prob) / max(market_prob, 0.01)  # Odds
    p = model_prob
    q = 1 - p

    # Kelly fraction: f* = (bp - q) / b
    f_star = (b * p - q) / max(b, 0.01)
    f_star = max(0, f_star)

    # Apply divisor (fifth-Kelly)
    f_adjusted = f_star / KELLY_DIVISOR

    # Dollar amount with cap
    dollar = min(f_adjusted * bankroll, MAX_POSITION)

    return round(f_adjusted, 4), round(dollar, 2)


# ── Seed Text Builder ─────────────────────────────────────────

def build_whale_seed_text(whale: WhaleProfile, position: WhalePosition,
                           orderbook_info: Dict = None) -> str:
    """Build rich seed text for MiroFish swarm simulation."""

    ob_section = ""
    if orderbook_info:
        ob_section = f"""
ORDERBOOK ANALYSIS:
  Best price: {orderbook_info.get('best_price', 'N/A')}
  Depth at 1%: ${orderbook_info.get('depth_1pct', 0):,.0f}
  Slippage est: {orderbook_info.get('slippage_pct', 0):.1%}
  Feasible: {'YES' if orderbook_info.get('feasible') else 'NO'}
"""

    insider_section = ""
    if whale.insider_flags:
        insider_section = f"""
⚠️ INSIDER FLAGS: {', '.join(whale.insider_flags)}
  Insider probability score: {whale.insider_score:.0f}/100
"""

    return f"""POLYMARKET WHALE TRADE ANALYSIS
============================================================
MARKET: {position.market_title}
CONDITION: {position.condition_id[:20]}...

WHALE PROFILE:
  Name/Handle: {whale.display_name}
  Address: {whale.address[:20]}...
  Elite Score: {whale.elite_score:.1f}/100
  Total PnL: ${whale.pnl:,.2f}
  Volume: ${whale.volume:,.2f}
  Brier Score: {whale.brier_score:.4f} (skill: {whale.brier_skill:.4f})
  Win Rate: {whale.win_rate_raw:.1%} raw -> {whale.bayesian_win_rate:.1%} Bayesian
  Difficulty-Adjusted Accuracy: {whale.difficulty_adjusted_acc:.1%}
  ROI: {whale.realized_roi:.1%}
  Max Drawdown: ${whale.max_drawdown:,.2f}
  Calmar Ratio: {whale.calmar_ratio:.2f}
  Categories: {', '.join(whale.categories)}
{insider_section}
POSITION DETAILS:
  Side: {position.side}
  Size: {position.size:,.2f} shares (${position.size_usd:,.2f})
  Entry Price: {position.entry_price:.4f}
  Current Price: {position.current_price:.4f}
  Unrealized P&L: ${position.unrealized_pnl:,.2f}
{ob_section}
SIMULATION OBJECTIVE:
Analyze whether this whale's position represents genuine informational edge
or is likely noise/manipulation. Consider:
  1. Does the whale's track record justify following this trade?
  2. What is the fair probability for this market given public information?
  3. Is the entry price favorable or has the whale already moved the market?
  4. Are there signs of coordinated multi-wallet manipulation?
  5. What is the expected slippage if we try to emulate this trade?

AGENT ROSTER (20 specialized analysts):
  - WhaleBehaviorAnalyst: Pattern recognition on whale trading history
  - MarketMicrostructureExpert: Orderbook dynamics, spread analysis
  - BlockchainAnalyst: On-chain flow analysis, wallet clustering
  - PredictionMarketResearcher: Market efficiency, information aggregation
  - ContrarianTrader: Argues against whale's thesis
  - QuantitativeAnalyst: Statistical edge calculation, Kelly sizing
  - RiskManager: Position sizing limits, correlation exposure
  - MarketMaker: Liquidity provision perspective, adverse selection
  - RetailSentimentTracker: Social media signals around this market
  - InstitutionalFlowAnalyst: Large-block trade pattern recognition
"""


# ── Simulation ─────────────────────────────────────────────────

def simulate_whale_trade(client: MiroFishClient, whale: WhaleProfile,
                          position: WhalePosition,
                          max_rounds: int = 24,
                          skip_graph: bool = False) -> Optional[Dict]:
    """
    Run MiroFish swarm simulation to validate a whale's trade.
    Returns prediction dict or None on failure.
    """
    seed_text = build_whale_seed_text(whale, position)

    sim_requirement = (
        f"Simulate expert prediction market discourse about: "
        f"'{position.market_title}'. "
        f"A high-performing Polymarket trader (elite score {whale.elite_score:.0f}/100, "
        f"PnL ${whale.pnl:,.0f}) has taken a ${position.size_usd:,.0f} "
        f"{position.side} position at {position.entry_price:.2f}. "
        f"Generate 20 specialized agents including whale behavior analysts, "
        f"market microstructure experts, blockchain analysts, contrarian traders, "
        f"and quantitative analysts. Have them debate on Twitter and Reddit "
        f"simultaneously, tracking consensus on whether this whale trade "
        f"represents genuine edge or noise."
    )

    project_name = (
        f"Whale Hunt: {whale.display_name} - "
        f"{position.market_title[:50]}"
    )

    try:
        print(f"  [WHALE] Simulating whale trade...")
        print(f"     Market: {position.market_title[:60]}")
        print(f"     Whale: {whale.display_name} (score {whale.elite_score:.0f})")
        print(f"     Position: {position.side} @ {position.entry_price:.4f}")

        result = client.run_dual_platform(
            simulation_requirement=sim_requirement,
            seed_text=seed_text,
            project_name=project_name,
            max_rounds=max_rounds,
            skip_graph=skip_graph,
        )

        prediction = {
            "connector": "whale_hunter",
            "whale_address": whale.address,
            "whale_name": whale.display_name,
            "whale_elite_score": whale.elite_score,
            "whale_brier_score": whale.brier_score,
            "market_title": position.market_title,
            "condition_id": position.condition_id,
            "side": position.side,
            "entry_price": position.entry_price,
            "position_size_usd": position.size_usd,
            "simulation_id": result.get("simulation_id"),
            "project_id": result.get("project_id"),
            "report_id": result.get("report_id"),
            "steps": result.get("steps"),
            "timestamp": datetime.now().isoformat(),
        }

        return prediction

    except Exception as e:
        print(f"  [FAIL] Simulation failed: {e}")
        return None


# ── Signal Generation ──────────────────────────────────────────

def generate_signal(whale: WhaleProfile, position: WhalePosition,
                     model_prob: float, market_price: float,
                     simulation_id: str, report_id: str,
                     slippage: float = 0.02) -> Optional[Dict]:
    """
    Generate a trade signal if edge is sufficient and compliance passes.

    Now supports FADE logic: if a whale has a proven losing track record,
    we invert their position (take the opposite side).

    Returns signal dict or None.
    """
    # Compliance gate
    if len(whale.insider_flags) > MAX_INSIDER_FLAGS:
        print(f"  [BLOCK] BLOCKED: {whale.display_name} has {len(whale.insider_flags)} "
              f"insider flags: {whale.insider_flags}")
        return None

    # ── Determine signal direction (FOLLOW / FADE / SKIP) ──────
    tracked_bets, tracked_acc = _get_tracked_performance(whale.address)
    sig_direction = determine_signal_direction(tracked_bets, tracked_acc)

    if sig_direction == "SKIP":
        print(f"  [SKIP] SKIP: {whale.display_name} has inconclusive tracked record "
              f"({tracked_bets} bets, {tracked_acc:.0%} accuracy)")
        return None

    # Determine our position direction
    if sig_direction == "FADE":
        # Invert the whale's position
        our_side = "NO" if position.side == "YES" else "YES"
        # When fading, our model_prob is inverted (we bet AGAINST the whale)
        effective_prob = 1.0 - model_prob
        effective_market = 1.0 - market_price
        print(f"  [SYNC] FADE MODE: whale is {position.side}, we go {our_side} "
              f"(tracked {tracked_bets} bets @ {tracked_acc:.0%})")
    else:
        our_side = position.side
        effective_prob = model_prob
        effective_market = market_price

    # Edge calculation (using effective prices for fade)
    edge = effective_prob - effective_market
    
    # Smart filter: time-aware edge adjustment
    try:
        from smart_filter import calculate_adjusted_edge, get_current_conditions
        adj_edge, time_mult, whale_mult, confidence = calculate_adjusted_edge(
            edge, whale.address
        )
        cond = get_current_conditions()
        print(f"  [SMART] {cond['emoji']} Edge {edge:+.1%} -> {adj_edge:+.1%} "
              f"(time:{time_mult:.2f}, whale:{whale_mult:.2f}, {confidence})")
        
        # Use adjusted edge for decision
        if adj_edge < MIN_EDGE:
            print(f"  [DOWN] No signal: adjusted edge {adj_edge:+.1%} below {MIN_EDGE:.0%} "
                  f"(raw edge was {edge:+.1%}, {sig_direction})")
            return None
        edge = adj_edge  # Use adjusted edge for Kelly sizing
    except ImportError:
        # Fall back to raw edge if smart_filter not available
        if edge < MIN_EDGE:
            print(f"  [DOWN] No signal: edge {edge:+.1%} below {MIN_EDGE:.0%} threshold "
                  f"(direction: {sig_direction})")
            return None

    # Kelly sizing
    fraction, dollar_amount = kelly_size(effective_prob, effective_market)
    if dollar_amount < 10:
        print(f"  [DOWN] No signal: Kelly size too small (${dollar_amount:.2f})")
        return None

    signal = {
        "signal_id": f"wh_{uuid.uuid4().hex[:12]}",
        "whale_address": whale.address,
        "whale_name": whale.display_name,
        "whale_elite_score": whale.elite_score,
        "market_title": position.market_title,
        "condition_id": position.condition_id,
        "direction": our_side,
        "signal_type": sig_direction,         # FOLLOW or FADE
        "whale_direction": position.side,      # What the whale actually holds
        "position_size": dollar_amount,
        "kelly_fraction": fraction,
        "model_prob": effective_prob,
        "market_price": effective_market,
        "edge": edge,
        "whale_entry_price": position.entry_price,
        "slippage_estimate": slippage,
        "simulation_id": simulation_id,
        "report_id": report_id,
        "status": "PAPER",
        "created_at": datetime.now().isoformat(),
    }

    # Persist
    conn = sqlite3.connect(str(WHALE_DB), timeout=10)
    conn.execute("""
        INSERT OR REPLACE INTO trade_signals
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        signal["signal_id"], signal["whale_address"], signal["whale_name"],
        signal["whale_elite_score"], signal["market_title"],
        signal["condition_id"], signal["direction"], signal["position_size"],
        signal["kelly_fraction"], signal["model_prob"], signal["market_price"],
        signal["edge"], signal["whale_entry_price"], signal["slippage_estimate"],
        signal["simulation_id"], signal["report_id"], signal["status"],
        signal["created_at"], None, None,
    ))
    # C7 fix: Mark whale position as having generated a signal
    conn.execute("""
        UPDATE whale_positions SET signal_generated = 1
        WHERE address = ? AND condition_id = ?
    """, (signal["whale_address"], signal["condition_id"]))
    conn.commit()
    conn.close()

    fade_label = " (FADING whale)" if sig_direction == "FADE" else ""
    print(f"\n  [TARGET] SIGNAL GENERATED{fade_label}:")
    print(f"     Market: {position.market_title[:60]}")
    print(f"     Direction: {our_side} ({sig_direction} -- whale holds {position.side})")
    print(f"     Swarm: {effective_prob:.0%} vs Market: {effective_market:.0%}")
    print(f"     Edge: {edge:+.1%}")
    print(f"     Size: ${dollar_amount:,.2f} (Kelly {fraction:.1%})")
    print(f"     Whale: {whale.display_name} (score {whale.elite_score:.0f})")

    # Send Telegram alert with priority levels
    fade_emoji = "🔄" if sig_direction == "FADE" else "🐋"
    
    # Priority based on edge
    if edge >= ALERT_URGENT_EDGE:
        priority = "🚨 URGENT"
        priority_bar = "█████"
    elif edge >= ALERT_HIGH_EDGE:
        priority = "⚠️ HIGH"
        priority_bar = "███░░"
    else:
        priority = "📊 NORMAL"
        priority_bar = "██░░░"
    
    alert_msg = f"""<b>{fade_emoji} {priority} — SIGNAL ({sig_direction})</b>

<b>Market:</b> {position.market_title[:50]}
<b>Direction:</b> {our_side}{fade_label}
<b>Edge:</b> {edge:+.1%} [{priority_bar}]

<b>Swarm:</b> {effective_prob:.0%} vs Market: {effective_market:.0%}
<b>Size:</b> ${dollar_amount:,.2f} (Kelly {fraction:.1%})

<b>Whale:</b> {whale.display_name} (Score: {whale.elite_score:.0f})
<b>Tracked:</b> {tracked_bets} bets @ {tracked_acc:.0%}

🆔 {signal['signal_id'][:12]}"""

    if send_telegram_alert(alert_msg):
        print("     [ALERT] Telegram alert sent!")
    else:
        print("     [WARN] Telegram alert failed")

    return signal


# ── Prediction Logging ─────────────────────────────────────────

def log_prediction(prediction: Dict):
    """Append prediction to JSONL log."""
    with open(PREDICTIONS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(prediction, ensure_ascii=False, default=str) + "\n")
    print(f"  [LOG] Logged to {PREDICTIONS_LOG.name}")


# ── Whale Discovery & Position Detection ──────────────────────

def fetch_and_score_whales(api: PolymarketAPI,
                            top_n: int = TOP_LEADERBOARD) -> List[WhaleProfile]:
    """
    Fetch leaderboard and score each wallet properly.
    """
    print(f"\n[STATS] Fetching top {top_n} leaderboard...")
    leaders = api.get_leaderboard(limit=top_n)

    if not leaders:
        print("  [WARN] No leaderboard data available")
        return []

    print(f"  Got {len(leaders)} leaderboard entries")
    profiles = []

    for i, entry in enumerate(leaders):
        addr = entry.get("proxyWallet") or entry.get("address", "")
        name = (entry.get("userName") or entry.get("username")
                or addr[:10])
        pnl = float(entry.get("pnl", 0) or 0)
        vol = float(entry.get("vol", 0) or entry.get("volume", 0) or 0)

        if not addr:
            continue

        print(f"  [{i+1}/{len(leaders)}] Scoring {name}...", end=" ", flush=True)

        # Skip whales scored in last 6 hours — use cached DB profile
        if _whale_recently_scored(addr, max_age_hours=6):
            cached = _load_whale_from_db(addr)
            if cached:
                profiles.append(cached)
                print(f"cached (score={cached.elite_score:.0f})", flush=True)
                continue

        # Fetch wallet data (reduced to 100 closed positions — Brier converges by ~30)
        positions = api.get_positions(addr)
        closed = api.get_closed_positions(addr, max_total=100)
        activity = api.get_activity(addr)

        profile = score_trader(addr, name, pnl, vol, positions, closed, activity)
        if profile:
            # ── Feedback loop: blend our tracked outcomes into elite score ──
            tracked_bets, tracked_acc = _get_tracked_performance(addr)
            if tracked_bets >= 5:
                old_score = profile.elite_score
                profile.elite_score = adjusted_elite_score(
                    profile.elite_score, tracked_bets, tracked_acc
                )
                direction = determine_signal_direction(tracked_bets, tracked_acc)
                print(f"score={profile.elite_score:.0f} "
                      f"(was {old_score:.0f}, tracked {tracked_bets} bets "
                      f"@ {tracked_acc:.0%} -> {direction})", flush=True)
            else:
                print(f"score={profile.elite_score:.0f}")

            profiles.append(profile)

            # Persist
            _persist_whale(profile)
        else:
            print("skip (insufficient data)")

    return profiles


def _get_tracked_performance(address: str) -> Tuple[int, float]:
    """Look up our own tracked outcomes for this whale from the DB."""
    try:
        conn = sqlite3.connect(str(WHALE_DB), timeout=10)
        row = conn.execute(
            "SELECT COALESCE(tracked_bets, 0), COALESCE(tracked_accuracy, 0) "
            "FROM tracked_whales WHERE address = ?",
            (address,)
        ).fetchone()
        conn.close()
        if row:
            return int(row[0]), float(row[1])
    except Exception:
        pass
    return 0, 0.0


def _load_whale_from_db(address: str) -> Optional[WhaleProfile]:
    """Load a cached WhaleProfile from the tracked_whales table."""
    try:
        conn = sqlite3.connect(str(WHALE_DB), timeout=10)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM tracked_whales WHERE address = ?", (address,)
        ).fetchone()
        conn.close()
        if not row:
            return None

        flags = []
        try:
            flags = json.loads(row["insider_flags"] or "[]")
        except Exception:
            pass

        cats = []
        try:
            cats = json.loads(row["categories"] or "[]")
        except Exception:
            pass

        return WhaleProfile(
            address=row["address"],
            display_name=row["display_name"],
            pnl=row["pnl"] or 0,
            volume=row["volume"] or 0,
            num_trades=row["num_trades"] or 0,
            win_rate_raw=row["win_rate_raw"] or 0,
            brier_score=row["brier_score"] or 0.25,
            brier_skill=row["brier_skill"] or 0,
            difficulty_adjusted_acc=row["difficulty_adj_acc"] or 0,
            bayesian_win_rate=row["bayesian_win_rate"] or 0.5,
            realized_roi=row["realized_roi"] or 0,
            max_drawdown=row["max_drawdown"] or 0,
            calmar_ratio=row["calmar_ratio"] or 0,
            elite_score=row["elite_score"] or 0,
            categories=cats,
            avg_position_size=row["avg_position_size"] or 0,
            insider_flags=flags,
            insider_score=row["insider_score"] or 0,
        )
    except Exception:
        return None


def _whale_recently_scored(address: str, max_age_hours: int = 6) -> bool:
    """Check if a whale was scored recently enough to skip re-scoring."""
    try:
        conn = sqlite3.connect(str(WHALE_DB), timeout=10)
        row = conn.execute(
            "SELECT last_updated FROM tracked_whales WHERE address = ?",
            (address,)
        ).fetchone()
        conn.close()
        if row and row[0]:
            from datetime import timedelta
            last = datetime.fromisoformat(row[0])
            return (datetime.now() - last) < timedelta(hours=max_age_hours)
    except Exception:
        pass
    return False


def _persist_whale(whale: WhaleProfile, max_retries: int = 5):
    """Save whale profile to database, preserving outcome tracking columns."""
    import time as _time
    
    for attempt in range(max_retries):
        conn = None
        try:
            conn = sqlite3.connect(str(WHALE_DB), timeout=60)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=60000")
            now = datetime.now().isoformat()

            # Check if exists for first_seen
            cursor = conn.execute(
                "SELECT first_seen FROM tracked_whales WHERE address = ?",
                (whale.address,)
            )
            row = cursor.fetchone()
            first_seen = row[0] if row else now

            # Use explicit column names + ON CONFLICT to preserve
            # tracked_bets, winning_bets, tracked_accuracy (set by outcome tracker)
            conn.execute("""
                INSERT INTO tracked_whales
                    (address, display_name, elite_score, pnl, volume,
                     brier_score, brier_skill, win_rate_raw, bayesian_win_rate,
                     difficulty_adj_acc, realized_roi, max_drawdown, calmar_ratio,
                     num_trades, avg_position_size, insider_flags, insider_score,
                     cluster_id, categories, first_seen, last_updated)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(address) DO UPDATE SET
                    display_name = excluded.display_name,
                    elite_score = excluded.elite_score,
                    pnl = excluded.pnl,
                    volume = excluded.volume,
                    brier_score = excluded.brier_score,
                    brier_skill = excluded.brier_skill,
                    win_rate_raw = excluded.win_rate_raw,
                    bayesian_win_rate = excluded.bayesian_win_rate,
                    difficulty_adj_acc = excluded.difficulty_adj_acc,
                    realized_roi = excluded.realized_roi,
                    max_drawdown = excluded.max_drawdown,
                    calmar_ratio = excluded.calmar_ratio,
                    num_trades = excluded.num_trades,
                    avg_position_size = excluded.avg_position_size,
                    insider_flags = excluded.insider_flags,
                    insider_score = excluded.insider_score,
                    categories = excluded.categories,
                    last_updated = excluded.last_updated
            """, (
                whale.address, whale.display_name, whale.elite_score,
                whale.pnl, whale.volume, whale.brier_score, whale.brier_skill,
                whale.win_rate_raw, whale.bayesian_win_rate, whale.difficulty_adjusted_acc,
                whale.realized_roi, whale.max_drawdown, whale.calmar_ratio,
                whale.num_trades, whale.avg_position_size,
                json.dumps(whale.insider_flags), whale.insider_score,
                None,  # cluster_id (set by clustering)
                json.dumps(whale.categories),
                first_seen, now,
            ))
            conn.commit()
            conn.close()
            return  # Success!
            
        except sqlite3.OperationalError as e:
            if conn:
                try:
                    conn.close()
                except Exception:  # H12 FIX: Never use bare except
                    pass
            if "locked" in str(e) and attempt < max_retries - 1:
                _time.sleep(2 * (attempt + 1))  # Exponential backoff
                continue
            raise


def aggressive_stale_sweep() -> dict:
    """C6 FIX: Aggressive stale sweep — clean expired, epoch-bugged, and resolved positions.

    Runs three SQL operations:
    1. Mark expired: end_date > 2 hours past and still pending
    2. Mark epoch bugs: end_date in 1970 or before 2020 (bad data)
    3. Auto-resolve: current_price >= 0.99 or <= 0.01 clearly indicates outcome
    """
    try:
        conn = sqlite3.connect(str(WHALE_DB), timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")

        # 1. Mark positions as expired where end_date is >2 hours past
        expired = conn.execute("""
            UPDATE whale_positions
            SET outcome = 'expired'
            WHERE outcome = 'pending'
              AND end_date IS NOT NULL AND end_date != ''
              AND datetime(end_date) < datetime('now', '-2 hours')
        """).rowcount

        # 2. Mark epoch-bugged positions (1970 dates or before 2020)
        epoch_bugs = conn.execute("""
            UPDATE whale_positions
            SET outcome = 'expired'
            WHERE outcome = 'pending'
              AND end_date IS NOT NULL AND end_date != ''
              AND (end_date LIKE '1970%' OR end_date < '2020-01-01')
        """).rowcount

        # 3. Auto-resolve positions where price clearly indicates outcome (H14)
        auto_won = conn.execute("""
            UPDATE whale_positions
            SET outcome = CASE
                    WHEN side = 'YES' AND current_price >= 0.99 THEN 'won'
                    WHEN side = 'NO' AND current_price <= 0.01 THEN 'won'
                    WHEN side = 'YES' AND current_price <= 0.01 THEN 'lost'
                    WHEN side = 'NO' AND current_price >= 0.99 THEN 'lost'
                END,
                resolved_at = datetime('now')
            WHERE outcome = 'pending'
              AND current_price IS NOT NULL
              AND (current_price >= 0.99 OR current_price <= 0.01)
        """).rowcount

        conn.commit()
        conn.close()

        total = expired + epoch_bugs + auto_won
        if total > 0:
            print(f"  [SWEEP] Aggressive stale sweep: {expired} expired, {epoch_bugs} epoch-bugs, {auto_won} auto-resolved")
        return {"expired": expired, "epoch_bugs": epoch_bugs, "auto_resolved": auto_won, "total": total}
    except Exception as e:
        print(f"  [WARN] Aggressive stale sweep failed: {e}")
        return {"expired": 0, "epoch_bugs": 0, "auto_resolved": 0, "total": 0}


def detect_new_positions(api: PolymarketAPI,
                          whales: List[WhaleProfile]) -> List[Tuple[WhaleProfile, WhalePosition]]:
    """
    Detect NEW positions from elite wallets.

    Two sources (fixes survivorship bias):
      1. /positions — current open positions (may miss fast-resolving winners)
      2. /closed-positions — recently closed positions we never saw while open

    Compares against whale_positions table to find new entries only.
    """
    from datetime import timedelta

    # C6 FIX: Run aggressive stale sweep before scanning for new positions
    aggressive_stale_sweep()

    conn = sqlite3.connect(str(WHALE_DB), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")  # Enable concurrent access
    conn.execute("PRAGMA busy_timeout=30000")  # 30s retry on lock
    new_positions = []
    side_cache = {}  # Cache token_id -> side across all whales

    elite_whales = [w for w in whales if w.elite_score >= MIN_ELITE_SCORE]
    print(f"\n[SCAN] Scanning {len(elite_whales)} elite wallets for new positions...")

    skipped_underwater = 0
    skipped_resolved = 0
    closed_detected = 0

    for idx, whale in enumerate(elite_whales):
        print(f"  [{idx+1}/{len(elite_whales)}] {whale.display_name[:20]}...", end="", flush=True)
        positions = []
        
        # ── Source 1: Current open positions (15s timeout) ──────────
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(api.get_positions, whale.address)
                try:
                    raw_positions = future.result(timeout=15)
                    positions = extract_positions(whale.address, raw_positions,
                                                  side_cache=side_cache, skip_side_lookup=True)
                    print(f" {len(positions)}pos", end="", flush=True)
                except concurrent.futures.TimeoutError:
                    print(" TIMEOUT", end="", flush=True)
                    raw_positions = []
        except Exception as e:
            print(" err1", end="", flush=True)

        # ── Source 2: Recently closed positions (15s timeout, 1 page only) ──
        try:
            cutoff_ts = int((datetime.now() - timedelta(hours=48)).timestamp())
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    api.get_closed_positions, whale.address,
                    start=cutoff_ts, limit=50, max_total=50  # 1 page, not 10
                )
                try:
                    recent_closed = future.result(timeout=15)
                    closed_positions = extract_positions(whale.address, recent_closed,
                                                        side_cache=side_cache, skip_side_lookup=True)
                    positions.extend(closed_positions)
                    print(f"+{len(closed_positions)}cl", end="", flush=True)
                except concurrent.futures.TimeoutError:
                    print(" T2", end="", flush=True)
        except Exception as e:
            print(" err2", end="", flush=True)

        print(f" = {len(positions)} total", flush=True)
        for pos in positions:
            if not pos.condition_id:
                continue

            # LAYER 1: Reject already-resolved markets (price at 0 or 1)
            if pos.current_price >= 0.95 or pos.current_price <= 0.05:
                skipped_resolved += 1
                continue

            # Skip positions already deeply underwater (disposition effect filter)
            if pos.size_usd > 0 and pos.unrealized_pnl < -pos.size_usd * 0.3:
                skipped_underwater += 1
                continue

            # Check if we've seen this position before
            cursor = conn.execute(
                "SELECT id FROM whale_positions WHERE address = ? AND condition_id = ?",
                (whale.address, pos.condition_id)
            )
            if cursor.fetchone():
                continue  # Already tracked

            # New position!
            pos.is_new = True
            new_positions.append((whale, pos))

            # Determine signal direction for alert context
            tracked_bets, tracked_acc = _get_tracked_performance(whale.address)
            sig_dir = determine_signal_direction(tracked_bets, tracked_acc)
            dir_label = f" [{sig_dir}]" if sig_dir != "FOLLOW" else ""

            # C3 FIX: Skip alert if market is already resolved (redundant safety check)
            if pos.current_price >= 0.95 or pos.current_price <= 0.05:
                continue  # Market resolved — do not send Telegram alert

            # H6 FIX: Skip alert if market end_date has passed (stale market)
            if pos.market_end_date:
                try:
                    # Parse end_date (may be ISO format or date string)
                    end_str = pos.market_end_date.replace("Z", "+00:00")
                    if "T" in end_str:
                        market_end = datetime.fromisoformat(end_str.replace("+00:00", ""))
                    else:
                        market_end = datetime.strptime(end_str[:10], "%Y-%m-%d")
                    
                    # 6-hour buffer (market may still be settling)
                    if datetime.now() > market_end + timedelta(hours=6):
                        print(f"  [SKIP] Stale market (ended {pos.market_end_date}): {pos.market_title[:40]}")
                        continue
                except (ValueError, TypeError) as e:
                    # Don't block alert on parse failure, just log
                    print(f"  [WARN] Could not parse end_date '{pos.market_end_date}': {e}")

            # H10 FIX: Quick market validity check (optional, uses cached API data)
            # This catches markets that closed between whale detection and alert
            try:
                book = api.get_orderbook(pos.token_id)
                if book:
                    bids = book.get("bids", [])
                    asks = book.get("asks", [])
                    # No orderbook = market likely closed/resolved
                    if not bids and not asks:
                        print(f"  [SKIP] No orderbook (market closed?): {pos.market_title[:40]}")
                        continue
            except Exception:
                pass  # Don't block alert on API failure

            # 🚨 IMMEDIATE TELEGRAM ALERT on new whale position
            # Priority based on whale elite score + position size
            if whale.elite_score >= 40 or pos.size_usd >= 10000:
                move_priority = "🔥 HOT"
            elif whale.elite_score >= 30 or pos.size_usd >= 5000:
                move_priority = "⚡ ACTIVE"
            else:
                move_priority = "👀 NEW"
            
            alert_msg = f"""🐋 <b>{move_priority} WHALE MOVE{dir_label}</b>

<b>{whale.display_name}</b> (Score: {whale.elite_score:.0f})
├ PnL: ${whale.pnl:,.0f}
└ Track: {tracked_bets} bets @ {tracked_acc:.0%}

<b>📈 {pos.market_title[:45]}</b>
├ {pos.side} @ ${pos.entry_price:.4f}
└ Size: ${pos.size_usd:,.2f}

⏳ Validating..."""
            if send_telegram_alert(alert_msg):
                print(f"  [ALERT] Alert sent for {whale.display_name}: {pos.market_title[:40]}")
            
            # Check if this whale is flagged as potential insider
            try:
                from insider_detector import InsiderDetector
                detector = InsiderDetector()
                detector.alert_new_insider_move(
                    whale.address, 
                    pos.market_title, 
                    pos.side, 
                    pos.size_usd
                )
                detector.close()
            except Exception:
                pass  # Don't block on insider detection failure

            # Insert into tracking table (including end_date for freshness filtering)
            conn.execute("""
                INSERT OR IGNORE INTO whale_positions
                (address, condition_id, token_id, market_title, side,
                 size, size_usd, entry_price, current_price,
                 unrealized_pnl, detected_at, signal_generated, end_date)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?)
            """, (
                whale.address, pos.condition_id, pos.token_id,
                pos.market_title, pos.side, pos.size, pos.size_usd,
                pos.entry_price, pos.current_price, pos.unrealized_pnl,
                datetime.now().isoformat(),
                pos.market_end_date or None,
            ))

    conn.commit()
    conn.close()

    if skipped_resolved > 0:
        print(f"  Skipped {skipped_resolved} already-resolved positions (price at 0/1)")
    if skipped_underwater > 0:
        print(f"  Skipped {skipped_underwater} underwater positions (disposition effect filter)")
    print(f"  Found {len(new_positions)} new positions")
    return new_positions


def refresh_pending_prices(api: PolymarketAPI, limit: int = 100):
    """Update current_price for oldest pending positions.

    This keeps prices fresh so sweep_resolved_prices() can catch
    markets that resolved since we last checked.
    """
    conn = sqlite3.connect(str(WHALE_DB), timeout=30)
    positions = conn.execute("""
        SELECT id, token_id FROM whale_positions
        WHERE outcome = 'pending'
          AND token_id IS NOT NULL AND token_id != ''
        ORDER BY detected_at ASC
        LIMIT ?
    """, (limit,)).fetchall()

    updated = 0
    for pos_id, token_id in positions:
        try:
            price_data = api.get_price(token_id)
            if price_data:
                new_price = float(price_data.get('price', 0) or 0)
                if new_price > 0:
                    conn.execute(
                        "UPDATE whale_positions SET current_price = ? WHERE id = ?",
                        (new_price, pos_id)
                    )
                    updated += 1
        except Exception:
            pass

    conn.commit()
    conn.close()
    if updated > 0:
        print(f"  [REFRESH] Updated prices for {updated}/{len(positions)} pending positions")
    return updated


# ── Commands ───────────────────────────────────────────────────

def cmd_health(client: MiroFishClient):
    """Health check — show system status without running simulations."""
    _init_db()

    print("=" * 60)
    print("[WHALE] WHALE HUNTER -- Health Check")
    print("=" * 60)

    # MiroFish
    print("\n[SCAN] MiroFish Backend...")
    if client.health_check():
        print("  [OK] MiroFish: ONLINE")
    else:
        print("  [FAIL] MiroFish: OFFLINE")

    # Polymarket API
    print("\n[SCAN] Polymarket API...")
    api = PolymarketAPI()
    if api.health_check():
        print("  [OK] Polymarket: ONLINE")

        # Quick leaderboard sample
        leaders = api.get_leaderboard(limit=5)
        if leaders:
            print(f"\n  Top 5 by PnL:")
            for i, e in enumerate(leaders):
                name = (e.get("userName") or e.get("username")
                        or e.get("proxyWallet", "?")[:10])
                pnl = float(e.get("pnl", 0) or 0)
                print(f"    #{i+1} {name:20s} PnL: ${pnl:>12,.2f}")
    else:
        print("  [FAIL] Polymarket: OFFLINE")
    api.close()

    # Database stats
    print(f"\n[STATS] Database ({WHALE_DB.name}):")
    conn = sqlite3.connect(str(WHALE_DB), timeout=10)
    for table, label in [
        ("tracked_whales", "Tracked whales"),
        ("whale_positions", "Tracked positions"),
        ("trade_signals", "Trade signals"),
    ]:
        try:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {label}: {count}")
        except sqlite3.OperationalError:
            print(f"  {label}: (table not created)")
    conn.close()

    # Clusters
    clusters = load_clusters(str(WHALE_DB))
    if clusters:
        print(f"\n  Detected clusters: {len(clusters)}")
        for c in clusters[:3]:
            print(f"    {c['cluster_id']}: {c['size']} wallets, "
                  f"combined PnL ${c['combined_pnl']:,.2f}")

    # Recent signals
    conn = sqlite3.connect(str(WHALE_DB), timeout=10)
    try:
        cursor = conn.execute(
            "SELECT * FROM trade_signals ORDER BY created_at DESC LIMIT 3"
        )
        signals = cursor.fetchall()
        if signals:
            print(f"\n  Recent signals:")
            for s in signals:
                sig_id = s[0] or "?"
                market = (s[4] or "Unknown")[:40]
                direction = s[6] or "?"
                edge = s[11] if s[11] is not None else 0
                size = s[7] if s[7] is not None else 0
                print(f"    {sig_id}: {market}... "
                      f"{direction} edge={edge:+.1%} ${size:,.0f}")
    except sqlite3.OperationalError:
        pass
    conn.close()

    # Predictions log
    if PREDICTIONS_LOG.exists():
        lines = sum(1 for _ in open(PREDICTIONS_LOG))
        print(f"\n  Predictions logged: {lines}")
    else:
        print(f"\n  Predictions logged: 0")


def cmd_test(client: MiroFishClient):
    """Quick test — score one whale, simulate one position."""
    _init_db()

    print("=" * 60)
    print("[WHALE] WHALE HUNTER -- Test Mode (5 rounds, skip graph)")
    print("=" * 60)

    api = PolymarketAPI()

    # Get top trader
    leaders = api.get_leaderboard(limit=3)
    if not leaders:
        print("No leaderboard data")
        api.close()
        return

    # Score first trader with sufficient positions
    profile = None
    for entry in leaders:
        addr = entry.get("proxyWallet") or entry.get("address", "")
        name = (entry.get("userName") or entry.get("username") or addr[:10])
        pnl = float(entry.get("pnl", 0) or 0)
        vol = float(entry.get("vol", 0) or 0)

        positions = api.get_positions(addr)
        closed = api.get_closed_positions(addr)
        activity = api.get_activity(addr)

        profile = score_trader(addr, name, pnl, vol, positions, closed, activity)
        if profile and positions:
            break

    if not profile:
        print("No scoreable traders found")
        api.close()
        return

    # Get their top position
    raw_positions = api.get_positions(profile.address)
    whale_positions = extract_positions(profile.address, raw_positions, side_cache={})
    api.close()

    if not whale_positions:
        print(f"No open positions for {profile.display_name}")
        return

    # Sort by size, pick largest
    whale_positions.sort(key=lambda p: p.size_usd, reverse=True)
    target = whale_positions[0]

    print(f"\n[TARGET] Target:")
    print(f"  Whale: {profile.display_name} (score {profile.elite_score:.0f})")
    print(f"  Market: {target.market_title[:60]}")
    print(f"  Side: {target.side} @ {target.entry_price:.4f}")
    print(f"  Size: ${target.size_usd:,.2f}")

    # Simulate
    prediction = simulate_whale_trade(
        client, profile, target,
        max_rounds=5, skip_graph=True
    )

    if prediction:
        log_prediction(prediction)

        # Parse report
        report_id = prediction.get("report_id")
        if report_id:
            consensus = extract_consensus_from_report(report_id)
            if consensus and consensus.get("consensus_probability"):
                model_prob = consensus["consensus_probability"] / 100
                market_price = target.entry_price
                edge = model_prob - market_price
                print(f"\n  Swarm consensus: {model_prob:.0%}")
                print(f"  Whale entry: {market_price:.0%}")
                print(f"  Edge: {edge:+.1%}")

        print(f"\n  [OK] Test complete: {json.dumps(prediction, indent=2, default=str)[:300]}")
    else:
        print(f"\n  [FAIL] Test failed")


def cmd_scan(client: MiroFishClient, top_n: int = 3):
    """Full scan — score whales, detect positions, simulate, generate signals."""
    _init_db()

    print("=" * 60)
    print(f"[WHALE] WHALE HUNTER -- Full Scan (top {top_n} positions)")
    print("=" * 60)

    api = PolymarketAPI()
    tracker = OutcomeTracker()

    # 1. Score whales from leaderboard
    whales = fetch_and_score_whales(api, top_n=TOP_LEADERBOARD)
    ranked = rank_traders(whales, min_trades=5, min_elite_score=MIN_ELITE_SCORE,
                          max_insider_flags=MAX_INSIDER_FLAGS)

    # 1b. Also load elite whales from DB (not just leaderboard)
    db_elites = _load_elite_from_db(min_score=60.0, limit=30)
    existing_addrs = {w.address for w in ranked}
    added = 0
    for dw in db_elites:
        if dw.address not in existing_addrs:
            ranked.append(dw)
            existing_addrs.add(dw.address)
            added += 1
    if added:
        print(f"\n  Added {added} elite whales from DB (not in leaderboard)")

    print(f"\n[TOP] Elite Traders ({len(ranked)} qualified):")
    for i, w in enumerate(ranked[:10]):
        insider = " [WARN]" if w.insider_flags else ""
        print(f"  #{i+1} {w.display_name:20s} Score: {w.elite_score:5.1f} "
              f"Brier: {w.brier_score:.3f} WR: {w.bayesian_win_rate:.0%} "
              f"PnL: ${w.pnl:>10,.0f}{insider}")

    # 2. Detect new positions
    new_positions = detect_new_positions(api, ranked)

    if not new_positions:
        print("\n  No new positions detected. Scan complete.")
        api.close()
        return

    # 3. Sort by priority (elite_score × position_size)
    new_positions.sort(
        key=lambda wp: wp[0].elite_score * wp[1].size_usd,
        reverse=True
    )

    # 4. Simulate top_n positions
    signals_generated = 0
    sims_run = 0

    for whale, position in new_positions[:top_n]:
        print(f"\n{'-' * 50}")
        print(f"Whale: {whale.display_name} (score {whale.elite_score:.0f})")
        print(f"Market: {position.market_title[:60]}")
        print(f"Position: {position.side} @ {position.entry_price:.4f} "
              f"(${position.size_usd:,.2f})")

        # Orderbook check (optional — skip if no token_id)
        slippage_info = {}
        if position.token_id:
            slippage_info = api.calculate_slippage(
                position.token_id, position.side, 1000
            )
            if not slippage_info.get("feasible", True):
                print(f"  [SKIP] Skipping: {slippage_info.get('reason', 'infeasible')}")
                continue

        # Run simulation
        prediction = simulate_whale_trade(
            client, whale, position,
            max_rounds=24, skip_graph=False
        )
        sims_run += 1

        if not prediction:
            continue

        log_prediction(prediction)

        # Parse report
        report_id = prediction.get("report_id")
        model_prob = None

        if report_id:
            consensus = extract_consensus_from_report(report_id)
            if consensus and consensus.get("consensus_probability"):
                model_prob = consensus["consensus_probability"] / 100
                print(f"  Swarm consensus: {model_prob:.0%}")

        if model_prob is None:
            # Fallback: use whale's Brier skill as a prior
            # If whale has positive skill, lean toward their trade
            if whale.brier_skill > 0:
                model_prob = position.entry_price + 0.05  # Small premium
            else:
                model_prob = position.entry_price  # No premium
            model_prob = max(0.05, min(0.95, model_prob))
            print(f"  Fallback prob (no report): {model_prob:.0%}")

        # Generate signal
        market_price = position.entry_price
        signal = generate_signal(
            whale, position, model_prob, market_price,
            prediction.get("simulation_id", ""),
            prediction.get("report_id", ""),
            slippage=slippage_info.get("slippage_pct", 0.02),
        )

        if signal:
            signals_generated += 1

            # Track in outcome tracker
            tracker.record_prediction(
                prediction_id=signal["signal_id"],
                market_id=position.condition_id,
                connector="whale_hunter",
                predicted_probability=model_prob,
                market_price=market_price,
                metadata=json.dumps({
                    "whale": whale.display_name,
                    "elite_score": whale.elite_score,
                    "direction": position.side,
                    "position_size": signal["position_size"],
                }),
            )

    api.close()

    # Summary
    print(f"\n{'=' * 60}")
    print(f"SCAN COMPLETE")
    print(f"  Whales scored: {len(whales)}")
    print(f"  Elite qualified: {len(ranked)}")
    print(f"  New positions: {len(new_positions)}")
    print(f"  Simulations run: {sims_run}")
    print(f"  Signals generated: {signals_generated}")
    print(f"{'=' * 60}")

    # Check outcomes and sync to dashboard
    check_outcomes()
    sync_dashboard()
    
    # Show performance summary
    show_performance_summary()


def _load_elite_from_db(min_score: float = 60.0, limit: int = 20) -> List[WhaleProfile]:
    """Load top elite whales from our tracked_whales DB."""
    conn = sqlite3.connect(str(WHALE_DB))
    cur = conn.cursor()
    cur.execute("""
        SELECT address, display_name, elite_score, pnl, volume,
               brier_score, brier_skill, win_rate_raw, bayesian_win_rate,
               difficulty_adj_acc, realized_roi, max_drawdown, calmar_ratio,
               num_trades, avg_position_size, insider_flags, insider_score
        FROM tracked_whales 
        WHERE elite_score >= ?
        ORDER BY elite_score DESC 
        LIMIT ?
    """, (min_score, limit))
    
    profiles = []
    for row in cur.fetchall():
        profiles.append(WhaleProfile(
            address=row[0],
            display_name=row[1] or row[0][:10],
            pnl=row[3] or 0,
            volume=row[4] or 0,
            num_trades=row[13] or 0,
            win_rate_raw=row[7] or 0,
            brier_score=row[5] or 0.25,
            brier_skill=row[6] or 0,
            difficulty_adjusted_acc=row[9] or 0.5,
            bayesian_win_rate=row[8] or 0.5,
            realized_roi=row[10] or 0,
            max_drawdown=row[11] or 0,
            calmar_ratio=row[12] or 0,
            elite_score=row[2] or 0,
            avg_position_size=row[14] or 0,
            insider_flags=row[15] or "",
            insider_score=row[16] or 0,
        ))
    conn.close()
    return profiles


def cmd_scan_fast(top_n: int = 10):
    """Fast scan — detect and alert on whale moves, NO simulation."""
    _init_db()

    print("=" * 60)
    print(f"[WHALE] WHALE HUNTER -- FAST SCAN (no sim)")
    print("=" * 60)

    api = PolymarketAPI(rate_limit=0.5)  # Faster rate limit

    # 1. Score whales from leaderboard (discover new whales)
    whales = fetch_and_score_whales(api, top_n=TOP_LEADERBOARD)
    print(f"\n[DEBUG] Scoring complete. Ranking {len(whales)} whales...", flush=True)
    ranked = rank_traders(whales, min_trades=5, min_elite_score=MIN_ELITE_SCORE,
                          max_insider_flags=MAX_INSIDER_FLAGS)
    print(f"[DEBUG] Ranking complete. {len(ranked)} elite whales.", flush=True)

    # 1b. ALSO include our top elite whales from DB (may not be on leaderboard!)
    print("[DEBUG] Loading elite whales from DB...", flush=True)
    db_elites = _load_elite_from_db(min_score=60.0, limit=30)
    print(f"[DEBUG] Loaded {len(db_elites)} from DB.", flush=True)
    # Merge: add DB elites that aren't already in ranked
    ranked_addrs = {w.address for w in ranked}
    added_from_db = 0
    for elite in db_elites:
        if elite.address not in ranked_addrs:
            ranked.append(elite)
            added_from_db += 1
    if added_from_db > 0:
        print(f"  Added {added_from_db} elite whales from DB (not on leaderboard)")

    print(f"\n[WHALE] Elite Traders ({len(ranked)} total):")
    for i, w in enumerate(ranked[:10]):
        insider = " [!]" if w.insider_flags else ""
        print(f"  #{i+1} {w.display_name:20s} Score: {w.elite_score:5.1f} "
              f"PnL: ${w.pnl:>10,.0f}{insider}")

    # 2. Detect new positions (alerts are sent automatically!)
    print(f"\n[DEBUG] Starting position detection for {len(ranked)} whales...", flush=True)
    new_positions = detect_new_positions(api, ranked)
    print(f"[DEBUG] Position detection complete. Found {len(new_positions)} new.", flush=True)

    api.close()

    # Summary
    print(f"\n{'=' * 60}")
    print(f"FAST SCAN COMPLETE")
    print(f"  Whales scored: {len(whales)}")
    print(f"  Elite qualified: {len(ranked)}")
    print(f"  New positions detected: {len(new_positions)}")
    if new_positions:
        print(f"  [ALERT] Telegram alerts sent for each new position!")
    print(f"{'=' * 60}")

    # Check outcomes and sync to dashboard
    check_outcomes()
    sync_dashboard()
    
    # Show performance summary
    show_performance_summary()
    
    # Check watchlist
    try:
        from market_watchlist import send_watchlist_alerts
        print("\n[WATCH] Checking watchlist...")
        send_watchlist_alerts()
    except Exception as e:
        print(f"  [WARN] Watchlist check failed: {e}")

    return {
        "whales_scored": len(whales),
        "elite_qualified": len(ranked),
        "new_positions": len(new_positions),
        "positions": [(w.display_name, p.market_title, p.side, p.size_usd) 
                      for w, p in new_positions]
    }


def show_performance_summary():
    """Display historical win rate summary."""
    conn = sqlite3.connect(str(WHALE_DB), timeout=10)
    
    print(f"\n{'-' * 40}")
    print("[STATS] PERFORMANCE SUMMARY")
    print(f"{'-' * 40}")
    
    # Overall signal performance
    try:
        cur = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) as won,
                SUM(CASE WHEN outcome = 'lost' THEN 1 ELSE 0 END) as lost,
                SUM(CASE WHEN outcome = 'pending' THEN 1 ELSE 0 END) as pending
            FROM whale_positions
            WHERE signal_generated = 1
        """)
        row = cur.fetchone()
        if row and row[0] > 0:
            total, won, lost, pending = row
            resolved = won + lost
            win_rate = (won / resolved * 100) if resolved > 0 else 0
            print(f"Signals: {total} total")
            print(f"  + Won: {won}")
            print(f"  - Lost: {lost}")
            print(f"  ~ Pending: {pending}")
            if resolved > 0:
                print(f"  Win Rate: {win_rate:.1f}% ({won}/{resolved})")
    except Exception as e:
        print(f"  (No signal data: {e})")
    
    # Top performing whales (by tracked accuracy)
    try:
        cur = conn.execute("""
            SELECT display_name, tracked_bets, tracked_accuracy, elite_score
            FROM tracked_whales
            WHERE tracked_bets >= 5
            ORDER BY tracked_accuracy DESC
            LIMIT 5
        """)
        rows = cur.fetchall()
        if rows:
            print(f"\n[TOP] Top Whales (by tracked accuracy):")
            for i, (name, bets, acc, score) in enumerate(rows, 1):
                acc_pct = (acc or 0) * 100
                print(f"  #{i} {name[:15]:15s} {acc_pct:5.1f}% ({bets} bets) Score: {score:.0f}")
    except Exception:
        pass
    
    # Recent resolved positions
    try:
        cur = conn.execute("""
            SELECT market_title, side, outcome, resolved_at
            FROM whale_positions
            WHERE outcome IN ('won', 'lost')
            ORDER BY resolved_at DESC
            LIMIT 5
        """)
        rows = cur.fetchall()
        if rows:
            print(f"\n[RECENT] Recent Results:")
            for title, side, outcome, resolved in rows:
                emoji = "[OK]" if outcome == "won" else "[FAIL]"
                title_short = title[:35] if title else "Unknown"
                print(f"  {emoji} {side} {title_short}")
    except Exception:
        pass
    
    conn.close()
    print(f"{'-' * 40}\n")


# ── CLI Entry Point ────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Whale Hunter - MiroFish Connector"
    )
    parser.add_argument("--test", action="store_true",
                        help="Quick test (5 rounds, skip graph)")
    parser.add_argument("--scan", action="store_true",
                        help="Full scan + simulate whale positions")
    parser.add_argument("--fast", action="store_true",
                        help="Fast scan - detect & alert, NO simulation")
    parser.add_argument("--digest", action="store_true",
                        help="Generate daily digest summary")
    parser.add_argument("--time", action="store_true",
                        help="Show time-of-day analysis")
    parser.add_argument("--cluster", action="store_true",
                        help="Run wallet cluster analysis")
    parser.add_argument("--watchlist", action="store_true",
                        help="Check watchlist for whale activity")
    parser.add_argument("--perf", action="store_true",
                        help="Show performance report")
    parser.add_argument("--url", default="http://localhost:5001",
                        help="MiroFish backend URL")
    parser.add_argument("--api-key", default=None,
                        help="MiroFish API key")
    parser.add_argument("--top", type=int, default=3,
                        help="Number of positions to simulate")
    args = parser.parse_args()

    # Handle new commands without MiroFish client
    if args.digest:
        from daily_digest import generate_digest
        generate_digest(send_telegram=True)
    elif args.time:
        from time_analysis import print_time_report
        print_time_report()
    elif args.cluster:
        from cluster_analyzer import run_cluster_analysis
        run_cluster_analysis(threshold=0.20, min_cluster_size=2)
    elif args.watchlist:
        from market_watchlist import send_watchlist_alerts, print_watchlist
        print_watchlist()
        print("\nChecking for activity...")
        send_watchlist_alerts()
    elif args.perf:
        from performance_tracker import print_performance_report
        print_performance_report(days=30)
    else:
        client = MiroFishClient(
            base_url=args.url,
            api_key=args.api_key,
            poll_timeout=1800,
        )

        if args.test:
            cmd_test(client)
        elif args.fast:
            cmd_scan_fast(top_n=args.top)
        elif args.scan:
            cmd_scan(client, top_n=args.top)
        else:
            cmd_health(client)

