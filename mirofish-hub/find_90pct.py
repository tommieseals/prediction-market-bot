#!/usr/bin/env python3
"""Find 90%+ confidence picks from whale consensus - WITH EXPIRATION FILTERING"""

import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

conn = sqlite3.connect('data/whale_hunter.db')
c = conn.cursor()

# Get current time
now = datetime.now(timezone.utc)

# Get all pending positions from elite whales WITH end_date
c.execute('''
    SELECT w.display_name, w.elite_score, p.market_title, p.side, p.entry_price, p.token_id, p.end_date
    FROM whale_positions p
    JOIN tracked_whales w ON p.address = w.address
    WHERE p.outcome = 'pending'
    AND w.elite_score >= 60
    AND p.entry_price IS NOT NULL
    ORDER BY p.detected_at DESC
''')

# Group by market+side
picks = defaultdict(list)
for row in c.fetchall():
    whale, score, market, side, price, token, end_date = row
    key = (market, side)
    picks[key].append({
        'whale': whale,
        'score': score,
        'price': price,
        'token': token,
        'end_date': end_date
    })

def parse_end_date(end_date_str):
    """Parse end_date string to datetime"""
    if not end_date_str:
        return None
    try:
        # Try ISO format
        if 'T' in end_date_str:
            dt = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        else:
            dt = datetime.strptime(end_date_str, '%Y-%m-%d %H:%M:%S')
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def format_time_remaining(end_dt):
    """Format time remaining as human readable string"""
    if not end_dt:
        return "Unknown", "gray", 999999
    
    delta = end_dt - now
    total_minutes = delta.total_seconds() / 60
    
    if total_minutes < 0:
        return "EXPIRED", "red", -1
    elif total_minutes < 30:
        return f"{int(total_minutes)}m left - TOO LATE", "red", total_minutes
    elif total_minutes < 120:
        hours = int(total_minutes // 60)
        mins = int(total_minutes % 60)
        return f"{hours}h {mins}m left - WARNING", "yellow", total_minutes
    else:
        hours = int(total_minutes // 60)
        mins = int(total_minutes % 60)
        return f"{hours}h {mins}m left", "green", total_minutes
    
def format_expiry_time(end_dt):
    """Format expiry time as readable date/time"""
    if not end_dt:
        return "Unknown"
    # Convert to local time (CST/CDT)
    local_dt = end_dt.astimezone()
    return local_dt.strftime("%b %d, %I:%M %p")

print("=" * 70)
print("  HIGH CONFIDENCE PICKS (70%+ implied) - WITH EXPIRATION TIMES")
print("=" * 70)
print()
print("  Legend: [GREEN] Safe (>2h) | [YELLOW] Warning (<2h) | [RED] Too Late")
print()

results = []
for (market, side), whales in picks.items():
    if len(whales) >= 2:
        avg_price = sum(w['price'] for w in whales) / len(whales)
        
        # Get end_date from first whale with it
        end_date_str = None
        for w in whales:
            if w['end_date']:
                end_date_str = w['end_date']
                break
        
        end_dt = parse_end_date(end_date_str)
        time_remaining, status, minutes_left = format_time_remaining(end_dt)
        expiry_str = format_expiry_time(end_dt)
        
        # Skip expired markets
        if minutes_left < 0:
            continue
        
        # Skip markets expiring in < 30 minutes
        if minutes_left < 30 and minutes_left >= 0:
            continue
        
        if side == 'NO':
            implied_win = (1 - avg_price) * 100
        else:
            implied_win = avg_price * 100
        
        if implied_win >= 70:
            results.append({
                'market': market,
                'side': side,
                'price': avg_price,
                'implied': implied_win,
                'whales': whales,
                'count': len(whales),
                'end_dt': end_dt,
                'time_remaining': time_remaining,
                'expiry_str': expiry_str,
                'status': status,
                'minutes_left': minutes_left
            })

# Sort by expiration time (soonest first), then by implied win rate
results.sort(key=lambda x: (x['minutes_left'] if x['minutes_left'] > 0 else 999999, -x['implied']))

# Color codes for terminal
COLORS = {
    'green': '\033[92m',
    'yellow': '\033[93m',
    'red': '\033[91m',
    'gray': '\033[90m',
    'reset': '\033[0m'
}

for i, r in enumerate(results[:15], 1):
    whale_names = [w['whale'][:15] for w in r['whales'][:3]]
    color = COLORS.get(r['status'], '')
    reset = COLORS['reset']
    
    status_label = ""
    if r['status'] == 'yellow':
        status_label = " [WARNING]"
    elif r['status'] == 'green':
        status_label = " [SAFE]"
    
    print(f"{i}. {r['market'][:60]}")
    print(f"   Side: {r['side']} @ ${r['price']:.2f} = {r['implied']:.0f}% implied win")
    print(f"   {color}EXPIRES: {r['expiry_str']} ({r['time_remaining']}){status_label}{reset}")
    print(f"   Whales ({r['count']}): {', '.join(whale_names)}")
    print(f"   Token: {r['whales'][0]['token']}")
    print()

if not results:
    print("No valid picks found (all may be expired or expiring too soon)")
