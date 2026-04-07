import sqlite3
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

output = []

output.append('=== TOP 10 WHALES BY ELITE SCORE ===')
cur.execute('''
    SELECT display_name, elite_score, pnl, bayesian_win_rate
    FROM tracked_whales
    ORDER BY elite_score DESC
    LIMIT 10
''')
for row in cur.fetchall():
    name, score, pnl, wr = row
    pnl = pnl or 0
    wr = wr or 0
    score = score or 0
    output.append(f'{name}: Elite={score:.0f} | PnL=${pnl:,.0f} | WR={wr:.1%}')

output.append('')
output.append('=== PENDING POSITIONS BY CATEGORY ===')
cur.execute('''
    SELECT 
        CASE 
            WHEN market_title LIKE '%vs.%' OR market_title LIKE '% vs %' THEN 'Sports'
            WHEN market_title LIKE '%Trump%' OR market_title LIKE '%Biden%' OR market_title LIKE '%election%' THEN 'Politics'
            WHEN market_title LIKE '%Bitcoin%' OR market_title LIKE '%ETH%' OR market_title LIKE '%crypto%' THEN 'Crypto'
            ELSE 'Other'
        END as category,
        COUNT(*)
    FROM whale_positions
    WHERE outcome = 'pending'
    GROUP BY category
''')
for cat, count in cur.fetchall():
    output.append(f'{cat}: {count}')

output.append('')
output.append('=== RECENT RESOLVED (Last 15) ===')
cur.execute('''
    SELECT market_title, side, outcome, actual_pnl, resolved_at
    FROM whale_positions
    WHERE outcome IN ('won', 'lost')
    ORDER BY resolved_at DESC
    LIMIT 15
''')
for row in cur.fetchall():
    title, side, outcome, pnl, resolved = row
    emoji = 'WIN' if outcome == 'won' else 'LOSS'
    pnl = pnl or 0
    output.append(f'{emoji} | {side} | ${pnl:,.0f} | {title[:50]}')

output.append('')
output.append('=== POSITIONS WITH MISSING end_date ===')
cur.execute('''
    SELECT COUNT(*) FROM whale_positions 
    WHERE outcome = 'pending' AND end_date IS NULL
''')
missing = cur.fetchone()[0]
output.append(f'Missing end_date: {missing} positions')

cur.execute('''
    SELECT COUNT(*) FROM whale_positions 
    WHERE outcome = 'pending' AND end_date IS NOT NULL
''')
has_date = cur.fetchone()[0]
output.append(f'Has end_date: {has_date} positions')

conn.close()

# Write to file
with open(r'C:\Users\User\Desktop\where-we-are-now\CURRENT_DATA.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print('Wrote CURRENT_DATA.txt')
