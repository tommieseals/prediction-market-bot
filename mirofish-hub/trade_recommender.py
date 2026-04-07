"""
Trade Recommender
=================
Combines all intelligence to recommend trades.
"""
import sqlite3
from datetime import datetime
import os
import requests

DB_PATH = 'data/whale_hunter.db'
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "939543801")


def get_recommendations(conn, max_results=5):
    """Generate trade recommendations."""
    cur = conn.cursor()
    
    recommendations = []
    
    # Get pending markets with elite whale positions
    cur.execute('''
        SELECT p.market_title, p.side, p.condition_id, p.entry_price,
               COUNT(DISTINCT p.address) as whale_count,
               SUM(CASE WHEN e.tier='LEGENDARY' THEN 1 ELSE 0 END) as legendary_count,
               SUM(CASE WHEN e.tier='ELITE' THEN 1 ELSE 0 END) as elite_count,
               AVG(p.size_usd) as avg_size
        FROM whale_positions p
        JOIN elite_whales e ON p.address = e.address
        WHERE p.outcome IS NULL OR p.outcome = ''
        GROUP BY p.market_title, p.side
        HAVING whale_count >= 1
        ORDER BY legendary_count DESC, elite_count DESC, whale_count DESC
    ''')
    
    dow = datetime.now().weekday()
    day_bonus = 10 if dow in [0, 1, 2] else -10  # Mon-Wed good
    
    for row in cur.fetchall():
        market, side, cond_id, price, whales, legendary, elite, avg_size = row
        
        # Calculate score
        score = 0
        reasons = []
        
        # Legendary whales
        if legendary > 0:
            score += legendary * 30
            reasons.append(f"{legendary} LEGENDARY whale(s)")
        
        # Elite whales
        if elite > 0:
            score += elite * 15
            reasons.append(f"{elite} ELITE whale(s)")
        
        # Whale count (sweet spot 3-5)
        if 3 <= whales <= 5:
            score += 15
        elif whales > 5:
            score -= 10
            reasons.append(f"⚠️ {whales} whales (crowded)")
        
        # Category bonus
        t = market.lower()
        if any(x in t for x in ['tennis', 'spread']):
            score += 15
            reasons.append("✅ Good category")
        elif 'politics' in t:
            score -= 20
            reasons.append("❌ Politics")
        
        # Day bonus
        score += day_bonus
        
        # Size bonus
        if avg_size and avg_size >= 1000:
            score += 5
        
        # Confidence from entry price
        conf = 1 - abs(0.5 - (price or 0.5)) * 2  # Higher when near 50%
        if 0.3 <= (price or 0.5) <= 0.7:
            score += 5
        
        recommendations.append({
            'market': market,
            'side': side,
            'price': price or 0,
            'whale_count': whales,
            'legendary': legendary,
            'elite': elite,
            'score': score,
            'reasons': reasons
        })
    
    # Sort and return top
    recommendations.sort(key=lambda x: x['score'], reverse=True)
    return recommendations[:max_results]


def format_recommendation(rec, rank):
    """Format a single recommendation."""
    market = rec['market'][:45] + '...' if len(rec['market']) > 45 else rec['market']
    
    output = f"\n*{rank}. {market}*\n"
    output += f"   📊 {rec['side']} @ ${rec['price']:.2f}\n"
    output += f"   🐋 {rec['whale_count']} whales ({rec['legendary']}L, {rec['elite']}E)\n"
    output += f"   ⭐ Score: {rec['score']}\n"
    
    if rec['reasons']:
        for r in rec['reasons'][:2]:
            output += f"   • {r}\n"
    
    return output


def send_alert(message):
    """Send to Telegram."""
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
    parser.add_argument('--top', type=int, default=5, help='Number of recommendations')
    parser.add_argument('--alert', action='store_true', help='Send to Telegram')
    args = parser.parse_args()
    
    conn = sqlite3.connect(DB_PATH)
    
    print('=' * 60)
    print('TRADE RECOMMENDER')
    print(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('=' * 60)
    
    recommendations = get_recommendations(conn, args.top)
    
    if not recommendations:
        print("\nNo recommendations available right now.")
        conn.close()
        return
    
    print(f'\nTop {len(recommendations)} Trade Opportunities:')
    print('-' * 60)
    
    msg = "🎯 *TRADE RECOMMENDATIONS*\n"
    
    for i, rec in enumerate(recommendations, 1):
        rec_text = format_recommendation(rec, i)
        print(rec_text)
        msg += rec_text
    
    if args.alert:
        send_alert(msg)
        print("\n📱 Sent to Telegram!")
    
    conn.close()


if __name__ == '__main__':
    main()
