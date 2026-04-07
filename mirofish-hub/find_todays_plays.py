import requests
import sqlite3

# Get active markets with liquidity
r = requests.get('https://gamma-api.polymarket.com/markets?closed=false&active=true&limit=500')
markets = r.json()

# Also check our whale DB for positions in liquid markets
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Get whale positions ending soon
cur.execute('''
SELECT DISTINCT market_title, condition_id, side, COUNT(*) as whale_count,
       SUM(size_usd) as total_size, end_date
FROM whale_positions wp
JOIN tracked_whales tw ON wp.address = tw.address
WHERE wp.outcome = 'pending'
  AND tw.elite_score >= 65
  AND wp.end_date IN ('2026-03-25', '2026-03-26')
GROUP BY market_title, side
HAVING whale_count >= 2
ORDER BY whale_count DESC, total_size DESC
LIMIT 20
''')

print("=== TODAY/TOMORROW WHALE PLAYS ===\n")
for row in cur.fetchall():
    market, cond, side, whales, size, end = row
    print(f"{market[:55]}")
    print(f"  {side} | {whales} whales | ${size or 0:,.0f} | Ends: {end}")
    
    # Check if this market is in Gamma API with liquidity
    for m in markets:
        if cond and cond[:20] in str(m.get('conditionId', '')):
            liq = m.get('liquidity', 0)
            if liq:
                print(f"  LIQUIDITY: ${float(liq):,.0f}")
            break
    print()

conn.close()

# Also show NBA games from Gamma API
print("\n=== NBA GAMES WITH LIQUIDITY ===\n")
for m in markets:
    q = m.get('question', '')
    liq = float(m.get('liquidity', 0) or 0)
    end = m.get('endDate', '')[:10]
    
    if ('vs.' in q or 'vs ' in q) and any(team in q for team in ['Celtics', 'Lakers', 'Warriors', 'Heat', 'Thunder', 'Cavaliers', 'Rockets', 'Pistons', 'Bulls', 'Knicks', 'Nets', 'Bucks', 'Nuggets', 'Suns', 'Clippers', 'Spurs', 'Mavericks', 'Hawks', 'Pacers', 'Magic', 'Hornets', 'Wizards', 'Grizzlies', 'Pelicans', 'Timberwolves', 'Raptors', '76ers', 'Trail Blazers', 'Kings', 'Jazz']):
        if liq > 500:
            print(f"{q[:55]}")
            print(f"  Ends: {end} | Liquidity: ${liq:,.0f}")
            print()
