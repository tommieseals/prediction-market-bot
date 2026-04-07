#!/usr/bin/env python3
"""
VALIDATE PICKS - Integration script for whale_hunter_connector

This script:
1. Fetches pending consensus picks from the database
2. Runs each through the three-agent pipeline
3. Updates the database with validation results
4. Sends Telegram alerts for TRADE signals

Usage:
    python validate_picks.py --top 5        # Validate top 5 picks
    python validate_picks.py --pick <id>    # Validate specific pick
    python validate_picks.py --continuous   # Run continuously
"""

import argparse
import sqlite3
import json
import time
import requests
from datetime import datetime
from pathlib import Path
import sys
import os

# Add parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import AgentOrchestrator, TradeSignal

# Paths
WHALE_DB = Path(__file__).parent.parent / "data" / "whale_hunter.db"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "939543801")


def send_telegram_alert(message: str) -> bool:
    """Send Telegram alert for trade signals."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        return resp.ok
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def get_pending_picks(limit: int = 10) -> list:
    """Get pending consensus picks from database."""
    conn = sqlite3.connect(str(WHALE_DB))
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute("""
        SELECT 
            id, market_title, condition_id, side as consensus_side,
            whale_count, avg_entry_price, confidence, created_at,
            end_date, notes
        FROM consensus_picks
        WHERE (outcome = 'pending' OR outcome IS NULL)
          AND (end_date IS NULL OR datetime(end_date) > datetime('now'))
        ORDER BY whale_count DESC, confidence DESC
        LIMIT ?
    """, (limit,)).fetchall()
    
    conn.close()
    return [dict(r) for r in rows]


def update_pick_validation(pick_id: int, signal: TradeSignal):
    """Update consensus pick with validation results."""
    try:
        conn = sqlite3.connect(str(WHALE_DB))
        
        # Update notes with validation info
        validation_summary = (
            f"VALIDATED: {signal.decision} | "
            f"Score: {signal.overall_score:.0%} | "
            f"Edge: {signal.edge:.1%} | "
            f"Validates whales: {signal.validates_whales}"
        )
        
        conn.execute("""
            UPDATE consensus_picks
            SET notes = COALESCE(notes, '') || ' | ' || ?
            WHERE id = ?
        """, (validation_summary, pick_id))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"DB update error: {e}")


def format_trade_alert(signal: TradeSignal) -> str:
    """Format a trade signal as a Telegram alert."""
    emoji = "🟢" if signal.decision == "TRADE" else "🔴"
    
    alert = f"""
{emoji} <b>AGENT VALIDATION COMPLETE</b>

<b>Market:</b> {signal.market_title[:50]}
<b>Decision:</b> {signal.decision}
<b>Side:</b> {signal.side}

<b>Analysis:</b>
• Edge: {signal.edge:.1%}
• Score: {signal.overall_score:.0%}
• Confidence: {signal.confidence:.0%}
• Validates whales: {'✅' if signal.validates_whales else '❌'}

<b>Whale Data:</b>
• {signal.whale_count} whales on {signal.whale_consensus}
• Entry: ${signal.entry_price:.3f}
"""
    
    if signal.decision == "TRADE":
        alert += f"""
💰 <b>TRADE SIGNAL</b>
• Recommended size: ${signal.recommended_size:.2f}
• Stop loss: ${signal.stop_loss:.3f}
"""
    
    if signal.concerns:
        alert += f"\n⚠️ <b>Concerns:</b> {signal.concerns[0][:50]}"
    
    return alert.strip()


def validate_picks(picks: list, bankroll: float = 500.0, fast_mode: bool = False) -> list:
    """Validate a list of picks through the agent pipeline."""
    if fast_mode:
        print("[FAST MODE] Skipping LLM profile generation for speed")
    orchestrator = AgentOrchestrator(bankroll=bankroll, fast_mode=fast_mode)
    results = []
    
    for i, pick in enumerate(picks):
        print(f"\n[{i+1}/{len(picks)}] Validating: {pick['market_title'][:50]}")
        
        try:
            # Run through agent pipeline
            signal = orchestrator.process_pick(pick)
            results.append(signal)
            
            # Update database
            if pick.get('id'):
                update_pick_validation(pick['id'], signal)
            
            # Send alert for TRADE signals
            if signal.decision == "TRADE":
                alert = format_trade_alert(signal)
                if send_telegram_alert(alert):
                    print(f"  📱 Alert sent")
            
            # Rate limit
            time.sleep(2)
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Validate whale picks with agent pipeline")
    parser.add_argument("--top", type=int, default=5, help="Validate top N picks")
    parser.add_argument("--pick", type=int, help="Validate specific pick ID")
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    parser.add_argument("--bankroll", type=float, default=500.0, help="Bankroll for sizing")
    parser.add_argument("--fast", action="store_true", help="Fast mode (skip LLM profiles, ~10x faster)")
    args = parser.parse_args()
    
    print("=" * 60)
    print("MIROFISH THREE-AGENT VALIDATION PIPELINE")
    print("=" * 60)
    
    if args.continuous:
        print("Running continuously (Ctrl+C to stop)...")
        while True:
            picks = get_pending_picks(limit=3)
            if picks:
                print(f"\nFound {len(picks)} picks to validate")
                validate_picks(picks, args.bankroll, fast_mode=args.fast)
            else:
                print("No pending picks")
            
            print(f"\nSleeping 30 minutes...")
            time.sleep(30 * 60)
    
    elif args.pick:
        conn = sqlite3.connect(str(WHALE_DB))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM consensus_picks WHERE id = ?", 
            (args.pick,)
        ).fetchone()
        conn.close()
        
        if row:
            picks = [dict(row)]
            validate_picks(picks, args.bankroll, fast_mode=args.fast)
        else:
            print(f"Pick ID {args.pick} not found")
    
    else:
        picks = get_pending_picks(limit=args.top)
        if picks:
            print(f"\nFound {len(picks)} picks to validate:")
            for p in picks:
                print(f"  • {p['market_title'][:50]} ({p['whale_count']} whales)")
            
            print()
            results = validate_picks(picks, args.bankroll, fast_mode=args.fast)
            
            # Summary
            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            trades = [r for r in results if r.decision == "TRADE"]
            no_trades = [r for r in results if r.decision == "NO_TRADE"]
            
            print(f"Total validated: {len(results)}")
            print(f"TRADE signals: {len(trades)}")
            print(f"NO_TRADE: {len(no_trades)}")
            
            if trades:
                print("\n💰 TRADE SIGNALS:")
                for t in trades:
                    print(f"  {t.side} {t.market_title[:40]} | ${t.recommended_size:.2f} | Edge: {t.edge:.1%}")
        else:
            print("No pending picks to validate")


if __name__ == "__main__":
    main()
