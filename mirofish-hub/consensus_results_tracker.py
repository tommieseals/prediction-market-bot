#!/usr/bin/env python3
"""
📊 CONSENSUS RESULTS TRACKER

Verifies consensus picks against actual Polymarket outcomes.
Tracks P&L and performance metrics.

Usage:
    python consensus_results_tracker.py              # Check all pending
    python consensus_results_tracker.py --summary    # Performance summary
    python consensus_results_tracker.py --live       # Show live picks only
"""

import sqlite3
import requests
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"
GAMMA_API = "https://gamma-api.polymarket.com"


def get_market_outcome(condition_id: str) -> Optional[Dict]:
    """Check Polymarket for resolved outcome."""
    try:
        # Get positions to find token_id
        conn = sqlite3.connect(DB_PATH, timeout=30)
        cur = conn.cursor()
        cur.execute("""
            SELECT token_id FROM whale_positions 
            WHERE condition_id = ? LIMIT 1
        """, (condition_id,))
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return None
        
        token_id = row[0]
        
        # Query Gamma API with clob_token_ids
        url = f"{GAMMA_API}/markets?clob_token_ids={token_id}"
        resp = requests.get(url, timeout=15)
        
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        if not data or len(data) == 0:
            return None
        
        market = data[0]
        
        # Check if resolved
        closed = market.get("closed", False)
        end_date = market.get("end_date_iso")

        # Determine winner from outcomePrices (primary) or tokens (fallback)
        winner = None

        # Method 1: outcomePrices — ["0", "1"] means outcome[1] won
        outcome_prices = market.get("outcomePrices", [])
        if isinstance(outcome_prices, str):
            import json as _json
            try:
                outcome_prices = _json.loads(outcome_prices)
            except Exception:
                outcome_prices = []

        outcomes = market.get("outcomes", [])
        if isinstance(outcomes, str):
            import json as _json
            try:
                outcomes = _json.loads(outcomes)
            except Exception:
                outcomes = []

        if outcome_prices and len(outcome_prices) >= 2:
            try:
                prices = [float(p) for p in outcome_prices]
                if prices[0] > 0.95:
                    # First outcome won — for binary markets this is YES
                    winner = "YES"
                elif prices[1] > 0.95:
                    # Second outcome won — for binary markets this is NO
                    winner = "NO"
            except (ValueError, TypeError):
                pass

        # Method 2: tokens[].winner (fallback if outcomePrices didn't work)
        if winner is None:
            tokens = market.get("tokens", []) or []
            for token in tokens:
                if token.get("winner") is True:
                    winner = token.get("outcome", "").upper()
                    break

        return {
            "closed": closed,
            "winner": winner,
            "end_date": end_date,
            "title": market.get("question", "")
        }
        
    except Exception as e:
        print(f"  [WARN] API error: {e}")
        return None


def resolve_pending_picks(bet_size: float = 100) -> Dict:
    """Check all pending consensus picks and resolve outcomes.

    Args:
        bet_size: Standardized bet size for P&L calculation (default $100).
                  This gives a per-unit P&L that's comparable across picks.
    """
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    
    # Get pending picks with past end_dates
    cur.execute("""
        SELECT id, market_title, condition_id, side, confidence, 
               avg_entry_price, created_at
        FROM consensus_picks
        WHERE outcome = 'pending'
        ORDER BY created_at ASC
    """)
    
    pending = cur.fetchall()
    print(f"\n[STATS] Checking {len(pending)} pending consensus picks...\n")
    
    resolved = 0
    won = 0
    lost = 0
    still_pending = 0
    
    for pick in pending:
        pick_id, title, cid, side, conf, entry, created = pick
        
        print(f"• {title[:50]}...")
        print(f"  Pick: {side} @ ${entry:.2f} | Confidence: {conf:.0f}%")
        
        result = get_market_outcome(cid)
        
        if not result:
            print(f"  [WAIT] Market not found or API error")
            still_pending += 1
            continue
        
        if not result["closed"]:
            print(f"  [WAIT] Still open")
            still_pending += 1
            continue
        
        winner = result["winner"]
        if not winner:
            print(f"  [WAIT] No winner declared yet")
            still_pending += 1
            continue
        
        # Determine if we won
        is_win = (side == winner)
        outcome = "won" if is_win else "lost"
        
        # Calculate P&L (standardized unit bet)
        if is_win:
            # Won: profit = bet / entry_price - bet
            pnl = (bet_size / entry) - bet_size if entry > 0 else 0
        else:
            # Lost: lose the bet
            pnl = -bet_size
        
        # Update database
        cur.execute("""
            UPDATE consensus_picks
            SET outcome = ?, 
                resolved_at = datetime('now'),
                won = ?,
                profit_loss = ?
            WHERE id = ?
        """, (outcome, 1 if is_win else 0, pnl, pick_id))
        
        resolved += 1
        if is_win:
            won += 1
            print(f"  [OK] WON! Winner: {winner} | P&L: +${pnl:.2f}")
        else:
            lost += 1
            print(f"  [FAIL] LOST. Winner: {winner} | P&L: -${bet_size:.2f}")
    
    conn.commit()
    conn.close()
    
    return {
        "checked": len(pending),
        "resolved": resolved,
        "won": won,
        "lost": lost,
        "still_pending": still_pending
    }


def get_performance_summary() -> None:
    """Print overall performance summary."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    
    print("\n" + "="*60)
    print("[STATS] CONSENSUS PICKS PERFORMANCE")
    print("="*60)
    
    # Overall stats
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN outcome = 'lost' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN outcome = 'pending' THEN 1 ELSE 0 END) as pending,
            SUM(COALESCE(profit_loss, 0)) as total_pnl
        FROM consensus_picks
    """)
    
    row = cur.fetchone()
    total, wins, losses, pending, total_pnl = row
    
    print(f"\n[UP] Overall Record:")
    print(f"   Total picks: {total}")
    print(f"   Resolved: {wins + losses}")
    print(f"   Pending: {pending}")
    
    if wins + losses > 0:
        win_rate = wins / (wins + losses) * 100
        print(f"\n[TARGET] Win Rate: {win_rate:.1f}% ({wins}W / {losses}L)")
        print(f"[MONEY] Total P&L: ${total_pnl:.2f}")
    
    # Recent picks
    print(f"\n[LIST] Recent Resolved Picks:")
    cur.execute("""
        SELECT market_title, side, outcome, profit_loss, resolved_at
        FROM consensus_picks
        WHERE outcome IN ('won', 'lost')
        ORDER BY resolved_at DESC
        LIMIT 10
    """)
    
    for title, side, outcome, pnl, resolved in cur.fetchall():
        emoji = "[OK]" if outcome == "won" else "[FAIL]"
        pnl_str = f"+${pnl:.0f}" if pnl > 0 else f"-${abs(pnl):.0f}"
        print(f"   {emoji} {side} | {pnl_str} | {title[:40]}")
    
    conn.close()


def show_live_picks() -> None:
    """Show currently pending picks."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    
    print("\n" + "="*60)
    print("[RED] LIVE CONSENSUS PICKS")
    print("="*60)
    
    cur.execute("""
        SELECT market_title, side, confidence, avg_entry_price, 
               created_at, end_date
        FROM consensus_picks
        WHERE outcome = 'pending'
        ORDER BY created_at DESC
    """)
    
    picks = cur.fetchall()
    
    if not picks:
        print("\nNo pending picks.")
    else:
        print(f"\n{len(picks)} active picks:\n")
        for title, side, conf, entry, created, end_date in picks:
            end_str = end_date[:10] if end_date else "TBD"
            print(f"• {title[:50]}")
            print(f"  {side} @ ${entry:.2f} | Conf: {conf:.0f}% | Ends: {end_str}")
            print()
    
    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="📊 Consensus Results Tracker"
    )
    parser.add_argument("--summary", action="store_true",
                        help="Show performance summary")
    parser.add_argument("--live", action="store_true",
                        help="Show live picks only")
    parser.add_argument("--resolve", action="store_true",
                        help="Resolve pending picks (default)")
    
    args = parser.parse_args()
    
    if args.summary:
        get_performance_summary()
    elif args.live:
        show_live_picks()
    else:
        result = resolve_pending_picks()
        
        print("\n" + "="*60)
        print("[STATS] RESOLUTION SUMMARY")
        print("="*60)
        print(f"Checked: {result['checked']}")
        print(f"Resolved: {result['resolved']} ({result['won']}W / {result['lost']}L)")
        print(f"Still pending: {result['still_pending']}")
        
        # Show updated summary
        get_performance_summary()


if __name__ == "__main__":
    main()
