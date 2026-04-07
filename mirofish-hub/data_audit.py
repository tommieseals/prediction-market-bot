# -*- coding: utf-8 -*-
import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print('DATA QUALITY AUDIT')
print('=' * 50)

# Check for stale positions
cur.execute("""SELECT COUNT(*) FROM whale_positions 
               WHERE (outcome IS NULL OR outcome = 'pending')
               AND end_date < date('now', '-1 day')""")
stale = cur.fetchone()[0]
print(f'Stale pending positions: {stale}')

# Check for missing sides
cur.execute("SELECT COUNT(*) FROM whale_positions WHERE side IS NULL OR side = ''")
no_side = cur.fetchone()[0]
print(f'Positions missing side: {no_side}')

# Check for zero prices
cur.execute('SELECT COUNT(*) FROM whale_positions WHERE entry_price = 0 OR entry_price IS NULL')
no_price = cur.fetchone()[0]
print(f'Positions with zero/null price: {no_price}')

# Check consensus picks without end_date
cur.execute("SELECT COUNT(*) FROM consensus_picks WHERE end_date IS NULL OR end_date = ''")
no_end = cur.fetchone()[0]
print(f'Picks missing end_date: {no_end}')

# Check for duplicate whales
cur.execute("""SELECT address, COUNT(*) as cnt FROM tracked_whales 
               GROUP BY address HAVING cnt > 1""")
dup_whales = cur.fetchall()
print(f'Duplicate whale addresses: {len(dup_whales)}')

# Check signal generation status
cur.execute('SELECT COUNT(*) FROM whale_positions WHERE signal_generated = 1')
sig_yes = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM whale_positions WHERE signal_generated = 0')
sig_no = cur.fetchone()[0]
print(f'Signal generated: {sig_yes} yes, {sig_no} no')

# Check mirofish_results
cur.execute('SELECT COUNT(*) FROM mirofish_results')
mf = cur.fetchone()[0]
print(f'MiroFish results: {mf}')

# Check trade signals
cur.execute('SELECT COUNT(*) FROM trade_signals')
sigs = cur.fetchone()[0]
print(f'Trade signals: {sigs}')

# Check for positions with bad dates
cur.execute("SELECT COUNT(*) FROM whale_positions WHERE end_date LIKE '1970%' OR end_date LIKE '1969%'")
epoch = cur.fetchone()[0]
print(f'Positions with epoch dates: {epoch}')

# Check for negative sizes
cur.execute('SELECT COUNT(*) FROM whale_positions WHERE size < 0 OR size_usd < 0')
neg = cur.fetchone()[0]
print(f'Positions with negative size: {neg}')

# Liquidity check status
cur.execute("SELECT COUNT(*) FROM consensus_picks")
total = cur.fetchone()[0]
print(f'\nTotal consensus picks: {total}')

# Win/loss by category
print('\nWin rate by detection time:')
cur.execute("""
SELECT 
    CASE 
        WHEN hours_since_first_whale < 2 THEN '0-2h'
        WHEN hours_since_first_whale < 6 THEN '2-6h'
        WHEN hours_since_first_whale < 12 THEN '6-12h'
        ELSE '12h+'
    END as timing,
    COUNT(*) as total
FROM consensus_picks
GROUP BY timing
""")
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]} picks')

conn.close()
print('\nAudit complete.')
