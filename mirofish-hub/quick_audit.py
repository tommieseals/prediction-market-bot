import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print('=== CRITICAL DATA ISSUES ===')
print()

# 1. Expired but pending
cur.execute('''SELECT COUNT(*) FROM whale_positions 
    WHERE end_date < datetime('now') 
    AND (outcome = 'pending' OR outcome IS NULL)''')
expired_pending = cur.fetchone()[0]
print(f'EXPIRED BUT PENDING: {expired_pending}')

# 2. Price = 1.0 but pending (market resolved YES side won)
cur.execute('''SELECT COUNT(*) FROM whale_positions 
    WHERE current_price = 1.0 
    AND (outcome = 'pending' OR outcome IS NULL)''')
price_1_pending = cur.fetchone()[0]
print(f'PRICE=1.0 BUT PENDING: {price_1_pending} <-- DEFINITELY RESOLVED')

# 3. Price = 0.0 but pending (market resolved NO side won)
cur.execute('''SELECT COUNT(*) FROM whale_positions 
    WHERE current_price = 0.0 
    AND (outcome = 'pending' OR outcome IS NULL)''')
price_0_pending = cur.fetchone()[0]
print(f'PRICE=0.0 BUT PENDING: {price_0_pending}')

# 4. NULL end_date
cur.execute('SELECT COUNT(*) FROM whale_positions WHERE end_date IS NULL')
null_dates = cur.fetchone()[0]
print(f'NULL END_DATE: {null_dates}')

print()
print('=== OUTCOME DISTRIBUTION ===')
cur.execute('SELECT COALESCE(outcome, "NULL") as o, COUNT(*) as c FROM whale_positions GROUP BY outcome ORDER BY c DESC')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

print()
print('=== ROOT CAUSE ANALYSIS ===')

# Check if refresh_positions ever ran
cur.execute('SELECT COUNT(*) FROM whale_positions WHERE outcome = "won"')
won = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM whale_positions WHERE outcome = "lost"')
lost = cur.fetchone()[0]
print(f'Positions marked WON: {won}')
print(f'Positions marked LOST: {lost}')

if won == 0 and lost == 0:
    print()
    print('!!! NO POSITIONS HAVE EVER BEEN RESOLVED !!!')
    print('The refresh_positions() function is either:')
    print('  1. Never being called')
    print('  2. Not working correctly')
    print('  3. Not committing to database')

# Check current_price distribution for "pending" positions
print()
print('=== PRICE DISTRIBUTION FOR PENDING POSITIONS ===')
cur.execute('''
    SELECT 
        CASE 
            WHEN current_price = 1.0 THEN 'RESOLVED_YES'
            WHEN current_price = 0.0 THEN 'RESOLVED_NO'
            WHEN current_price > 0.9 THEN 'LIKELY_YES (>0.9)'
            WHEN current_price < 0.1 THEN 'LIKELY_NO (<0.1)'
            ELSE 'ACTIVE'
        END as status,
        COUNT(*) as cnt
    FROM whale_positions 
    WHERE outcome = 'pending' OR outcome IS NULL
    GROUP BY status
    ORDER BY cnt DESC
''')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

conn.close()

print()
print('=== RECOMMENDATION ===')
print('Need to run a position resolution sweep that:')
print('1. Checks Polymarket API for actual market outcomes')
print('2. Updates outcome field based on current_price (1.0=resolved YES, 0.0=resolved NO)')
print('3. Calculates actual_pnl for resolved positions')
