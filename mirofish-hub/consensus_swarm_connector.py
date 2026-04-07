#!/usr/bin/env python3
"""
🐋🐟 CONSENSUS SWARM CONNECTOR 🐟🐋

THE MONEY MACHINE: Whale Consensus -> MiroFish Validation -> Trading Signals

Pipeline:
1. Pull GREEN consensus picks from whale API
2. Run MiroFish swarm simulation for each
3. Validate whale signal against crowd sentiment
4. Generate trading signals when edge confirmed
5. Send Telegram alerts for actionable trades

Usage:
    python consensus_swarm_connector.py --scan     # Full scan with sims
    python consensus_swarm_connector.py --fast     # Quick check, no sims
    python consensus_swarm_connector.py --top 5    # Top 5 picks only
"""

import os
import sys
import json
import time
import uuid
import sqlite3
import argparse
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent))

from mirofish_client import MiroFishClient
from ensemble_voter import EnsembleVoter
from narrative_detector import narrative_squeeze_score
from whale_scorer import categorize_market
from domain_sim_manager import DomainSimManager
from auto_executor import AutoExecutor
from insider_detector import InsiderDetector

# Map market categories to domain sim domains
CATEGORY_TO_DOMAIN = {
    "sports": "sports",
    "nba": "sports",
    "nfl": "sports",
    "mlb": "sports",
    "nhl": "sports",
    "soccer": "sports",
    "tennis": "sports",
    "mma": "sports",
    "politics": "politics",
    "geopolitics": "politics",
    "crypto": "markets",
    "finance": "markets",
    "economy": "markets",
    "commodities": "markets",
}

# ══════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════

WHALE_API_URL = "http://localhost:8081"
MIROFISH_URL = "http://localhost:5001"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "939543801")
DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"

# Thresholds
MIN_CONFIDENCE = 45.0      # Minimum Bayesian confidence to track picks (lowered: picks typically 49-61%)
MIN_WHALES = 3             # Minimum whale count
MIN_AGREEMENT = 50.0       # Minimum agreement % (lowered to capture more picks for tracking)
MIN_EDGE = 8.0             # Minimum edge to generate signal (%)
KELLY_MAX = 0.15           # Max Kelly fraction for position sizing

# MiroFish sim settings
SIM_MAX_ROUNDS = 3         # Keep sims fast
SIM_TIMEOUT = 1800         # 30 min max per sim (prep ~20 min + sim ~6-10 min on RTX 3060)

# Ollama settings for warm-up
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:4b"  # Updated 2026-04-04: 97.5 tok/sec (fastest!)


# ══════════════════════════════════════════════════════════════
# LLM WARM-UP (prevents cold start timeout)
# ══════════════════════════════════════════════════════════════

def warm_up_llm() -> bool:
    """
    Warm up the Ollama model before running simulations.
    First request loads ~9GB into VRAM (~7s), then subsequent calls are fast.
    """
    try:
        print("[HOT] Warming up LLM (loading model to GPU)...")
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": "Say OK",
                "stream": False
            },
            timeout=60
        )
        if r.status_code == 200:
            print("   [OK] LLM warm - model loaded to GPU")
            return True
        else:
            print(f"   [WARN] LLM warm-up failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"   [WARN] LLM warm-up error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# TELEGRAM ALERTS
# ══════════════════════════════════════════════════════════════

def send_telegram(message: str, parse_mode: str = "HTML") -> bool:
    """Send Telegram alert."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"  [WARN] Telegram error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# WHALE API CLIENT
# ══════════════════════════════════════════════════════════════

def get_consensus_picks(min_confidence: float = MIN_CONFIDENCE,
                        min_whales: int = MIN_WHALES) -> List[Dict]:
    """Get GREEN consensus picks from whale API."""
    try:
        r = requests.get(f"{WHALE_API_URL}/api/consensus", timeout=120)
        r.raise_for_status()
        data = r.json()
        
        picks = data.get("picks", [])
        # Filter by thresholds
        filtered = [
            p for p in picks
            if p.get("confidence_pct", 0) >= min_confidence
            and p.get("whale_count", 0) >= min_whales
            and p.get("agreement_pct", 0) >= MIN_AGREEMENT
        ]
        
        # Sort by confidence descending
        filtered.sort(key=lambda x: x.get("confidence_pct", 0), reverse=True)
        return filtered
        
    except Exception as e:
        print(f"[FAIL] Failed to get consensus: {e}")
        return []


def get_portfolio_heat() -> Dict[str, Any]:
    """Get portfolio heat/concentration data."""
    try:
        r = requests.get(f"{WHALE_API_URL}/api/portfolio/heat", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


# ══════════════════════════════════════════════════════════════
# MIROFISH SWARM INTEGRATION
# ══════════════════════════════════════════════════════════════

def run_mirofish_sim(pick: Dict, client: MiroFishClient) -> Dict[str, Any]:
    """
    Run MiroFish swarm simulation for a consensus pick.
    
    Returns:
        {
            "status": "success" | "failed" | "skipped",
            "swarm_prob": float (0-100),
            "swarm_sentiment": "bullish" | "bearish" | "neutral",
            "agent_count": int,
            "convergence": float (0-1),
            "validates_whales": bool,
            "edge": float,
            "error": str (if failed)
        }
    """
    market_title = pick.get("market_title", "Unknown")
    consensus_side = pick.get("consensus_side", "YES")
    whale_count = pick.get("whale_count", 0)
    agreement_pct = pick.get("agreement_pct", 0)
    avg_entry = pick.get("avg_entry_price", 0.5)
    
    print(f"\n[FISH] Running MiroFish sim for: {market_title[:50]}...")
    print(f"   Whales: {whale_count} | Agreement: {agreement_pct}% | Side: {consensus_side}")
    
    try:
        # Check MiroFish health
        if not client.health_check():
            return {"status": "skipped", "error": "MiroFish not running"}
        
        # Build simulation requirement
        sim_requirement = f"""
Prediction Market Analysis: {market_title}

Current market data:
- {whale_count} whale traders have taken positions
- {agreement_pct}% agree on {consensus_side} outcome
- Average entry price: ${avg_entry:.2f}

Simulate crowd sentiment with diverse agents:
1. Would the general public bet YES or NO on this?
2. What probability would informed traders assign?
3. Is there edge in following the whale consensus?

CRITICAL: Include 2-3 Devil's Advocate agents who MUST argue the OPPOSITE
side ({('NO' if consensus_side == 'YES' else 'YES')}). They should present
the strongest possible case AGAINST the whale consensus. This prevents
groupthink and tests conviction strength.

Also include: a Quantitative Analyst (odds/probability focus), a Contrarian
Trader (challenges conventional wisdom), and a Risk Manager (worst-case
scenarios).

Focus on: sentiment direction, probability estimate, confidence level.
"""
        
        # Create project with no_zep_ prefix to skip graph memory
        project_name = f"no_zep_consensus_{pick.get('condition_id', 'unknown')[:8]}"
        
        # Build seed text with whale data
        seed_text = f"""
PREDICTION MARKET DATA
======================
Market: {market_title}

Whale Activity:
- {whale_count} institutional traders have positioned
- {agreement_pct}% consensus on {consensus_side}
- Average entry price: ${avg_entry:.2f}

Key Whales:
"""
        for w in pick.get("whales", [])[:5]:
            seed_text += f"- {w.get('name', 'anon')} (Elite: {w.get('elite', 0):.0f}) -> {w.get('side', 'YES')}\n"
        
        seed_text += f"""

Question: Will this market resolve {consensus_side}?
Analyze sentiment and provide probability estimate.
"""

        # ── Auto-Research: enrich seed with real-world data ──
        try:
            from auto_researcher import AutoResearcher
            researcher = AutoResearcher()
            category = pick.get("category", "other")
            research_data = researcher.research(market_title, category)
            if research_data:
                seed_text += f"\n\nRESEARCH DATA (auto-gathered):\n{research_data}"
                print(f"   [RESEARCH] Research added ({len(research_data)} chars)")
        except ImportError:
            pass  # auto_researcher.py not yet available
        except Exception as e:
            print(f"   [WARN] Research failed (non-critical): {e}")
        
        start_time = time.time()

        # Use run_dual_platform() — the proven all-in-one pipeline that
        # handles project creation, graph build, sim create/prepare/start,
        # polling, and report generation in the correct order.
        print("   [LAUNCH] Running full MiroFish pipeline...")
        pipeline_result = client.run_dual_platform(
            simulation_requirement=sim_requirement,
            seed_text=seed_text,
            project_name=project_name,
            max_rounds=SIM_MAX_ROUNDS,
            skip_graph=True,  # Skip Zep graph (not configured)
        )

        elapsed = time.time() - start_time
        print(f"   [OK] Pipeline completed in {elapsed:.1f}s")

        # Extract report from pipeline result
        report = pipeline_result
        return parse_mirofish_report(report, pick)
        
    except Exception as e:
        print(f"   [FAIL] MiroFish error: {e}")
        return {"status": "failed", "error": str(e)}


def _extract_prob_from_markdown(markdown: str, consensus_side: str) -> float:
    """Extract probability from Chinese/English markdown report text.

    Looks for patterns like:
    - "66.7%的鲸鱼交易者认为YES"
    - "胜率为70%"
    - "probability: 65%"
    - "概率为 75%"
    - "可能性较高" (mapped to ~80%)
    """
    import re

    # Pattern 1: Explicit percentages near keywords
    pct_patterns = [
        r'(\d{1,3}(?:\.\d+)?)\s*%\s*(?:的|chance|probability|概率|胜率|可能)',
        r'(?:probability|概率|胜率|可能性|置信度)\D{0,40}(\d{1,3}(?:\.\d+)?)\s*%',
        r'(\d{1,3}(?:\.\d+)?)\s*%\s*(?:agree|consensus|共识|认为)',
    ]
    probs = []
    for pat in pct_patterns:
        for match in re.finditer(pat, markdown, re.IGNORECASE):
            val = float(match.group(1))
            if 10 <= val <= 99:
                probs.append(val)

    if probs:
        return sum(probs) / len(probs)

    # Pattern 2: Chinese qualitative phrases
    chinese_map = {
        "可能性较高": 80.0, "可能性很高": 85.0, "可能性较低": 25.0,
        "可能性很低": 15.0, "大概率": 80.0, "小概率": 20.0,
        "看好": 70.0, "不看好": 30.0, "谨慎": 40.0,
        "风险较大": 35.0, "有利": 65.0, "不利": 35.0,
    }
    found = []
    for phrase, prob in chinese_map.items():
        if phrase in markdown:
            found.append(prob)

    if found:
        return sum(found) / len(found)

    # Pattern 3: Count bullish vs bearish agent quotes
    bullish_words = ["bullish", "看好", "有利", "胜", "赢", "agree", "support",
                     "positive", "favor", "likely", "confident"]
    bearish_words = ["bearish", "不看好", "不利", "输", "败", "disagree", "risk",
                     "negative", "against", "unlikely", "cautious", "谨慎"]
    bull_count = sum(1 for w in bullish_words if w in markdown.lower())
    bear_count = sum(1 for w in bearish_words if w in markdown.lower())

    if bull_count + bear_count > 0:
        return (bull_count / (bull_count + bear_count)) * 100

    return None  # No signal extracted — caller must handle None


def parse_mirofish_report(report: Dict, pick: Dict) -> Dict[str, Any]:
    """Parse MiroFish markdown report to extract sentiment and probability.

    The report from run_dual_platform() contains:
    - report["report"]["markdown_content"] — Chinese markdown with agent quotes
    - report["report"]["status"] — "completed" or "failed"
    - report["report"]["report_id"] — for reference

    We extract probability using:
    1. report_parser.extract_consensus_from_report() (handles Chinese text)
    2. Fallback: regex probability extraction from markdown
    3. Fallback: keyword sentiment counting
    """
    consensus_side = pick.get("consensus_side", "YES")
    avg_entry = pick.get("avg_entry_price", 0.5)

    try:
        # Get markdown content from the report
        report_data = report.get("report", {})
        markdown = report_data.get("markdown_content", "") or ""
        report_status = report_data.get("status", "unknown")

        if not markdown:
            print("   [WARN] No markdown content in report")
            return {
                "status": "no_report",
                "swarm_prob": None,
                "swarm_sentiment": "neutral",
                "agent_count": 0,
                "convergence": 0.0,
                "validates_whales": False,
                "edge": 0,
            }

        # Use regex extraction as primary parser (proven working)
        swarm_prob = _extract_prob_from_markdown(markdown, consensus_side)

        # Count agent contributions
        agent_count = markdown.count("[twitter]") + markdown.count("[reddit]")

        # If swarm_prob is None or exactly 50.0, treat as "no data"
        if swarm_prob is None or swarm_prob == 50.0:
            print("   [WARN] No real probability extracted from report (got None/50.0)")
            return {
                "status": "no_signal",
                "swarm_prob": None,
                "swarm_sentiment": "neutral",
                "agent_count": agent_count,
                "convergence": 0.0,
                "validates_whales": False,
                "edge": 0,
            }

        # Determine sentiment
        if swarm_prob > 55:
            swarm_sentiment = "bullish"
        elif swarm_prob < 45:
            swarm_sentiment = "bearish"
        else:
            swarm_sentiment = "neutral"

        # Convergence: how far from 50% (higher = stronger signal)
        convergence = abs(swarm_prob - 50) / 50

        # Check if swarm validates whale consensus
        whale_is_yes = consensus_side == "YES"
        swarm_is_yes = swarm_sentiment == "bullish"
        validates = (whale_is_yes == swarm_is_yes) or swarm_sentiment == "neutral"

        # Calculate edge
        if validates:
            if whale_is_yes:
                edge = swarm_prob - (avg_entry * 100)
            else:
                edge = (100 - swarm_prob) - ((1 - avg_entry) * 100)
        else:
            edge = -10  # Negative edge if swarm disagrees

        return {
            "status": "success",
            "swarm_prob": round(swarm_prob, 1),
            "swarm_sentiment": swarm_sentiment,
            "agent_count": agent_count,
            "convergence": round(convergence, 2),
            "validates_whales": validates,
            "edge": round(edge, 1),
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": f"Report parse error: {e}",
            "swarm_prob": None,
            "validates_whales": False,
            "edge": 0,
        }


# ══════════════════════════════════════════════════════════════
# DATABASE UPDATES
# ══════════════════════════════════════════════════════════════

def update_mirofish_result(condition_id: str, result: Dict,
                           max_retries: int = 3) -> bool:
    """Update whale_hunter.db with MiroFish results (with retry for DB locks)."""
    for attempt in range(max_retries):
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH, timeout=60)
            conn.execute("PRAGMA busy_timeout=30000")  # 30s retry on lock
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS mirofish_results (
                    condition_id TEXT PRIMARY KEY,
                    swarm_prob REAL,
                    swarm_sentiment TEXT,
                    agent_count INTEGER,
                    convergence REAL,
                    validates_whales INTEGER,
                    edge REAL,
                    status TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

            now = datetime.now().isoformat()

            cur.execute("""
                INSERT OR REPLACE INTO mirofish_results
                (condition_id, swarm_prob, swarm_sentiment, agent_count, convergence,
                 validates_whales, edge, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                        COALESCE((SELECT created_at FROM mirofish_results WHERE condition_id = ?), ?),
                        ?)
            """, (
                condition_id,
                result.get("swarm_prob", 0),
                result.get("swarm_sentiment", "neutral"),
                result.get("agent_count", 0),
                result.get("convergence", 0),
                1 if result.get("validates_whales") else 0,
                result.get("edge", 0),
                result.get("status", "unknown"),
                condition_id, now, now,
            ))

            conn.commit()
            return True

        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                wait = (attempt + 1) * 2
                print(f"  [WARN] DB locked, retrying in {wait}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            print(f"  [WARN] DB update error after {max_retries} attempts: {e}")
            return False
        except Exception as e:
            print(f"  [WARN] DB update error: {e}")
            return False
        finally:
            if conn:
                conn.close()
    return False


def save_consensus_pick(signal: Dict) -> bool:
    """Save a consensus pick to track prediction vs outcome."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")  # 30s retry on lock
        cur = conn.cursor()

        # Get end_date AND token_id from whale_positions
        cid = signal.get("condition_id", "")
        cur.execute("""
            SELECT end_date, token_id FROM whale_positions
            WHERE condition_id = ? AND token_id IS NOT NULL AND token_id != ''
            LIMIT 1
        """, (cid,))
        row = cur.fetchone()
        end_date = row[0] if row else None
        token_id = row[1] if row else None

        cur.execute("""
            INSERT INTO consensus_picks
            (market_title, condition_id, token_id, side, confidence, whale_count,
             avg_entry_price, end_date, outcome, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            signal.get("market", ""),
            cid,
            token_id,
            signal.get("side", ""),
            signal.get("confidence", 0),
            signal.get("whale_count", 0),
            signal.get("entry_price", 0),
            end_date,
            f"Edge: {signal.get('edge', 0):.1f}% | Type: {signal.get('validation_type', 'unknown')}"
        ))

        conn.commit()
        print(f"   [LOG] Tracked pick in consensus_picks table")
        return True
    except sqlite3.IntegrityError:
        # Already tracked
        return True
    except Exception as e:
        print(f"   [WARN] Failed to track pick: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_cached_mirofish(condition_id: str, max_age_hours: int = 6) -> Optional[Dict]:
    """Get cached MiroFish result if recent enough."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")  # 30s retry on lock
        cur = conn.cursor()

        cur.execute("""
            SELECT swarm_prob, swarm_sentiment, validates_whales, edge, updated_at
            FROM mirofish_results
            WHERE condition_id = ?
        """, (condition_id,))

        row = cur.fetchone()

        if not row:
            return None

        # Check age
        updated_at = datetime.fromisoformat(row[4])
        age = datetime.now() - updated_at
        if age > timedelta(hours=max_age_hours):
            return None

        return {
            "status": "success",
            "swarm_prob": row[0],
            "swarm_sentiment": row[1],
            "validates_whales": bool(row[2]),
            "edge": row[3],
            "cached": True
        }

    except Exception:
        return None
    finally:
        if conn:
            conn.close()


# ══════════════════════════════════════════════════════════════
# SIGNAL GENERATION
# ══════════════════════════════════════════════════════════════

def _write_signal_to_db(signal: Dict, pick: Dict, mirofish: Optional[Dict] = None):
    """Write a generated signal to the trade_signals table (A16 fix)."""
    import hashlib
    conn = None
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")  # 30s retry on lock
        cur = conn.cursor()

        # Ensure table exists
        cur.execute("""
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
                status TEXT,
                created_at TEXT,
                resolved_at TEXT,
                pnl REAL
            )
        """)

        # Build a deterministic signal_id from condition_id + timestamp
        now_iso = signal.get("signal_time", datetime.now().isoformat())
        condition_id = signal.get("condition_id", "unknown")
        raw_id = f"consensus_{condition_id}_{now_iso}"
        signal_id = hashlib.sha256(raw_id.encode()).hexdigest()[:16]

        # Map consensus fields to trade_signals schema
        whale_count = signal.get("whale_count", 0)
        validation_type = signal.get("validation_type", "unknown")

        cur.execute("""
            INSERT OR IGNORE INTO trade_signals (
                signal_id, whale_address, whale_name, whale_elite_score,
                market_title, condition_id, direction, position_size,
                kelly_fraction, model_prob, market_price, edge,
                whale_entry_price, slippage_estimate, simulation_id,
                report_id, status, created_at, resolved_at, pnl
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal_id,
            "consensus",                                    # whale_address
            f"{whale_count}_whales",                        # whale_name (whale count)
            signal.get("agreement", 0),                     # whale_elite_score (repurpose as agreement %)
            signal.get("market"),                            # market_title
            condition_id,                                   # condition_id
            signal.get("side"),                             # direction
            None,                                           # position_size (not yet sized)
            signal.get("kelly"),                            # kelly_fraction
            signal.get("swarm_prob"),                       # model_prob
            signal.get("entry_price"),                      # market_price
            signal.get("edge"),                             # edge
            signal.get("entry_price"),                      # whale_entry_price
            None,                                           # slippage_estimate
            mirofish.get("simulation_id") if mirofish else None,  # simulation_id
            None,                                           # report_id
            "pending",                                      # status
            now_iso,                                        # created_at
            None,                                           # resolved_at
            None,                                           # pnl
        ))

        conn.commit()
        print(f"  [OK] Signal written to trade_signals: {signal_id} ({validation_type})")
    except Exception as e:
        print(f"  [WARN] Failed to write signal to DB: {e}")
    finally:
        if conn:
            conn.close()


def _check_market_insiders(condition_id: str) -> Dict:
    """
    Check if any flagged insiders are trading on this market.
    
    Returns dict with count and flags of insider activity.
    """
    if not condition_id:
        return {"count": 0, "flags": []}
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        
        # Find addresses trading this market that have insider flags
        rows = conn.execute("""
            SELECT DISTINCT wp.address, GROUP_CONCAT(if.flag_type) as flags
            FROM whale_positions wp
            JOIN insider_flags if ON wp.address = if.address
            WHERE wp.condition_id = ?
            GROUP BY wp.address
        """, (condition_id,)).fetchall()
        
        conn.close()
        
        if not rows:
            return {"count": 0, "flags": []}
        
        # Collect unique flags
        all_flags = set()
        for r in rows:
            if r[1]:
                all_flags.update(r[1].split(","))
        
        return {
            "count": len(rows),
            "flags": list(all_flags),
            "addresses": [r[0][:12] + "..." for r in rows[:3]]
        }
    except Exception:
        return {"count": 0, "flags": []}


def generate_signal(pick: Dict, mirofish: Optional[Dict] = None) -> Optional[Dict]:
    """Generate trading signal if edge is sufficient.
    
    Can work with or without MiroFish validation.
    If no MiroFish result, use whale consensus alone.
    """
    
    # If MiroFish result available, check validation
    if mirofish and mirofish.get("status") == "success":
        edge = mirofish.get("edge", 0)
        validates = mirofish.get("validates_whales", False)
        
        if not validates:
            return None
        
        if edge < MIN_EDGE:
            return None
    else:
        # No MiroFish - use whale confidence as edge proxy
        # High agreement + high confidence = estimated edge
        agreement = pick.get("agreement_pct", 0)
        confidence = pick.get("confidence_pct", 0)
        whale_count = pick.get("whale_count", 0)
        
        # Require strong whale consensus without MiroFish
        if agreement < 80 or whale_count < 5:
            return None
        
        # Estimate edge from confidence (Bayesian already accounts for many factors)
        # If confidence is 85%, and entry is 0.50, edge ≈ 35%
        entry = pick.get("avg_entry_price", 0.5)
        consensus_side = pick.get("consensus_side", "YES")
        
        if consensus_side == "YES":
            edge = confidence - (entry * 100)
        else:
            edge = confidence - ((1 - entry) * 100)
        
        if edge < MIN_EDGE:
            return None
        
        # Flag as whale-only signal
        mirofish = {"status": "whale_only", "edge": edge, "swarm_prob": confidence}
    
    # Determine validation type for alert formatting
    validation_type = "whale_only" if mirofish.get("status") == "whale_only" else "swarm"
    edge = mirofish.get("edge", 0)
    
    # Calculate position size using Kelly
    confidence = pick.get("confidence_pct", 50) / 100
    kelly = pick.get("kelly_fraction", 0.05)
    
    # Adjust Kelly by edge strength
    edge_factor = min(edge / 20, 1.0)  # Scale 0-1 for 0-20% edge
    adjusted_kelly = min(kelly * edge_factor, KELLY_MAX)

    # Check for insider activity on this market
    insider_info = _check_market_insiders(pick.get("condition_id", ""))
    
    signal_dict = {
        "signal_id": f"cs_{uuid.uuid4().hex[:12]}",
        "market": pick.get("market_title"),
        "condition_id": pick.get("condition_id"),
        "side": pick.get("consensus_side"),
        "whale_count": pick.get("whale_count"),
        "agreement": pick.get("agreement_pct"),
        "confidence": pick.get("confidence_pct"),
        "swarm_prob": mirofish.get("swarm_prob"),
        "edge": edge,
        "kelly": round(adjusted_kelly, 4),
        "entry_price": pick.get("avg_entry_price"),
        "category": pick.get("category"),
        "validation_type": validation_type,
        "signal_time": datetime.now().isoformat(),
        "insider_count": insider_info.get("count", 0),
        "insider_flags": insider_info.get("flags", []),
    }

    # A16 FIX: Write signal to trade_signals table in DB
    _write_signal_to_db(signal_dict, pick, mirofish)

    return signal_dict


def format_signal_alert(signal: Dict) -> str:
    """Format signal as Telegram alert."""
    
    edge_emoji = "🔥" if signal["edge"] >= 15 else "✅" if signal["edge"] >= 10 else "📊"
    validation_type = signal.get("validation_type", "swarm")
    
    if validation_type == "whale_only":
        header = f"{edge_emoji} <b>WHALE CONSENSUS SIGNAL</b> {edge_emoji}"
        validation_section = f"""
<b>Whale Analysis:</b>
• Bayesian confidence: {signal["confidence"]:.1f}%
• <b>Estimated Edge: +{signal["edge"]:.1f}%</b>
<i>(MiroFish unavailable - whale-only mode)</i>"""
    else:
        header = f"{edge_emoji} <b>VALIDATED SIGNAL</b> {edge_emoji}"
        validation_section = f"""
<b>MiroFish Swarm:</b>
• Crowd probability: {signal["swarm_prob"]:.0f}%
• <b>Edge: +{signal["edge"]:.1f}%</b>"""
    
    # Add insider info if present
    insider_section = ""
    if signal.get("insider_count", 0) > 0:
        insider_section = f"""

<b>Insider Activity:</b> {signal["insider_count"]} flagged traders on this market
• Flags: {', '.join(signal.get('insider_flags', [])[:3])}"""
    
    return f"""
{header}

<b>Market:</b> {signal["market"][:60]}
<b>Side:</b> {signal["side"]} @ ${signal["entry_price"]:.2f}

<b>Whale Consensus:</b>
• {signal["whale_count"]} whales ({signal["agreement"]:.0f}% agree)
{validation_section}

<b>Position Size:</b>
• Kelly fraction: {signal["kelly"]:.1%}
{insider_section}
Category: {signal["category"]}
"""


# ══════════════════════════════════════════════════════════════
# MAIN ORCHESTRATION
# ══════════════════════════════════════════════════════════════

def sweep_expired() -> int:
    """
    Mark positions with past end_dates as expired (no API calls needed).

    This is a fast local-only sweep that clears stale markets before
    consensus generation. Markets whose end_date is >2 hours in the past
    are definitely over.
    """
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")  # 30s retry on lock
        result = conn.execute("""
            UPDATE whale_positions
            SET outcome = 'expired'
            WHERE outcome = 'pending'
              AND end_date IS NOT NULL AND end_date != ''
              AND datetime(end_date) < datetime('now', '-2 hours')
        """)
        count = result.rowcount
        conn.commit()
        conn.close()
        return count
    except Exception as e:
        print(f"   [WARN] Sweep failed: {e}")
        return 0


def refresh_positions(limit: int = 200) -> Dict:
    """
    Run outcome tracker to resolve pending positions before generating consensus.

    Clears stale/expired markets so the consensus pipeline only shows live picks.
    """
    try:
        from whale_outcome_tracker import WhaleOutcomeTracker
        tracker = WhaleOutcomeTracker()
        result = tracker.check_and_resolve_all(limit=limit)
        resolved = result.get("resolved", 0)
        won = result.get("won", 0)
        lost = result.get("lost", 0)
        if resolved > 0:
            print(f"   Resolved {resolved} stale positions ({won}W/{lost}L)")
        else:
            print(f"   No new resolutions (checked {result.get('checked', 0)} positions)")
        return result
    except Exception as e:
        print(f"   [WARN] Refresh failed: {e}")
        return {"checked": 0, "resolved": 0, "won": 0, "lost": 0}


def save_pick_for_tracking(pick: Dict, signal: Optional[Dict] = None) -> bool:
    """
    Save EVERY consensus pick for performance tracking — not just signals.

    This closes the feedback loop: we track what the consensus suggested
    (even if we didn't generate a signal), so we can verify later whether
    the pick would have won.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")  # 30s retry on lock
        cur = conn.cursor()

        # Ensure table exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS consensus_picks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_title TEXT,
                condition_id TEXT,
                token_id TEXT,
                side TEXT,
                confidence INTEGER,
                whale_count INTEGER,
                avg_entry_price REAL,
                created_at TEXT DEFAULT (datetime('now')),
                end_date TEXT,
                outcome TEXT DEFAULT 'pending',
                resolved_at TEXT,
                won INTEGER,
                profit_loss REAL,
                notes TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cp_condition ON consensus_picks(condition_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cp_outcome ON consensus_picks(outcome)")

        condition_id = pick.get("condition_id", "")

        # Get end_date and token_id from whale_positions
        row = cur.execute(
            "SELECT end_date, token_id FROM whale_positions WHERE condition_id = ? LIMIT 1",
            (condition_id,),
        ).fetchone()
        end_date = row[0] if row else None
        token_id = row[1] if row else None

        # Build notes
        signal_generated = signal is not None
        edge = signal.get("edge", 0) if signal else 0
        vtype = signal.get("validation_type", "none") if signal else "no_signal"
        agreement = pick.get("agreement_pct", 0)
        notes = (
            f"Edge: {edge:.1f}% | Type: {vtype} | "
            f"Agreement: {agreement:.0f}% | Signal: {'YES' if signal_generated else 'NO'}"
        )

        new_confidence = int(pick.get("confidence_pct", 0))
        new_whale_count = pick.get("whale_count", 0)
        new_entry = pick.get("avg_entry_price", 0)

        # UPSERT: if this market was already tracked today, UPDATE with latest
        # data (more whales may have joined, confidence may have changed)
        existing = cur.execute(
            "SELECT id FROM consensus_picks "
            "WHERE condition_id = ? AND date(created_at) = date('now')",
            (condition_id,),
        ).fetchone()

        if existing:
            cur.execute("""
                UPDATE consensus_picks
                SET confidence = ?, whale_count = ?, avg_entry_price = ?,
                    notes = ?, token_id = COALESCE(?, token_id),
                    end_date = COALESCE(?, end_date)
                WHERE id = ?
            """, (new_confidence, new_whale_count, new_entry,
                  notes, token_id, end_date, existing[0]))
            print(f"   [LOG] Updated pick: {pick.get('market_title', '')[:40]}")
        else:
            cur.execute("""
                INSERT INTO consensus_picks
                (market_title, condition_id, token_id, side, confidence, whale_count,
                 avg_entry_price, end_date, outcome, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """, (
                pick.get("market_title", ""),
                condition_id,
                token_id,
                pick.get("consensus_side", ""),
                new_confidence,
                new_whale_count,
                new_entry,
                end_date,
                notes,
            ))
            print(f"   [LOG] Tracked pick: {pick.get('market_title', '')[:40]}")

        conn.commit()
        return True
    except Exception as e:
        print(f"   [WARN] Failed to track pick: {e}")
        return False
    finally:
        if conn:
            conn.close()


def resolve_consensus_picks() -> Dict:
    """Check outcomes for saved consensus picks."""
    try:
        from consensus_results_tracker import resolve_pending_picks
        return resolve_pending_picks()
    except Exception as e:
        print(f"   [WARN] Results tracker failed: {e}")
        return {}


def run_consensus_swarm(top_n: int = 10, run_sims: bool = True,
                        send_alerts: bool = True,
                        skip_refresh: bool = False,
                        auto_execute: bool = False,
                        dry_run: bool = True) -> Dict[str, Any]:
    """
    Main pipeline: Refresh -> Consensus -> MiroFish -> Signals -> Execute

    Args:
        top_n: Number of top picks to process
        run_sims: Run full MiroFish sims (vs ensemble-only)
        send_alerts: Send Telegram alerts for signals
        skip_refresh: Skip position refresh step
        auto_execute: Automatically execute valid signals
        dry_run: If auto_execute, simulate trades without placing

    Returns summary of validated signals and executions.
    """

    print("\n" + "="*60)
    print("[WHALE][FISH] CONSENSUS SWARM CONNECTOR [FISH][WHALE]")
    print("="*60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'Full Simulation' if run_sims else 'Fast Check'}")
    print(f"Top picks: {top_n}")
    if auto_execute:
        print(f"Auto-execute: {'DRY RUN' if dry_run else '🔴 LIVE TRADING'}")

    results = {
        "picks_found": 0,
        "sims_run": 0,
        "sims_cached": 0,
        "signals_generated": 0,
        "signals": [],
        "executions": [],
        "errors": []
    }
    
    # Initialize executor if auto-execute enabled
    executor = None
    if auto_execute:
        try:
            executor = AutoExecutor(dry_run=dry_run)
            print(f"[EXEC] Auto-executor initialized")
        except Exception as e:
            print(f"[WARN] Auto-executor init failed: {e}")

    # Step 0a: Sweep expired markets (fast, local-only)
    expired_count = sweep_expired()
    if expired_count > 0:
        print(f"\n[SCAN] Swept {expired_count} expired positions (past end_date)")

    # Step 0a-C6: Aggressive stale sweep (epoch bugs + auto-resolve)
    try:
        from whale_hunter_connector import aggressive_stale_sweep
        sweep_result = aggressive_stale_sweep()
        if sweep_result.get("total", 0) > 0:
            print(f"[SCAN] Aggressive sweep: {sweep_result['expired']}exp/{sweep_result['epoch_bugs']}epoch/{sweep_result['auto_resolved']}resolved")
    except Exception as e:
        print(f"[WARN] Aggressive stale sweep failed: {e}")

    # Step 0a2: Price-based resolution (fast, local-only, NO API calls)
    try:
        from whale_outcome_tracker import sweep_resolved_prices
        price_result = sweep_resolved_prices()
        if price_result.get("total", 0) > 0:
            print(f"[SCAN] Price sweep: {price_result['won']}W/{price_result['lost']}L resolved")
    except Exception as e:
        print(f"[WARN] Price sweep failed: {e}")

    # Step 0b: Resolve stale positions via Polymarket API (light touch)
    if not skip_refresh:
        print("\n[SYNC] Refreshing positions (resolving via API, limit 20)...")
        refresh_positions(limit=20)  # Keep light — full resolution runs separately

    # Step 1: Get consensus picks (now filtered for live markets only)
    print("\n[STATS] Fetching consensus picks...")
    picks = get_consensus_picks()
    results["picks_found"] = len(picks)
    print(f"   Found {len(picks)} GREEN consensus picks")
    
    if not picks:
        print("   No picks to process")
        return results
    
    # Limit to top N
    picks = picks[:top_n]
    print(f"   Processing top {len(picks)} picks")
    
    # Step 2: Check portfolio heat
    heat = get_portfolio_heat()
    if heat:
        warnings = [c for c, d in heat.get("categories", {}).items() 
                    if d.get("status") == "WARNING"]
        if warnings:
            print(f"   [WARN] Portfolio concentration warnings: {', '.join(warnings)}")
    
    # Step 3: Run MiroFish for each pick
    client = None
    if run_sims:
        try:
            client = MiroFishClient(base_url=MIROFISH_URL, poll_timeout=SIM_TIMEOUT, request_timeout=600)
            if not client.health_check():
                print("   [WARN] MiroFish not running - using cached results only")
                run_sims = False
            else:
                # Warm up LLM to avoid cold start timeout
                warm_up_llm()
        except Exception as e:
            print(f"   [WARN] MiroFish connection failed: {e}")
            run_sims = False
    
    signals = []
    
    for i, pick in enumerate(picks, 1):
        market = pick.get("market_title", "Unknown")[:50]
        condition_id = pick.get("condition_id", "")
        
        print(f"\n[{i}/{len(picks)}] {market}...")
        print(f"   Whales: {pick.get('whale_count')} | "
              f"Agreement: {pick.get('agreement_pct'):.0f}% | "
              f"Confidence: {pick.get('confidence_pct'):.1f}%")
        
        # ── LAYERED VALIDATION (v2.0) ────────────────────────
        # Layer 1: Check cache
        # Layer 2: Ensemble vote (fast — seconds)
        # Layer 3: Domain sim interview (if available)
        # Layer 4: Full MiroFish sim (slow — 25 min, only if --scan)
        # Layer 5: Whale-only fallback
        mirofish_result = None

        # Layer 1: Cache
        cached = get_cached_mirofish(condition_id)
        if cached:
            print(f"   [CACHE] Using cached result (edge: {cached.get('edge', 0):.1f}%)")
            results["sims_cached"] += 1
            mirofish_result = cached

        # Layer 2: Ensemble vote with ENRICHED CONTEXT (whale data + news + sports)
        if mirofish_result is None:
            try:
                voter = EnsembleVoter()
                market_title = pick.get("market_title", "")
                condition_id = pick.get("condition_id", "")
                
                # Use enriched voting that injects whale data, insider flags, 
                # news context, and sports factors automatically
                vote = voter.vote_with_context(
                    market_title=market_title,
                    condition_id=condition_id,
                    base_context=f"Current market price: ${pick.get('avg_entry_price', 0):.2f}"
                )
                if vote.get("ensemble_prob") is not None:
                    ens_prob = vote["ensemble_prob"]
                    market_price = pick.get("avg_entry_price", 0.5)
                    edge = (ens_prob - market_price) * 100

                    print(f"   [ENSEMBLE] {ens_prob:.0%} (confidence: {vote.get('confidence', 0):.0%}) "
                          f"edge: {edge:+.1f}%")

                    mirofish_result = {
                        "status": "success",
                        "swarm_prob": ens_prob * 100,
                        "swarm_sentiment": "bullish" if ens_prob > 0.55 else "bearish" if ens_prob < 0.45 else "neutral",
                        "validates_whales": edge > 0,
                        "edge": edge,
                        "validation_source": "ensemble",
                    }
                    update_mirofish_result(condition_id, mirofish_result)
                    results["sims_run"] += 1
            except Exception as e:
                print(f"   [WARN] Ensemble failed: {e}")

        # Layer 3: Domain sim interview (fast — seconds, if domain sim available)
        if mirofish_result is None:
            try:
                category = categorize_market(pick.get("market_title", ""))
                domain = CATEGORY_TO_DOMAIN.get(category)
                if domain:
                    dsm = DomainSimManager()
                    domain_result = dsm.query_domain(domain, pick.get("market_title", ""))
                    if domain_result.get("status") == "success" and domain_result.get("probability") is not None:
                        domain_prob = domain_result["probability"] / 100.0
                        market_price = pick.get("avg_entry_price", 0.5)
                        edge = (domain_prob - market_price) * 100

                        print(f"   [DOMAIN] {domain.upper()} sim: {domain_prob:.0%} "
                              f"(agents: {domain_result.get('agent_count', '?')}) edge: {edge:+.1f}%")

                        mirofish_result = {
                            "status": "success",
                            "swarm_prob": domain_prob * 100,
                            "swarm_sentiment": "bullish" if domain_prob > 0.55 else "bearish" if domain_prob < 0.45 else "neutral",
                            "validates_whales": edge > 0,
                            "edge": edge,
                            "validation_source": "domain_sim",
                            "domain": domain,
                        }
                        update_mirofish_result(condition_id, mirofish_result)
            except Exception as e:
                print(f"   [WARN] Domain sim query failed: {e}")

        # Layer 4: Full MiroFish sim (slow — 25 min, only if --scan and no result yet)
        if mirofish_result is None and run_sims and client:
            mirofish_result = run_mirofish_sim(pick, client)
            results["sims_run"] += 1

            if mirofish_result.get("status") == "success":
                update_mirofish_result(condition_id, mirofish_result)
            else:
                results["errors"].append({
                    "market": market,
                    "error": mirofish_result.get("error", "Unknown")
                })
                mirofish_result = None

        # Layer 5: Narrative squeeze check (adds context, doesn't replace)
        try:
            squeeze = narrative_squeeze_score(
                market_title=pick.get("market_title", ""),
                market_price=pick.get("avg_entry_price", 0.5),
                swarm_prob=(mirofish_result or {}).get("swarm_prob", None),
                end_date=pick.get("end_date", ""),
            )
            if squeeze["recommendation"] == "FADE":
                print(f"   [SQUEEZE] FADE signal! Score: {squeeze['score']:.0f}/100")
        except Exception:
            pass
        
        # Generate signal - works with or without MiroFish
        # If mirofish_result is None, generate_signal tries whale-only mode
        signal = generate_signal(pick, mirofish_result)

        # ── Save EVERY pick for tracking (not just signals) ──
        save_pick_for_tracking(pick, signal)

        if signal:
            signals.append(signal)
            vtype = "[WHALE] WHALE" if signal.get("validation_type") == "whale_only" else "[FISH] SWARM"
            print(f"   [TARGET] {vtype} SIGNAL: {signal['side']} | Edge: +{signal['edge']:.1f}%")

            # ── Log to outcomes.db for calibration tracking ──
            try:
                from outcome_tracker import OutcomeTracker
                ot = OutcomeTracker()
                pred_prob = signal.get("model_prob", signal.get("confidence", 50) / 100)
                if isinstance(pred_prob, (int, float)) and pred_prob > 1:
                    pred_prob = pred_prob / 100  # Normalize to 0-1
                ot.record_prediction(
                    prediction_id=signal.get("signal_id", f"cs_{condition_id[:12]}"),
                    market_id=condition_id,
                    connector="consensus_swarm",
                    market_title=signal.get("market", market),
                    predicted_probability=pred_prob,
                    market_price=signal.get("entry_price", 0.5),
                    predicted_direction=signal.get("side", "YES"),
                    confidence_score=signal.get("confidence", 50) / 100 if isinstance(signal.get("confidence"), (int, float)) else 0.5,
                )
                print(f"   [STATS] Logged to calibration DB")
            except Exception as e:
                print(f"   [WARN] Calibration log failed: {e}")

            if send_alerts:
                # ── Tiered alerts: instant for high-conf, batch for medium ──
                sig_conf = signal.get("confidence", 50)
                sig_edge = signal.get("edge", 0)
                sig_whales = signal.get("whale_count", 0)

                if sig_conf >= 80 and sig_whales >= 5 and sig_edge >= 15:
                    # [GREEN] HIGH CONFIDENCE — instant Telegram
                    alert = "🟢 HIGH CONFIDENCE\n\n" + format_signal_alert(signal)
                    send_telegram(alert)
                    print(f"   [ALERT] [GREEN] Instant alert sent (high confidence)")
                elif sig_edge >= MIN_EDGE:
                    # [YELLOW] MEDIUM — still alert but tag as medium
                    alert = "🟡 MEDIUM CONFIDENCE\n\n" + format_signal_alert(signal)
                    send_telegram(alert)
                    print(f"   [ALERT] [YELLOW] Alert sent (medium confidence)")
                else:
                    # [RED] LOW — log only, skip Telegram
                    print(f"   [LOG] Logged (low confidence, no alert)")
        else:
            if mirofish_result:
                validates = mirofish_result.get("validates_whales", False)
                edge = mirofish_result.get("edge", 0)
                if not validates:
                    print(f"   [FAIL] Swarm disagrees with whales")
                else:
                    print(f"   [DOWN] Edge too low ({edge:.1f}% < {MIN_EDGE}%)")
            else:
                # Check why whale-only failed
                agreement = pick.get("agreement_pct", 0)
                whale_count = pick.get("whale_count", 0)
                if agreement < 80:
                    print(f"   [DOWN] Agreement too low for whale-only ({agreement:.0f}% < 80%)")
                elif whale_count < 5:
                    print(f"   [DOWN] Not enough whales for whale-only ({whale_count} < 5)")
                else:
                    print(f"   [DOWN] Estimated edge too low")
    
    if client:
        client.close()
    
    results["signals_generated"] = len(signals)
    results["signals"] = signals

    # Step 5: AUTO-EXECUTE valid signals
    if auto_execute and executor and signals:
        print("\n" + "="*60)
        print("[EXEC] AUTO-EXECUTION")
        print("="*60)
        
        for signal in signals:
            try:
                exec_result = executor.execute_signal(signal)
                results["executions"].append(exec_result)
                
                status = exec_result.get("status", "UNKNOWN")
                if status in ("EXECUTED", "DRY_RUN"):
                    size = exec_result.get("size_usd", 0)
                    print(f"   [{'DRY' if dry_run else 'LIVE'}] {signal['market'][:40]}... ${size:.2f}")
                elif status == "SKIPPED":
                    print(f"   [SKIP] {signal['market'][:40]}... {exec_result.get('reason', '')[:30]}")
                else:
                    print(f"   [FAIL] {signal['market'][:40]}... {status}")
                    
            except Exception as e:
                print(f"   [ERROR] Execution failed: {e}")
                results["errors"].append(str(e))
        
        executed = len([e for e in results["executions"] if e.get("status") in ("EXECUTED", "DRY_RUN")])
        print(f"\n[EXEC] {executed}/{len(signals)} signals executed")

    # Step 6: Resolve past consensus picks (close the feedback loop)
    print("\n[LIST] Checking consensus pick outcomes...")
    resolve_consensus_picks()

    # Summary
    print("\n" + "="*60)
    print("[STATS] SUMMARY")
    print("="*60)
    print(f"Picks processed: {len(picks)}")
    print(f"Sims run: {results['sims_run']}")
    print(f"Cached results: {results['sims_cached']}")
    print(f"Signals generated: {results['signals_generated']}")
    
    if results["executions"]:
        executed = len([e for e in results["executions"] if e.get("status") in ("EXECUTED", "DRY_RUN")])
        skipped = len([e for e in results["executions"] if e.get("status") == "SKIPPED"])
        print(f"Trades executed: {executed} (skipped: {skipped})")
    
    if signals:
        print(f"\n[TARGET] ACTIONABLE SIGNALS:")
        for s in signals:
            print(f"   * {s['market'][:40]} | {s['side']} | Edge: +{s['edge']:.1f}%")
    
    if results["errors"]:
        print(f"\n[WARN] Errors: {len(results['errors'])}")
        for e in results["errors"][:3]:
            print(f"   * {e['market'][:30]}: {e['error']}")

    # ── Auto-resolve old picks after every scan ──
    try:
        from consensus_results_tracker import resolve_pending_picks
        print("\n[LIST] Checking consensus pick outcomes...")
        res = resolve_pending_picks()
        resolved = res.get("resolved", 0)
        if resolved > 0:
            print(f"   Resolved {resolved} picks ({res.get('won',0)}W/{res.get('lost',0)}L)")
    except Exception as e:
        print(f"   [WARN] Resolution check failed: {e}")

    return results


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="🐋🐟 Consensus Swarm Connector - Whale + MiroFish Validation"
    )
    parser.add_argument("--scan", action="store_true", 
                        help="Full scan with MiroFish simulations")
    parser.add_argument("--fast", action="store_true",
                        help="Fast check using cached results only")
    parser.add_argument("--top", type=int, default=10,
                        help="Number of top picks to process (default: 10)")
    parser.add_argument("--no-alerts", action="store_true",
                        help="Disable Telegram alerts")
    parser.add_argument("--test", action="store_true",
                        help="Test mode - just show picks without processing")
    parser.add_argument("--refresh-only", action="store_true",
                        help="Just resolve stale positions, no consensus")
    parser.add_argument("--no-refresh", action="store_true",
                        help="Skip position refresh before consensus")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-trigger: only run sims for NEW GREEN picks (conf>80, 5+ whales)")
    parser.add_argument("--execute", action="store_true",
                        help="Auto-execute valid signals (DRY RUN by default)")
    parser.add_argument("--live", action="store_true",
                        help="LIVE TRADING - execute real trades (use with --execute)")

    args = parser.parse_args()

    if args.refresh_only:
        print("\n[SYNC] REFRESH MODE -- resolving stale positions only\n")
        result = refresh_positions(limit=200)
        sys.exit(0)

    if args.test:
        print("\n[TEST] TEST MODE - Showing consensus picks\n")
        picks = get_consensus_picks()
        for i, p in enumerate(picks[:args.top], 1):
            print(f"{i}. {p.get('market_title', 'Unknown')[:50]}")
            print(f"   Whales: {p.get('whale_count')} | "
                  f"Agreement: {p.get('agreement_pct'):.0f}% | "
                  f"Confidence: {p.get('confidence_pct'):.1f}% | "
                  f"Side: {p.get('consensus_side')}")
        return

    if args.auto:
        # Auto-trigger mode: scan for NEW GREEN picks, run sims only on high-conf
        print("\n[AUTO] AUTO MODE -- scanning for new high-confidence picks\n")
        run_sims = True
        send_alerts = True
        # Auto mode: only process GREEN picks with high confidence
        args.top = 5  # Limit to top 5 to save GPU time

    run_sims = (args.scan or args.auto) and not args.fast
    send_alerts = not args.no_alerts
    auto_execute = args.execute
    dry_run = not args.live

    if args.live and not args.execute:
        print("[WARN] --live requires --execute flag")
        sys.exit(1)

    results = run_consensus_swarm(
        top_n=args.top,
        run_sims=run_sims,
        send_alerts=send_alerts,
        skip_refresh=args.no_refresh,
        auto_execute=auto_execute,
        dry_run=dry_run,
    )

    # Exit code based on signals
    sys.exit(0 if results["signals_generated"] > 0 else 1)


if __name__ == "__main__":
    main()
