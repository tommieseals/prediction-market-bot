"""
Market Scanner
==============
Scans for markets where elite whales are positioned.
Finds the best opportunities based on elite whale activity.
"""
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
import os
import requests

DB_PATH = 'data/whale_hunter.db'
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "939543801")


def categorize(title):
    """Categorize market."""
    if not title:
        return 'Other'
    t = title.lower()
    if any(x in t for x in ['tennis', 'open']):
        return 'Tennis'
    if 'spread' in t or 'o/u' in t:
        return 'Spreads'
    if any(x in t for x in ['iran', 'israel', 'ukraine']):
        return 'Geopolitics'
    if any(x in t for x in ['trump', 'biden', 'election']):
        return 'Politics'
    if any(x in t for x in ['nba', 'lakers', 'celtics']):
        return 'NBA'
    return 'Other'


def scan_elite_markets(conn):
    """Find markets where elite whales have positions."""
    cur = conn.cursor()
    
    # Get elite whale addresses
    cur.execute('SELECT address, name, tier FROM elite_whales')
    elites = {r[0]: {'name': r[1], 'tier': r[2]} for r in cur.fetchall()}
    
    if not elites:
        print("No elite whales found. Run elite_tracker.py first.")
        return []
    
    # Get pending positions from elite whales
    placeholders = ','.join(['?' for _ in elites])
    cur.execute(f'''
        SELECT p.market_title, p.side, p.entry_price, p.size_usd, 
               p.address, p.condition_id, p.end_date
        FROM whale_positions p
        WHERE p.address IN ({placeholders})
        AND (p.outcome IS NULL OR p.outcome = '' OR p.outcome = 'pending')
        ORDER BY p.detected_at DESC
    ''', list(elites.keys()))
    
    # Group by market
    markets = defaultdict(lambda: {
        'YES': {'whales': [], 'total_size': 0, 'avg_price': 0, 'prices': []},
        'NO': {'whales': [], 'total_size': 0, 'avg_price': 0, 'prices': []}
    })
    
    for market, side, price, size, addr, cond_id, end_date in cur.fetchall():
        whale = elites[addr]
        markets[market][side]['whales'].append({
            'name': whale['name'],
            'tier': whale['tier'],
            'size': size or 0
        })
        markets[market][side]['total_size'] += size or 0
        if price:
            markets[market][side]['prices'].append(price)
        markets[market]['condition_id'] = cond_id
        markets[market]['end_date'] = end_date
    
    # Calculate averages and scores
    results = []
    for market, data in markets.items():
        for side in ['YES', 'NO']:
            if not data[side]['whales']:
                continue
            
            prices = data[side]['prices']
            avg_price = sum(prices) / len(prices) if prices else 0
            
            legendary_count = len([w for w in data[side]['whales'] if w['tier'] == 'LEGENDARY'])
            elite_count = len([w for w in data[side]['whales'] if w['tier'] == 'ELITE'])
            total_whales = len(data[side]['whales'])
            
            # Score calculation
            score = 0
            score += legendary_count * 30
            score += elite_count * 20
            
            # Category bonus
            cat = categorize(market)
            if cat in ['Tennis', 'Spreads']:
                score += 15
            elif cat == 'Politics':
                score -= 10
            
            # Size bonus
            if data[side]['total_size'] >= 5000:
                score += 10
            elif data[side]['total_size'] >= 1000:
                score += 5
            
            results.append({
                'market': market,
                'side': side,
                'avg_price': avg_price,
                'total_size': data[side]['total_size'],
                'whale_count': total_whales,
                'legendary_count': legendary_count,
                'elite_count': elite_count,
                'whales': [w['name'] for w in data[side]['whales']],
                'category': cat,
                'score': score,
                'condition_id': data.get('condition_id'),
                'end_date': data.get('end_date')
            })
    
    # Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return results


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
    parser.add_argument('--top', type=int, default=15, help='Number of markets')
    parser.add_argument('--alert', action='store_true', help='Send to Telegram')
    args = parser.parse_args()
    
    conn = sqlite3.connect(DB_PATH)
    
    print('=' * 70)
    print('MARKET SCANNER - Elite Whale Positions')
    print('=' * 70)
    
    results = scan_elite_markets(conn)
    
    if not results:
        print("\nNo pending positions found from elite whales.")
        conn.close()
        return
    
    print(f'\nFound {len(results)} markets with elite whale positions')
    print()
    print(f'{"Score":<7} {"Side":<5} {"Whales":<10} {"Cat":<12} {"Price":<7} {"Market"}')
    print('-' * 70)
    
    for r in results[:args.top]:
        market_short = r['market'][:30] + '...' if len(r['market']) > 30 else r['market']
        whale_str = f"{r['whale_count']}({r['legendary_count']}L)"
        print(f"{r['score']:<7} {r['side']:<5} {whale_str:<10} {r['category']:<12} {r['avg_price']:.2f}    {market_short}")
    
    if args.alert and results:
        msg = "🎯 *ELITE MARKET SCAN*\n\n"
        for i, r in enumerate(results[:5], 1):
            msg += f"*{i}. {r['market'][:35]}...*\n"
            msg += f"   {r['side']} @ {r['avg_price']:.2f}\n"
            msg += f"   {r['whale_count']} whales ({r['legendary_count']} legendary)\n"
            msg += f"   Category: {r['category']}\n\n"
        send_alert(msg)
        print("\nSent to Telegram!")
    
    conn.close()


if __name__ == '__main__':
    main()
