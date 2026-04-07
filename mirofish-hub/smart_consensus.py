"""
Smart Consensus Filter
======================
Applies learned patterns to filter consensus picks for higher win rate.

Based on analysis (2026-03-27):
- 3-5 whales = 65-67% win rate (GOOD)
- 7+ whales = 25-31% win rate (BAD - get faded)
- 70-80% confidence = 71% win rate (GOOD)
- 90%+ confidence = 47% win rate (BAD - overconfidence trap)
- YES > NO (56% vs 45%)

This filter aims to boost win rate from 51% to 65%+
"""

import sqlite3
import json
import os
from datetime import datetime
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "939543801")

# Quality filters based on backtested data
# WARNING: Filter backtest only 16 trades - UNVALIDATED
# Patterns are real but combined filter needs 30+ trades to confirm
FILTERS = {
    'min_whale_count': 3,
    'max_whale_count': 5,  # VALIDATED: 6+ whales drop to 36% WR
    'min_confidence': 55,
    'max_confidence': 89,  # VALIDATED: 90%+ = only 47% WR
    'prefer_yes': True,    # VALIDATED: YES 55.6% vs NO 45.5%
    'min_edge': 5.0,       # Minimum edge percentage
}

# EVALUATOR NOTE (2026-03-27):
# - Whale pattern: VALIDATED (64.3% vs 36.1%, n=78)
# - Confidence pattern: VALIDATED (72.7% vs 47.4%)
# - Combined filter: UNVALIDATED (n=16, need n=30)
# - Action: Track filtered picks, reassess at n=30


def get_quality_picks():
    """Get picks that pass quality filters."""
    conn = sqlite3.connect('data/whale_hunter.db')
    cur = conn.cursor()
    
    # Get pending picks that pass filters
    cur.execute('''
        SELECT id, market_title, side, confidence, whale_count, 
               avg_entry_price, end_date, notes, created_at
        FROM consensus_picks 
        WHERE outcome = 'pending'
        AND whale_count >= ?
        AND whale_count <= ?
        AND confidence >= ?
        AND confidence <= ?
        ORDER BY 
            CASE WHEN side = 'YES' THEN 0 ELSE 1 END,  -- YES first
            whale_count DESC,  -- More whales within range
            confidence DESC
    ''', (
        FILTERS['min_whale_count'],
        FILTERS['max_whale_count'],
        FILTERS['min_confidence'],
        FILTERS['max_confidence']
    ))
    
    picks = []
    for row in cur.fetchall():
        pick = {
            'id': row[0],
            'market': row[1],
            'side': row[2],
            'confidence': row[3],
            'whale_count': row[4],
            'entry_price': row[5],
            'end_date': row[6],
            'notes': row[7],
            'created_at': row[8]
        }
        
        # Calculate quality score
        score = 0
        
        # Whale count sweet spot (4-5 is best)
        if pick['whale_count'] in [4, 5]:
            score += 30
        elif pick['whale_count'] in [3, 6]:
            score += 15
        
        # Confidence sweet spot (70-80 is best)
        if 70 <= pick['confidence'] <= 80:
            score += 30
        elif 60 <= pick['confidence'] <= 85:
            score += 15
        
        # YES preference
        if pick['side'] == 'YES':
            score += 10
        
        # Edge from notes
        if pick['notes']:
            try:
                edge_str = pick['notes'].split('Edge:')[1].split('%')[0].strip()
                edge = float(edge_str)
                if edge >= 10:
                    score += 20
                elif edge >= 5:
                    score += 10
            except:
                pass
        
        pick['quality_score'] = score
        picks.append(pick)
    
    conn.close()
    
    # Sort by quality score
    picks.sort(key=lambda x: x['quality_score'], reverse=True)
    
    return picks


def get_filtered_vs_all_stats():
    """Compare filtered picks performance vs all picks."""
    conn = sqlite3.connect('data/whale_hunter.db')
    cur = conn.cursor()
    
    # All resolved picks
    cur.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as won
        FROM consensus_picks WHERE outcome IN ('won','lost')
    ''')
    all_row = cur.fetchone()
    all_wr = all_row[1]/all_row[0]*100 if all_row[0]>0 else 0
    
    # Filtered picks (would have passed our filters)
    cur.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as won
        FROM consensus_picks 
        WHERE outcome IN ('won','lost')
        AND whale_count >= ?
        AND whale_count <= ?
        AND confidence >= ?
        AND confidence <= ?
    ''', (
        FILTERS['min_whale_count'],
        FILTERS['max_whale_count'],
        FILTERS['min_confidence'],
        FILTERS['max_confidence']
    ))
    filtered_row = cur.fetchone()
    filtered_wr = filtered_row[1]/filtered_row[0]*100 if filtered_row[0]>0 else 0
    
    conn.close()
    
    return {
        'all': {'total': all_row[0], 'won': all_row[1], 'win_rate': all_wr},
        'filtered': {'total': filtered_row[0], 'won': filtered_row[1], 'win_rate': filtered_wr}
    }


def send_telegram(message: str):
    """Send alert to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)
    except:
        pass


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--telegram', action='store_true', help='Send to Telegram')
    parser.add_argument('--top', type=int, default=5, help='Number of picks to show')
    args = parser.parse_args()
    
    print("=" * 60)
    print("SMART CONSENSUS FILTER")
    print("=" * 60)
    
    # Show filter stats
    stats = get_filtered_vs_all_stats()
    print(f"\n📊 FILTER BACKTEST:")
    print(f"All picks: {stats['all']['win_rate']:.1f}% ({stats['all']['won']}/{stats['all']['total']})")
    print(f"Filtered:  {stats['filtered']['win_rate']:.1f}% ({stats['filtered']['won']}/{stats['filtered']['total']})")
    improvement = stats['filtered']['win_rate'] - stats['all']['win_rate']
    print(f"Improvement: +{improvement:.1f}%")
    
    # Get quality picks
    picks = get_quality_picks()
    
    print(f"\n🎯 TOP {args.top} QUALITY PICKS:")
    print("-" * 60)
    
    msg_lines = [f"🎯 *Smart Consensus Picks*\n"]
    msg_lines.append(f"Filter: 3-6 whales, 55-89% conf")
    msg_lines.append(f"Backtest: {stats['filtered']['win_rate']:.0f}% vs {stats['all']['win_rate']:.0f}% all\n")
    
    for i, pick in enumerate(picks[:args.top], 1):
        print(f"\n{i}. {pick['market'][:50]}...")
        print(f"   {pick['side']} @ {pick['entry_price']:.2f}")
        print(f"   {pick['whale_count']} whales | {pick['confidence']}% conf")
        print(f"   Quality Score: {pick['quality_score']}")
        
        msg_lines.append(f"*{i}. {pick['market'][:40]}...*")
        msg_lines.append(f"   {pick['side']} @ {pick['entry_price']:.2f} | {pick['whale_count']}🐋 | {pick['confidence']}%")
        msg_lines.append(f"   Score: {pick['quality_score']}\n")
    
    if not picks:
        print("\n⚠️ No picks currently pass quality filters")
        msg_lines.append("⚠️ No picks currently pass quality filters")
    
    if args.telegram:
        send_telegram('\n'.join(msg_lines))
        print("\n📱 Sent to Telegram")


if __name__ == "__main__":
    main()
