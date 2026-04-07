# -*- coding: utf-8 -*-
"""Fix data issues in the database"""
import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print('DATA FIXES')
print('=' * 50)

# 1. Remove stale pending positions (end_date > 2 days ago)
cur.execute("""
UPDATE whale_positions 
SET outcome = 'expired'
WHERE (outcome IS NULL OR outcome = 'pending')
AND end_date IS NOT NULL
AND end_date != ''
AND date(end_date) < date('now', '-2 days')
""")
stale_fixed = cur.rowcount
print(f'[1] Marked {stale_fixed} stale positions as expired')

# 2. Remove positions with epoch dates
cur.execute("""
DELETE FROM whale_positions 
WHERE end_date LIKE '1970%' OR end_date LIKE '1969%'
""")
epoch_fixed = cur.rowcount
print(f'[2] Deleted {epoch_fixed} positions with epoch dates')

# 3. Remove duplicate consensus picks (keep newest)
cur.execute("""
DELETE FROM consensus_picks
WHERE id NOT IN (
    SELECT MAX(id) FROM consensus_picks GROUP BY condition_id
)
""")
dupes_fixed = cur.rowcount
print(f'[3] Removed {dupes_fixed} duplicate picks')

# 4. Add /api/health endpoint to whale_api.py 
# (will do separately as code change)

# 5. Update signal_generated for positions that have signals
cur.execute("""
UPDATE whale_positions 
SET signal_generated = 1
WHERE condition_id IN (SELECT condition_id FROM trade_signals)
AND signal_generated = 0
""")
sig_fixed = cur.rowcount
print(f'[4] Updated signal_generated for {sig_fixed} positions')

conn.commit()

# Verify fixes
print('\n' + '=' * 50)
print('VERIFICATION')
print('=' * 50)

cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'expired'")
print(f'Expired positions: {cur.fetchone()[0]}')

cur.execute("SELECT COUNT(*) FROM whale_positions WHERE signal_generated = 1")
print(f'Signal generated: {cur.fetchone()[0]}')

cur.execute("SELECT COUNT(DISTINCT condition_id), COUNT(*) FROM consensus_picks")
row = cur.fetchone()
print(f'Unique picks: {row[0]}, Total: {row[1]}')

conn.close()
print('\nData fixes complete!')
