"""
Whale Alert System
==================
Monitors for high-value whale moves and alerts when:
1. Top follow-score whale makes a new bet
2. Multiple elite whales pile into same market
3. Hot hand whale (streak 10+) makes a move
4. Category specialist bets in their specialty
"""
import sqlite3
from datetime import datetime, timedelta
import json
import os
import requests

DB_PATH = 'data/whale_hunter.db'
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "939543801")

# Alert thresholds
MIN_FOLLOW_SCORE = 75
MIN_STREAK = 10
MIN_ELITE_SCORE = 70
MIN_WHALE_CONSENSUS = 3

def get_top_whales(conn):
    """Get whales we should alert on."""
    cur = conn.cursor()
    
    # Get from profiles
    cur.execute('''
        SELECT address, name, follow_score, profile_json 
        FROM whale_profiles 
        WHERE follow_score >= ?
        ORDER BY follow_score DESC
    ''', (MIN_FOLLOW_SCORE,))
    
    return {
        r[0]: {
            'name': r[1],
            'follow_score': r[2],
            'profile': json.loads(r[3]) if r[3] else {}
        }
        for r in cur.fetchall()
    }


def get_recent_positions(conn, hours=1):
    """Get positions from the last N hours."""
    cur = conn.cursor()
    
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    
    cur.execute('''
        SELECT p.address, p.market_title, p.side, p.size_usd, p.entry_price,
               p.detected_at, w.display_name, w.elite_score
        FROM whale_positions p
        JOIN tracked_whales w ON p.address = w.address
        WHERE p.detected_at >= ?
        ORDER BY p.detected_at DESC
    ''', (since,))
    
    return cur.fetchall()


def check_whale_consensus(conn, market_title):
    """Check how many elite whales are in a market."""
    cur = conn.cursor()
    
    cur.execute('''
        SELECT COUNT(DISTINCT p.address) as whale_count,
               GROUP_CONCAT(w.display_name) as names,
               p.side
        FROM whale_positions p
        JOIN tracked_whales w ON p.address = w.address
        WHERE p.market_title = ?
        AND w.elite_score >= ?
        GROUP BY p.side
    ''', (market_title, MIN_ELITE_SCORE))
    
    return cur.fetchall()


def get_hot_hands(conn, min_streak=10):
    """Get whales currently on hot streaks."""
    cur = conn.cursor()
    
    cur.execute('SELECT DISTINCT address FROM whale_positions')
    addresses = [r[0] for r in cur.fetchall()]
    
    hot = {}
    for addr in addresses:
        cur.execute('''
            SELECT outcome FROM whale_positions 
            WHERE address = ? AND outcome IN ('won', 'lost')
            ORDER BY detected_at DESC
        ''', (addr,))
        outcomes = [r[0] for r in cur.fetchall()]
        
        if outcomes:
            streak = 0
            for o in outcomes:
                if o == 'won':
                    streak += 1
                else:
                    break
            
            if streak >= min_streak:
                cur.execute('SELECT display_name FROM tracked_whales WHERE address = ?', (addr,))
                name = cur.fetchone()
                hot[addr] = {
                    'name': name[0] if name else addr[:12],
                    'streak': streak
                }
    
    return hot


def send_alert(message):
    """Send alert to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)
        return response.ok
    except Exception as e:
        print(f"Alert failed: {e}")
        return False


def format_whale_alert(whale_name, market, side, size, entry_price, reason, extra=""):
    """Format a whale alert message."""
    return f"""🐋 *WHALE ALERT*

*{whale_name}*
{reason}

📊 *Market:* {market[:60]}
📈 *Side:* {side} @ ${entry_price:.2f}
💰 *Size:* ${size:,.0f}
{extra}
_Detected: {datetime.now().strftime('%H:%M CDT')}_"""


def check_for_alerts(conn):
    """Check for alert conditions and send notifications."""
    alerts_sent = 0
    
    # Get tracking data
    top_whales = get_top_whales(conn)
    hot_hands = get_hot_hands(conn)
    recent = get_recent_positions(conn, hours=1)
    
    # Track markets we've already alerted on
    alerted_markets = set()
    
    for pos in recent:
        addr, market, side, size, entry_price, detected, name, elite = pos
        
        if market in alerted_markets:
            continue
        
        alert_reasons = []
        extra_info = []
        
        # Check 1: Top follow-score whale
        if addr in top_whales:
            whale_data = top_whales[addr]
            alert_reasons.append(f"🌟 Follow Score: {whale_data['follow_score']:.0f}")
        
        # Check 2: Hot hand whale
        if addr in hot_hands:
            streak = hot_hands[addr]['streak']
            alert_reasons.append(f"🔥 Win Streak: {streak}")
        
        # Check 3: Elite score
        if elite and elite >= MIN_ELITE_SCORE:
            alert_reasons.append(f"⭐ Elite Score: {elite:.0f}")
        
        # Check 4: Whale consensus
        consensus = check_whale_consensus(conn, market)
        for row in consensus:
            if row[0] >= MIN_WHALE_CONSENSUS:
                alert_reasons.append(f"🐋 {row[0]} Elite Whales on {row[2]}")
                extra_info.append(f"Whales: {row[1][:50]}...")
        
        # Send alert if any conditions met
        if alert_reasons:
            reason = " | ".join(alert_reasons)
            extra = "\n".join(extra_info)
            msg = format_whale_alert(name or addr[:12], market, side, 
                                    size or 0, entry_price or 0, reason, extra)
            if send_alert(msg):
                alerts_sent += 1
                alerted_markets.add(market)
                print(f"Alert sent: {name} on {market[:40]}...")
    
    return alerts_sent


def generate_summary_report(conn):
    """Generate daily summary report."""
    cur = conn.cursor()
    
    # Get stats
    cur.execute('SELECT COUNT(*) FROM whale_profiles WHERE follow_score >= 75')
    top_count = cur.fetchone()[0]
    
    cur.execute('''
        SELECT COUNT(DISTINCT address) FROM whale_positions 
        WHERE detected_at >= datetime('now', '-24 hours')
    ''')
    active_24h = cur.fetchone()[0]
    
    # Get hot hands
    hot = get_hot_hands(conn, min_streak=5)
    
    report = f"""📊 *WHALE INTELLIGENCE DAILY SUMMARY*
_{datetime.now().strftime('%Y-%m-%d %H:%M CDT')}_

**Top Performers:**
• {top_count} whales with Follow Score 75+
• {len(hot)} whales on 5+ win streaks
• {active_24h} active in last 24h

**Hot Hands (10+ streak):**
"""
    
    hot_10 = [h for h in hot.values() if h['streak'] >= 10]
    for h in sorted(hot_10, key=lambda x: x['streak'], reverse=True)[:5]:
        report += f"• {h['name']}: {h['streak']} wins\n"
    
    # Category insights
    cur.execute('''
        SELECT 
            CASE 
                WHEN LOWER(market_title) LIKE '%spread%' THEN 'Spreads'
                WHEN LOWER(market_title) LIKE '%iran%' OR LOWER(market_title) LIKE '%israel%' THEN 'Geopolitics'
                WHEN LOWER(market_title) LIKE '%crypto%' OR LOWER(market_title) LIKE '%bitcoin%' THEN 'Crypto'
                ELSE 'Other'
            END as cat,
            COUNT(*) as bets,
            SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as won
        FROM whale_positions
        WHERE outcome IN ('won', 'lost')
        AND detected_at >= datetime('now', '-7 days')
        GROUP BY cat
        HAVING bets >= 10
    ''')
    
    report += "\n**7-Day Category Performance:**\n"
    for row in cur.fetchall():
        cat, bets, won = row
        wr = won/bets*100 if bets > 0 else 0
        report += f"• {cat}: {wr:.0f}% ({won}/{bets})\n"
    
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--scan', action='store_true', help='Scan for alerts')
    parser.add_argument('--summary', action='store_true', help='Send daily summary')
    parser.add_argument('--test', action='store_true', help='Test alert system')
    args = parser.parse_args()
    
    conn = sqlite3.connect(DB_PATH)
    
    if args.test:
        print("Testing alert system...")
        if send_alert("🧪 *TEST* - Whale Alert System Online"):
            print("Test alert sent successfully!")
        else:
            print("Test alert failed!")
    
    elif args.scan:
        print("Scanning for whale alerts...")
        alerts = check_for_alerts(conn)
        print(f"Sent {alerts} alerts")
    
    elif args.summary:
        print("Generating summary report...")
        report = generate_summary_report(conn)
        print(report)
        send_alert(report)
        print("Summary sent!")
    
    else:
        # Default: show status
        top = get_top_whales(conn)
        hot = get_hot_hands(conn)
        print(f"Whale Alert System Status")
        print(f"  Top whales (75+ score): {len(top)}")
        print(f"  Hot hands (10+ streak): {len([h for h in hot.values() if h['streak'] >= 10])}")
    
    conn.close()


if __name__ == '__main__':
    main()
