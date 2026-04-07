import sqlite3
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Get non-sports whale plays with good alignment
cur.execute('''
SELECT market_title, side, COUNT(*) as whales, SUM(size_usd) as size, 
       GROUP_CONCAT(tw.display_name) as whale_list,
       MAX(tw.elite_score) as top_elite,
       end_date, condition_id
FROM whale_positions wp
JOIN tracked_whales tw ON wp.address = tw.address
WHERE wp.outcome = 'pending'
  AND tw.elite_score >= 65
  AND (market_title LIKE '%Trump%' OR market_title LIKE '%Bitcoin%' 
       OR market_title LIKE '%Iran%' OR market_title LIKE '%tariff%'
       OR market_title LIKE '%recession%' OR market_title LIKE '%Fed%'
       OR market_title LIKE '%Vance%' OR market_title LIKE '%election%')
GROUP BY market_title, side
HAVING whales >= 2
ORDER BY whales DESC
LIMIT 15
''')

print('=== POLITICAL/CRYPTO WHALE PLAYS ===\n')
for row in cur.fetchall():
    market, side, whales, size, whale_list, top_elite, end, cond = row
    print(f'{market[:60]}')
    print(f'  {side} | {whales} whales | Size: ${size or 0:,.0f} | Top Elite: {top_elite}')
    whales_short = ','.join(whale_list.split(',')[:3]) if whale_list else 'N/A'
    print(f'  Whales: {whales_short}')
    print(f'  Ends: {end}')
    print()

# Also check for any 100% consensus plays regardless of category
print('\n=== 100% CONSENSUS PLAYS (Any Category) ===\n')
cur.execute('''
WITH market_sides AS (
    SELECT market_title, condition_id, side, COUNT(*) as cnt, SUM(size_usd) as size,
           MAX(tw.elite_score) as top_elite, end_date
    FROM whale_positions wp
    JOIN tracked_whales tw ON wp.address = tw.address
    WHERE wp.outcome = 'pending' AND tw.elite_score >= 65
    GROUP BY market_title, side
)
SELECT m1.market_title, m1.side, m1.cnt as whales, m1.size, m1.top_elite, m1.end_date
FROM market_sides m1
LEFT JOIN market_sides m2 ON m1.market_title = m2.market_title AND m1.side != m2.side
WHERE m2.market_title IS NULL  -- No opposing side = 100% consensus
  AND m1.cnt >= 3
ORDER BY m1.cnt DESC, m1.size DESC
LIMIT 10
''')

for row in cur.fetchall():
    market, side, whales, size, top_elite, end = row
    print(f'{market[:60]}')
    print(f'  {side} | {whales} whales (100%) | ${size or 0:,.0f} | Elite {top_elite} | {end}')
    print()

conn.close()
