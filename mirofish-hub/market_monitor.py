"""
Market Monitor - Runs continuously, alerts on new sports markets and whale moves
"""
import requests
import json
import sqlite3
import time
import os
from datetime import datetime

# Telegram alert config
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '939543801')

def send_alert(message):
    """Send Telegram alert"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}, timeout=10)
        print(f"[ALERT SENT] {message[:50]}...")
    except Exception as e:
        print(f"[ALERT FAILED] {e}")

def get_open_markets():
    """Fetch all open markets"""
    url = 'https://gamma-api.polymarket.com/markets?_limit=500&active=true&closed=false'
    try:
        r = requests.get(url, timeout=30)
        return r.json()
    except:
        return []

def is_sports_market(question):
    """Check if market is sports-related"""
    q = question.lower()
    sports_keywords = [
        'vs.', 'vs ', ' v ', 'spread', 'o/u', 'over/under', 'winner',
        'nba', 'nfl', 'mlb', 'nhl', 'ufc', 'boxing', 'tennis', 'golf',
        'lakers', 'celtics', 'yankees', 'dodgers', 'chiefs', 'cowboys',
        'warriors', 'bulls', 'heat', 'nets', 'knicks', 'clippers',
        'game', 'match', 'championship', 'playoffs', 'finals',
        'formula 1', 'f1', 'grand prix', 'premier league', 'la liga',
        'bundesliga', 'serie a', 'champions league', 'world cup'
    ]
    return any(kw in q for kw in sports_keywords)

def scan_for_opportunities():
    """Main scan function"""
    markets = get_open_markets()
    
    sports = []
    high_volume = []
    
    for m in markets:
        q = m.get('question', '')
        vol = m.get('volumeNum', 0)
        cid = m.get('conditionId', '')
        
        prices_raw = m.get('outcomePrices', '[]')
        if isinstance(prices_raw, str):
            prices = json.loads(prices_raw)
        else:
            prices = prices_raw
        
        yes_price = float(prices[0]) if prices else 0
        
        if is_sports_market(q):
            sports.append({
                'question': q,
                'yes': yes_price,
                'volume': vol,
                'condition_id': cid
            })
        
        if vol > 100000:
            high_volume.append({
                'question': q,
                'yes': yes_price,
                'volume': vol
            })
    
    return sports, high_volume

def load_seen_markets():
    """Load previously seen market IDs"""
    try:
        with open('data/seen_markets.json', 'r') as f:
            return set(json.load(f))
    except:
        return set()

def save_seen_markets(seen):
    """Save seen market IDs"""
    with open('data/seen_markets.json', 'w') as f:
        json.dump(list(seen), f)

def main():
    print(f"=== MARKET MONITOR STARTED ===")
    print(f"Time: {datetime.now()}")
    print(f"Checking every 5 minutes for new opportunities\n")
    
    seen = load_seen_markets()
    
    while True:
        try:
            sports, high_vol = scan_for_opportunities()
            
            # Check for NEW sports markets
            for s in sports:
                if s['condition_id'] not in seen:
                    seen.add(s['condition_id'])
                    alert = f"🏈 NEW SPORTS MARKET!\n\n{s['question']}\n\nYES: ${s['yes']:.2f}\nVolume: ${s['volume']:,.0f}"
                    send_alert(alert)
            
            save_seen_markets(seen)
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Scanned. {len(sports)} sports markets, {len(high_vol)} high volume.")
            
        except Exception as e:
            print(f"[ERROR] {e}")
        
        time.sleep(300)  # 5 minutes

if __name__ == '__main__':
    # One-time scan mode
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        sports, high_vol = scan_for_opportunities()
        print(f"Found {len(sports)} sports markets:")
        for s in sports:
            print(f"  - {s['question'][:60]} (YES: ${s['yes']:.2f})")
        print(f"\nFound {len(high_vol)} high-volume markets (>$100K)")
    else:
        main()
