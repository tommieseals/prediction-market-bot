"""
MiroFish Strategy Improvement System
=====================================
Uses swarm intelligence to analyze our trading performance
and suggest improvements. Runs 5x daily via heartbeat.

The swarm debates:
1. Why are our picks underperforming?
2. What patterns lead to wins vs losses?
3. What strategies should we try?
4. What research should we do on Twitter/Reddit?
"""

import sqlite3
import json
import os
import sys
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# MiroFish API
MIROFISH_BASE = "http://localhost:5001"
OLLAMA_URL = "http://localhost:11434"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "939543801")

def get_performance_data() -> Dict:
    """Get current performance stats from database."""
    conn = sqlite3.connect('data/whale_hunter.db')
    cur = conn.cursor()
    
    data = {
        'overall': {},
        'by_whale_count': [],
        'by_side': [],
        'by_confidence': [],
        'recent_losses': [],
        'recent_wins': [],
        'patterns': []
    }
    
    # Overall stats
    cur.execute('''SELECT outcome, COUNT(*) FROM consensus_picks GROUP BY outcome''')
    outcomes = dict(cur.fetchall())
    won = outcomes.get('won', 0)
    lost = outcomes.get('lost', 0)
    pending = outcomes.get('pending', 0)
    data['overall'] = {
        'won': won, 'lost': lost, 'pending': pending,
        'win_rate': won/(won+lost)*100 if (won+lost)>0 else 0,
        'total_resolved': won + lost
    }
    
    # By whale count
    cur.execute('''
        SELECT whale_count, 
               SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as w,
               SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as l
        FROM consensus_picks WHERE outcome IN ('won','lost')
        GROUP BY whale_count ORDER BY whale_count
    ''')
    for wc, w, l in cur.fetchall():
        wr = w/(w+l)*100 if (w+l)>0 else 0
        data['by_whale_count'].append({'whale_count': wc, 'won': w, 'lost': l, 'win_rate': wr})
    
    # By side
    cur.execute('''
        SELECT side,
               SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as w,
               SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as l
        FROM consensus_picks WHERE outcome IN ('won','lost')
        GROUP BY side
    ''')
    for side, w, l in cur.fetchall():
        wr = w/(w+l)*100 if (w+l)>0 else 0
        data['by_side'].append({'side': side, 'won': w, 'lost': l, 'win_rate': wr})
    
    # By confidence
    cur.execute('''
        SELECT 
            CASE 
                WHEN confidence >= 90 THEN '90+'
                WHEN confidence >= 80 THEN '80-90'
                WHEN confidence >= 70 THEN '70-80'
                WHEN confidence >= 60 THEN '60-70'
                ELSE '<60'
            END as bucket,
            SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as w,
            SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as l
        FROM consensus_picks WHERE outcome IN ('won','lost')
        GROUP BY bucket
    ''')
    for bucket, w, l in cur.fetchall():
        wr = w/(w+l)*100 if (w+l)>0 else 0
        data['by_confidence'].append({'confidence': bucket, 'won': w, 'lost': l, 'win_rate': wr})
    
    # Recent losses
    cur.execute('''SELECT market_title, side, confidence, whale_count, avg_entry_price, notes
                   FROM consensus_picks WHERE outcome='lost' ORDER BY resolved_at DESC LIMIT 10''')
    for r in cur.fetchall():
        data['recent_losses'].append({
            'market': r[0], 'side': r[1], 'confidence': r[2], 
            'whale_count': r[3], 'entry_price': r[4], 'notes': r[5]
        })
    
    # Recent wins
    cur.execute('''SELECT market_title, side, confidence, whale_count, avg_entry_price, notes
                   FROM consensus_picks WHERE outcome='won' ORDER BY resolved_at DESC LIMIT 10''')
    for r in cur.fetchall():
        data['recent_wins'].append({
            'market': r[0], 'side': r[1], 'confidence': r[2], 
            'whale_count': r[3], 'entry_price': r[4], 'notes': r[5]
        })
    
    conn.close()
    
    # Identify patterns
    data['patterns'] = identify_patterns(data)
    
    return data


def identify_patterns(data: Dict) -> List[str]:
    """Identify key patterns in the data."""
    patterns = []
    
    # Whale count patterns
    for wc in data['by_whale_count']:
        if wc['whale_count'] >= 7 and wc['win_rate'] < 40:
            patterns.append(f"HIGH WHALE COUNT PROBLEM: {wc['whale_count']} whales = only {wc['win_rate']:.0f}% win rate")
        if wc['whale_count'] <= 5 and wc['win_rate'] >= 60:
            patterns.append(f"SWEET SPOT: {wc['whale_count']} whales = {wc['win_rate']:.0f}% win rate")
    
    # Side patterns
    for s in data['by_side']:
        if s['win_rate'] < 50:
            patterns.append(f"WEAK SIDE: {s['side']} bets only {s['win_rate']:.0f}% win rate")
    
    # Confidence patterns
    for c in data['by_confidence']:
        if '90' in c['confidence'] and c['win_rate'] < 50:
            patterns.append(f"OVERCONFIDENCE TRAP: {c['confidence']}% confidence = only {c['win_rate']:.0f}% win rate")
        if '70' in c['confidence'] and c['win_rate'] >= 70:
            patterns.append(f"SWEET SPOT: {c['confidence']}% confidence = {c['win_rate']:.0f}% win rate")
    
    return patterns


def run_mirofish_analysis(data: Dict, question: str = None) -> Optional[str]:
    """Run MiroFish swarm analysis on our performance data."""
    
    if question is None:
        question = """
        Analyze our Polymarket whale-following trading strategy performance.
        
        Current win rate: {win_rate:.1f}%
        
        KEY OBSERVATIONS:
        - More whales agreeing = WORSE performance (7+ whales = 25-31% win rate)
        - High confidence (90%+) = only 47% win rate
        - Medium confidence (70-80%) = 71% win rate (better!)
        - YES bets (56%) outperform NO bets (45%)
        
        Recent losses: {losses}
        
        QUESTIONS FOR THE SWARM:
        1. Why does high whale agreement lead to losses? (Are they getting faded?)
        2. Should we FADE the consensus when 7+ whales agree?
        3. What market types should we avoid?
        4. What Twitter/Reddit research could help us find better edges?
        5. What specific strategy changes would improve win rate to 60%+?
        
        Be specific and actionable. Give concrete strategies to try.
        """.format(
            win_rate=data['overall']['win_rate'],
            losses=json.dumps([l['market'][:50] for l in data['recent_losses'][:5]])
        )
    
    # Try local Ollama first (faster)
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": "qwen3:4b",
                "prompt": f"You are an elite quantitative trading strategist analyzing whale-following performance data.\n\n{question}",
                "stream": False
            },
            timeout=120
        )
        if response.status_code == 200:
            return response.json().get('response', '')
    except Exception as e:
        print(f"Ollama failed: {e}")
    
    # Fallback to MiroFish API
    try:
        # Create a quick simulation
        response = requests.post(
            f"{MIROFISH_BASE}/api/predict",
            json={
                "question": question,
                "context": json.dumps(data),
                "num_agents": 20,
                "model": "qwen3:4b"
            },
            timeout=300
        )
        if response.status_code == 200:
            return response.json().get('prediction', '')
    except Exception as e:
        print(f"MiroFish failed: {e}")
    
    return None


def send_telegram_alert(message: str):
    """Send analysis results to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)
    except Exception as e:
        print(f"Telegram failed: {e}")


def save_analysis(analysis: str, data: Dict):
    """Save analysis to memory file for tracking."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    
    # Save to daily analysis file
    analysis_file = f"data/strategy_analysis_{timestamp}.md"
    with open(analysis_file, 'w') as f:
        f.write(f"# Strategy Analysis - {timestamp}\n\n")
        f.write(f"## Performance Data\n")
        f.write(f"- Win Rate: {data['overall']['win_rate']:.1f}%\n")
        f.write(f"- W/L/P: {data['overall']['won']}/{data['overall']['lost']}/{data['overall']['pending']}\n\n")
        f.write(f"## Patterns Identified\n")
        for p in data['patterns']:
            f.write(f"- {p}\n")
        f.write(f"\n## AI Analysis\n{analysis}\n")
    
    print(f"Saved analysis to {analysis_file}")
    
    # Append to insights log
    insights_file = "data/strategy_insights.jsonl"
    with open(insights_file, 'a') as f:
        f.write(json.dumps({
            'timestamp': timestamp,
            'win_rate': data['overall']['win_rate'],
            'patterns': data['patterns'],
            'analysis_summary': analysis[:500] if analysis else None
        }) + '\n')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='MiroFish Strategy Improver')
    parser.add_argument('--quick', action='store_true', help='Quick analysis without full swarm')
    parser.add_argument('--question', type=str, help='Custom question to ask')
    parser.add_argument('--telegram', action='store_true', help='Send results to Telegram')
    args = parser.parse_args()
    
    print("🐟 MiroFish Strategy Improver")
    print("=" * 50)
    
    # Get performance data
    print("\n📊 Loading performance data...")
    data = get_performance_data()
    
    print(f"\nCurrent Win Rate: {data['overall']['win_rate']:.1f}%")
    print(f"Resolved: {data['overall']['won']}W / {data['overall']['lost']}L")
    print(f"\nPatterns Found:")
    for p in data['patterns']:
        print(f"  • {p}")
    
    # Run analysis
    print("\n🧠 Running AI analysis...")
    analysis = run_mirofish_analysis(data, args.question)
    
    if analysis:
        print("\n" + "=" * 50)
        print("STRATEGY RECOMMENDATIONS:")
        print("=" * 50)
        print(analysis[:2000])  # Truncate for display
        
        # Save analysis
        save_analysis(analysis, data)
        
        # Send to Telegram if requested
        if args.telegram:
            msg = f"""🐟 *Strategy Analysis*

📊 Win Rate: {data['overall']['win_rate']:.1f}%

🔍 *Key Patterns:*
{chr(10).join(['• ' + p for p in data['patterns'][:3]])}

💡 *Recommendations:*
{analysis[:800]}

_Run at {datetime.now().strftime('%H:%M')}_"""
            send_telegram_alert(msg)
            print("\n📱 Sent to Telegram")
    else:
        print("\n❌ Analysis failed - check Ollama/MiroFish status")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
