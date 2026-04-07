#!/usr/bin/env python3
"""
WHALE OUTCOME TRACKER — Track bet outcomes and update whale reputation

Tracks every whale position and resolves them against actual market outcomes.
Updates whale reputation scores based on real performance.

Usage:
    python whale_outcome_tracker.py              # Check and resolve pending positions
    python whale_outcome_tracker.py --status     # Show tracking status
    python whale_outcome_tracker.py --leaderboard # Show whale accuracy leaderboard
"""

import argparse
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Telegram alerting
TELEGRAM_BOT_TOKEN = "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU"
TELEGRAM_CHAT_ID = "939543801"

DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"


def send_telegram_alert(message: str) -> bool:
    """Send alert to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, data=data, timeout=10)
        return resp.ok
    except Exception:
        return False


class WhaleOutcomeTracker:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or DB_PATH)
        self._init_db()

    def _init_db(self):
        """Ensure outcome tracking columns exist."""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            # Add outcome columns to whale_positions if they don't exist
            try:
                conn.execute("ALTER TABLE whale_positions ADD COLUMN outcome TEXT DEFAULT 'pending'")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                conn.execute("ALTER TABLE whale_positions ADD COLUMN resolved_at TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                conn.execute("ALTER TABLE whale_positions ADD COLUMN actual_pnl REAL")
            except sqlite3.OperationalError:
                pass
            
            try:
                conn.execute("ALTER TABLE whale_positions ADD COLUMN final_price REAL")
            except sqlite3.OperationalError:
                pass
            
            # Add accuracy tracking to tracked_whales
            try:
                conn.execute("ALTER TABLE tracked_whales ADD COLUMN tracked_bets INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            
            try:
                conn.execute("ALTER TABLE tracked_whales ADD COLUMN winning_bets INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            
            try:
                conn.execute("ALTER TABLE tracked_whales ADD COLUMN tracked_accuracy REAL DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            
            conn.commit()

    def get_pending_positions(self) -> List[Dict]:
        """Get all positions that haven't been resolved yet."""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT wp.*, tw.display_name as whale_name
                FROM whale_positions wp
                LEFT JOIN tracked_whales tw ON wp.address = tw.address
                WHERE wp.outcome = 'pending' OR wp.outcome IS NULL
                ORDER BY wp.detected_at DESC
            """)
            return [dict(row) for row in cur.fetchall()]

    def check_market_resolution(self, condition_id: str,
                                token_id: str = None) -> Optional[Dict]:
        """Check if a market has resolved on Polymarket.

        Uses clob_token_ids (token_id) for lookup — the condition_id param
        on the Gamma API doesn't actually filter, it returns random results.
        Falls back to condition_id only if token_id is unavailable.
        """
        try:
            # Primary: use clob_token_ids (correct lookup method)
            if token_id:
                resp = requests.get(
                    "https://gamma-api.polymarket.com/markets",
                    params={"clob_token_ids": token_id},
                    timeout=15
                )
            else:
                # Fallback: try condition_id (unreliable)
                resp = requests.get(
                    "https://gamma-api.polymarket.com/markets",
                    params={"condition_id": condition_id},
                    timeout=15
                )

            if not resp.ok:
                return None

            data = resp.json()
            if not data:
                return None

            market = data[0] if isinstance(data, list) else data

            # Verify we got the right market (not a random match)
            if token_id:
                clob_ids = market.get('clobTokenIds', [])
                if isinstance(clob_ids, str):
                    try:
                        clob_ids = json.loads(clob_ids)
                    except (json.JSONDecodeError, TypeError):
                        clob_ids = []
                if token_id not in clob_ids:
                    # Wrong market returned — skip
                    return None
            
            # Check if closed
            is_closed = market.get('closed', False)
            
            if is_closed:
                # Get outcome prices
                outcome_prices = market.get('outcomePrices', [])
                if isinstance(outcome_prices, str):
                    try:
                        outcome_prices = json.loads(outcome_prices)
                    except (json.JSONDecodeError, TypeError):
                        outcome_prices = []
                
                # Check resolution: price of 1.0 means that outcome won, 0 means it lost
                yes_won = False
                no_won = False
                
                if len(outcome_prices) >= 2:
                    yes_price = float(outcome_prices[0]) if outcome_prices[0] else 0
                    no_price = float(outcome_prices[1]) if outcome_prices[1] else 0
                    
                    # If both are 0, market was voided or not yet fully resolved
                    if yes_price == 0 and no_price == 0:
                        return {"resolved": False, "voided": True}
                    
                    if yes_price > 0.95:
                        yes_won = True
                    elif no_price > 0.95:
                        no_won = True
                
                if not yes_won and not no_won:
                    # Not clearly resolved yet
                    return {"resolved": False}
                
                return {
                    "resolved": True,
                    "yes_won": yes_won,
                    "no_won": no_won,
                    "final_yes_price": yes_price,
                    "final_no_price": no_price,
                    "market_title": market.get('question', ''),
                }
            
            return {"resolved": False}
            
        except Exception as e:
            print(f"Error checking market {condition_id[:20]}...: {e}")
            return None

    def resolve_position(self, position_id: int, outcome: str, final_price: float, actual_pnl: float):
        """Mark a position as resolved and update whale stats."""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            cur = conn.cursor()
            
            # Update position
            cur.execute("""
                UPDATE whale_positions 
                SET outcome = ?, resolved_at = ?, final_price = ?, actual_pnl = ?
                WHERE id = ?
            """, (outcome, datetime.now().isoformat(), final_price, actual_pnl, position_id))
            
            # Get whale address for this position
            cur.execute("SELECT address FROM whale_positions WHERE id = ?", (position_id,))
            row = cur.fetchone()
            if row:
                whale_address = row[0]
                
                # Update whale stats
                if outcome == 'won':
                    cur.execute("""
                        UPDATE tracked_whales 
                        SET tracked_bets = COALESCE(tracked_bets, 0) + 1,
                            winning_bets = COALESCE(winning_bets, 0) + 1,
                            tracked_accuracy = CAST(COALESCE(winning_bets, 0) + 1 AS REAL) / 
                                              CAST(COALESCE(tracked_bets, 0) + 1 AS REAL)
                        WHERE address = ?
                    """, (whale_address,))
                else:
                    cur.execute("""
                        UPDATE tracked_whales 
                        SET tracked_bets = COALESCE(tracked_bets, 0) + 1,
                            tracked_accuracy = CAST(COALESCE(winning_bets, 0) AS REAL) / 
                                              CAST(COALESCE(tracked_bets, 0) + 1 AS REAL)
                        WHERE address = ?
                    """, (whale_address,))
            
            conn.commit()

    def check_and_resolve_all(self, limit: int = 50) -> Dict:
        """Check all pending positions and resolve any that have completed."""
        import time
        import sys
        pending = self.get_pending_positions()[:limit]  # Limit to avoid API overload
        print(f"\n[STATS] Checking {len(pending)} pending positions...", flush=True)
        
        resolved_count = 0
        won_count = 0
        lost_count = 0
        alerts = []
        checked = 0
        
        for pos in pending:
            checked += 1
            if checked % 10 == 0:
                print(f"  Progress: {checked}/{len(pending)}", flush=True)
            time.sleep(0.3)  # Rate limit: ~3 requests per second
            condition_id = pos['condition_id']
            token_id = pos.get('token_id', '')
            result = self.check_market_resolution(condition_id, token_id=token_id)
            
            if not result or not result.get('resolved'):
                continue
            
            # Determine if whale's position won
            whale_side = pos['side'].upper()
            whale_won = False
            
            if whale_side == 'YES' and result.get('yes_won'):
                whale_won = True
            elif whale_side == 'NO' and result.get('no_won'):
                whale_won = True
            
            # Calculate P&L
            entry_price = pos['entry_price'] or 0.5
            size_usd = pos['size_usd'] or 0
            
            if whale_won:
                # Won: profit = shares * (1 - entry_price)
                shares = size_usd / entry_price if entry_price > 0 else 0
                actual_pnl = shares * (1 - entry_price)
                outcome = 'won'
                won_count += 1
            else:
                # Lost: lose entire position
                actual_pnl = -size_usd
                outcome = 'lost'
                lost_count += 1
            
            final_price = result.get('final_yes_price') if whale_side == 'YES' else result.get('final_no_price')
            
            # Resolve the position
            self.resolve_position(pos['id'], outcome, final_price or 0, actual_pnl)
            resolved_count += 1
            
            # Create alert
            whale_name = pos.get('whale_name', 'Unknown')
            tg_emoji = "✅" if whale_won else "❌"
            print_emoji = "[OK]" if whale_won else "[FAIL]"
            pnl_str = f"+${actual_pnl:,.2f}" if actual_pnl > 0 else f"-${abs(actual_pnl):,.2f}"

            alert = f"{tg_emoji} <b>BET RESOLVED</b>\n"
            alert += f"Whale: {whale_name}\n"
            alert += f"Market: {pos['market_title'][:50]}...\n"
            alert += f"Position: {whale_side} @ ${entry_price:.2f}\n"
            alert += f"Result: <b>{'WON' if whale_won else 'LOST'}</b>\n"
            alert += f"P&L: {pnl_str}"

            alerts.append(alert)
            print(f"  {print_emoji} {whale_name}: {outcome.upper()} on {pos['market_title'][:40]}... ({pnl_str})")
        
        # Send combined alert if any resolved
        if alerts:
            combined = f"🐋 <b>WHALE BET OUTCOMES</b>\n\n" + "\n\n".join(alerts[:5])  # Max 5 per message
            send_telegram_alert(combined)
        
        return {
            "checked": len(pending),
            "resolved": resolved_count,
            "won": won_count,
            "lost": lost_count
        }

    def get_whale_leaderboard(self) -> List[Dict]:
        """Get whale accuracy leaderboard based on tracked outcomes."""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    display_name,
                    elite_score,
                    pnl,
                    COALESCE(tracked_bets, 0) as tracked_bets,
                    COALESCE(winning_bets, 0) as winning_bets,
                    COALESCE(tracked_accuracy, 0) as tracked_accuracy
                FROM tracked_whales
                WHERE COALESCE(tracked_bets, 0) > 0
                ORDER BY tracked_accuracy DESC, tracked_bets DESC
                LIMIT 20
            """)
            return [dict(row) for row in cur.fetchall()]

    def get_tracking_status(self) -> Dict:
        """Get overall tracking status."""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            cur = conn.cursor()
            
            # Total positions
            cur.execute("SELECT COUNT(*) FROM whale_positions")
            total = cur.fetchone()[0]
            
            # Pending
            cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'pending' OR outcome IS NULL")
            pending = cur.fetchone()[0]
            
            # Won
            cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'won'")
            won = cur.fetchone()[0]
            
            # Lost
            cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'lost'")
            lost = cur.fetchone()[0]
            
            # Total P&L from resolved
            cur.execute("SELECT SUM(actual_pnl) FROM whale_positions WHERE outcome IN ('won', 'lost')")
            total_pnl = cur.fetchone()[0] or 0
            
            return {
                "total_positions": total,
                "pending": pending,
                "resolved": won + lost,
                "won": won,
                "lost": lost,
                "win_rate": won / (won + lost) if (won + lost) > 0 else 0,
                "total_pnl": total_pnl
            }


def cmd_status():
    """Show tracking status."""
    tracker = WhaleOutcomeTracker()
    status = tracker.get_tracking_status()
    
    print("\n" + "=" * 50)
    print("[WHALE] WHALE OUTCOME TRACKING STATUS")
    print("=" * 50)
    print(f"Total Positions:  {status['total_positions']}")
    print(f"Pending:          {status['pending']}")
    print(f"Resolved:         {status['resolved']}")
    print(f"  [OK] Won:         {status['won']}")
    print(f"  [FAIL] Lost:        {status['lost']}")
    print(f"Win Rate:         {status['win_rate']:.1%}")
    print(f"Total P&L:        ${status['total_pnl']:,.2f}")
    print("=" * 50)


def cmd_leaderboard():
    """Show whale accuracy leaderboard."""
    tracker = WhaleOutcomeTracker()
    leaders = tracker.get_whale_leaderboard()
    
    print("\n" + "=" * 60)
    print("[TOP] WHALE ACCURACY LEADERBOARD (Tracked Bets)")
    print("=" * 60)
    print(f"{'Rank':<5} {'Whale':<20} {'Bets':<6} {'Won':<5} {'Accuracy':<10} {'Elite':<6}")
    print("-" * 60)
    
    for i, w in enumerate(leaders, 1):
        print(f"{i:<5} {w['display_name'][:19]:<20} {w['tracked_bets']:<6} "
              f"{w['winning_bets']:<5} {w['tracked_accuracy']:.1%}      {w['elite_score']:.1f}")
    
    if not leaders:
        print("  No resolved bets yet. Run --check to resolve pending positions.")
    
    print("=" * 60)


def sweep_resolved_prices():
    """Fast LOCAL sweep: mark positions won/lost when current_price shows resolution.

    No API calls — just checks current_price in the DB.
    This is the primary defense against stale data.

    For binary markets:
      - current_price >= 0.95 on a token means that token's side WON
      - current_price <= 0.05 on a token means that token's side LOST

    But current_price tracks the token the whale holds, so:
      - If whale holds YES and price >= 0.95 → whale WON (YES resolved true)
      - If whale holds YES and price <= 0.05 → whale LOST (YES resolved false)
      - If whale holds NO and price >= 0.95 → whale WON (NO resolved true)
      - If whale holds NO and price <= 0.05 → whale LOST (NO resolved false)
    """
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")

    # Whale's token price >= 0.95 → they WON
    won = conn.execute("""
        UPDATE whale_positions
        SET outcome = 'won',
            resolved_at = datetime('now'),
            actual_pnl = CASE
                WHEN entry_price > 0 THEN (size_usd / entry_price) * (1.0 - entry_price)
                ELSE 0 END
        WHERE outcome = 'pending'
          AND current_price >= 0.95
          AND current_price IS NOT NULL
    """).rowcount

    # Whale's token price <= 0.05 → they LOST
    lost = conn.execute("""
        UPDATE whale_positions
        SET outcome = 'lost',
            resolved_at = datetime('now'),
            actual_pnl = -COALESCE(size_usd, 0)
        WHERE outcome = 'pending'
          AND current_price <= 0.05
          AND current_price IS NOT NULL
    """).rowcount

    conn.commit()
    conn.close()

    total = won + lost
    if total > 0:
        print(f"  [SWEEP] Price-based resolution: {won} won, {lost} lost ({total} total)")
    return {"won": won, "lost": lost, "total": total}


def cmd_check():
    """Check and resolve pending positions."""
    tracker = WhaleOutcomeTracker()
    result = tracker.check_and_resolve_all()

    print(f"\n{'=' * 50}")
    print(f"RESOLUTION COMPLETE")
    print(f"  Checked: {result['checked']} pending positions")
    print(f"  Resolved: {result['resolved']}")
    print(f"    [OK] Won: {result['won']}")
    print(f"    [FAIL] Lost: {result['lost']}")
    print(f"{'=' * 50}")


def cmd_report():
    """Generate comprehensive WHALE TRACKER — WINS & LOSSES REPORT."""
    tracker = WhaleOutcomeTracker()
    db_path = tracker.db_path

    import sqlite3 as _sql
    conn = _sql.connect(db_path)
    conn.row_factory = _sql.Row

    # Header
    resolved = conn.execute(
        "SELECT COUNT(*) FROM whale_positions WHERE outcome IN ('won','lost')"
    ).fetchone()[0]
    won = conn.execute(
        "SELECT COUNT(*) FROM whale_positions WHERE outcome = 'won'"
    ).fetchone()[0]
    lost = conn.execute(
        "SELECT COUNT(*) FROM whale_positions WHERE outcome = 'lost'"
    ).fetchone()[0]
    total_pnl = conn.execute(
        "SELECT COALESCE(SUM(actual_pnl), 0) FROM whale_positions WHERE outcome IN ('won','lost')"
    ).fetchone()[0]

    print("=" * 80)
    print("WHALE TRACKER - WINS & LOSSES REPORT")
    print(f"Generated: {datetime.now().isoformat()}")
    print(f"Resolved Trades: {resolved}  |  Won: {won}  |  Lost: {lost}  |  P&L: ${total_pnl:,.2f}")
    print("=" * 80)

    # Per-whale breakdown
    whales = conn.execute("""
        SELECT tw.display_name,
               SUM(CASE WHEN wp.outcome='won' THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN wp.outcome='lost' THEN 1 ELSE 0 END) as losses,
               SUM(wp.actual_pnl) as total_pnl,
               SUM(wp.size_usd) as total_risked,
               tw.elite_score,
               COALESCE(tw.tracked_accuracy, 0) as acc
        FROM whale_positions wp
        JOIN tracked_whales tw ON wp.address = tw.address
        WHERE wp.outcome IN ('won', 'lost')
        GROUP BY tw.display_name
        ORDER BY wins + losses DESC
    """).fetchall()

    for w in whales:
        total = w['wins'] + w['losses']
        wr = w['wins'] / total * 100 if total > 0 else 0
        print(f"\n{'─' * 60}")
        print(f"  {w['display_name']}  |  {w['wins']}W / {w['losses']}L "
              f"({wr:.1f}%)  |  P&L: ${w['total_pnl']:,.2f}  |  "
              f"Elite: {w['elite_score']:.1f}")
        print(f"{'─' * 60}")

        # Individual trades for this whale
        trades = conn.execute("""
            SELECT wp.market_title, wp.side, wp.entry_price, wp.size_usd,
                   wp.actual_pnl, wp.outcome, wp.resolved_at
            FROM whale_positions wp
            JOIN tracked_whales tw ON wp.address = tw.address
            WHERE tw.display_name = ? AND wp.outcome IN ('won','lost')
            ORDER BY ABS(wp.actual_pnl) DESC
        """, (w['display_name'],)).fetchall()

        for t in trades:
            emoji = "WIN " if t['outcome'] == 'won' else "LOSS"
            pnl_str = f"+${t['actual_pnl']:,.2f}" if t['actual_pnl'] > 0 else f"-${abs(t['actual_pnl']):,.2f}"
            print(f"    {emoji} | {t['side']:3s} @ ${t['entry_price']:.4f} | "
                  f"Size: ${t['size_usd']:>10,.2f} | "
                  f"P&L: {pnl_str:>14s} | {(t['market_title'] or '')[:45]}")

    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY BY WHALE")
    print(f"{'Whale':20s} {'Bets':>5s} {'W':>4s} {'L':>4s} {'WR':>7s} {'P&L':>14s} {'Risked':>14s}")
    print("-" * 80)
    for w in whales:
        total = w['wins'] + w['losses']
        wr = w['wins'] / total * 100 if total > 0 else 0
        print(f"{w['display_name']:20s} {total:5d} {w['wins']:4d} {w['losses']:4d} "
              f"{wr:6.1f}% ${w['total_pnl']:>13,.2f} ${w['total_risked']:>13,.2f}")
    print("=" * 80)
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Whale Outcome Tracker")
    parser.add_argument("--status", action="store_true", help="Show tracking status")
    parser.add_argument("--leaderboard", action="store_true", help="Show whale accuracy leaderboard")
    parser.add_argument("--check", action="store_true", help="Check and resolve pending positions")
    parser.add_argument("--report", action="store_true", help="Full wins & losses report")
    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.leaderboard:
        cmd_leaderboard()
    elif args.check:
        cmd_check()
    elif args.report:
        cmd_report()
    else:
        # Default: check and resolve
        cmd_check()
        cmd_status()
