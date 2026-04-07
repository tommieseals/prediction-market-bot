import sqlite3
import requests
from datetime import datetime, timedelta

conn = sqlite3.connect('data/whale_hunter.db')

print('='*60)
print('AUDIT: Whale Tracker -> Site Data Flow')
print('='*60)

# 1. Check most recent positions in DB
print('\n[1] MOST RECENT POSITIONS IN DATABASE:')
recent = conn.execute('''
    SELECT detected_at, market_title, side, size_usd, address
    FROM whale_positions
    WHERE detected_at IS NOT NULL
    ORDER BY detected_at DESC
    LIMIT 5
''').fetchall()

for r in recent:
    det, title, side, size, addr = r
    print(f"  {det[:16]} | {side} ${size:,.0f} | {title[:40]}")

latest_db_time = recent[0][0] if recent else 'N/A'
print(f"\n  Latest detection: {latest_db_time}")

# 2. Check consensus API
print('\n[2] CONSENSUS API CHECK:')
try:
    resp = requests.get('http://localhost:8081/api/consensus', timeout=10)
    data = resp.json()
    picks = data.get('picks', [])
    summary = data.get('summary', {})
    generated = summary.get('generated_at', 'N/A')
    
    print(f"  API Status: OK")
    print(f"  Total picks: {len(picks)}")
    print(f"  Generated at: {generated}")
    print(f"  GREEN: {summary.get('green', 0)} | YELLOW: {summary.get('yellow', 0)} | RED: {summary.get('red', 0)}")
except Exception as e:
    print(f"  API Error: {e}")

# 3. Check whale leaderboard API
print('\n[3] LEADERBOARD API CHECK:')
try:
    resp = requests.get('http://localhost:8081/api/leaderboard', timeout=10)
    data = resp.json()
    whales = data.get('whales', data) if isinstance(data, dict) else data
    print(f"  API Status: OK")
    print(f"  Whales returned: {len(whales) if isinstance(whales, list) else 'N/A'}")
except Exception as e:
    print(f"  API Error: {e}")

# 4. Check live positions API
print('\n[4] LIVE POSITIONS API CHECK:')
try:
    resp = requests.get('http://localhost:8081/api/positions/live', timeout=10)
    data = resp.json()
    positions = data.get('positions', data) if isinstance(data, dict) else data
    print(f"  API Status: OK")
    print(f"  Live positions returned: {len(positions) if isinstance(positions, list) else 'N/A'}")
    if isinstance(positions, list) and len(positions) > 0:
        p = positions[0]
        print(f"  Sample: {p.get('market_title', 'N/A')[:40]}")
except Exception as e:
    print(f"  API Error: {e}")

# 5. Database stats
print('\n[5] DATABASE STATS:')
stats = conn.execute('''
    SELECT 
        (SELECT COUNT(*) FROM whale_positions WHERE outcome = 'pending') as pending,
        (SELECT COUNT(*) FROM whale_positions WHERE outcome = 'won') as won,
        (SELECT COUNT(*) FROM whale_positions WHERE outcome = 'lost') as lost,
        (SELECT COUNT(*) FROM tracked_whales) as whales,
        (SELECT COUNT(*) FROM whale_positions WHERE detected_at >= datetime('now', '-24 hours')) as last_24h
''').fetchone()

print(f"  Pending positions: {stats[0]:,}")
print(f"  Won: {stats[1]:,} | Lost: {stats[2]:,}")
print(f"  Tracked whales: {stats[3]}")
print(f"  Positions detected last 24h: {stats[4]}")

# 6. Verify specific recent position appears in API
print('\n[6] DATA FLOW VERIFICATION:')
if recent:
    test_market = recent[0][1]  # most recent market title
    # Check if it's in consensus picks
    found_in_api = False
    for p in picks:
        if test_market in p.get('market_title', ''):
            found_in_api = True
            break
    
    if found_in_api:
        print(f"  PASS: Recent DB entry '{test_market[:35]}...' found in API")
    else:
        print(f"  INFO: Recent entry '{test_market[:35]}...' not in consensus (may be filtered)")
        print(f"        (Consensus only shows multi-whale picks)")

print('\n' + '='*60)
print('AUDIT COMPLETE')
print('='*60)

conn.close()
