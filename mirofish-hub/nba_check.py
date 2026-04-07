import sqlite3
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# NBA games
cur.execute('''
SELECT market_title, side, COUNT(*) as whales, SUM(size_usd) as size,
       MAX(tw.elite_score) as top_elite, end_date
FROM whale_positions wp
JOIN tracked_whales tw ON wp.address = tw.address
WHERE wp.outcome = 'pending'
  AND tw.elite_score >= 60
  AND (market_title LIKE '%Celtics%' OR market_title LIKE '%Thunder%' 
       OR market_title LIKE '%Heat%' OR market_title LIKE '%Cavaliers%'
       OR market_title LIKE '%Warriors%' OR market_title LIKE '%Rockets%'
       OR market_title LIKE '%Timberwolves%' OR market_title LIKE '%Jazz%'
       OR market_title LIKE '%O/U%' OR market_title LIKE '%Spread%')
GROUP BY market_title, side
HAVING whales >= 1
ORDER BY end_date, whales DESC
LIMIT 20
''')

print('=== NBA WHALE PLAYS ===\n')
for row in cur.fetchall():
    market, side, whales, size, elite, end = row
    print(f"{market[:50]}")
    print(f"  {side} | {whales} whale(s) | ${size or 0:,.0f} | Elite {elite} | {end}")
    print()

conn.close()
