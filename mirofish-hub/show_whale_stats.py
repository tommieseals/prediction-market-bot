import sqlite3
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Overall whale performance
print('='*60)
print('WHALE TRACKER OVERALL PERFORMANCE')
print('='*60)

cur.execute("""
    SELECT outcome, COUNT(*), SUM(COALESCE(actual_pnl, 0))
    FROM whale_positions
    WHERE outcome IN ('won', 'lost')
    GROUP BY outcome
""")
for row in cur.fetchall():
    outcome, count, pnl = row
    pnl = pnl or 0
    emoji = 'WIN' if outcome == 'won' else 'LOSS'
    print(f'{emoji}: {count} positions | P&L: ${pnl:,.2f}')

# Win rate
cur.execute("""
    SELECT 
        SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        COUNT(*)
    FROM whale_positions
    WHERE outcome IN ('won', 'lost')
""")
row = cur.fetchone()
print(f'\nWin Rate: {row[0]:.1f}% ({row[1]} resolved)')

# Pending
cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'pending'")
print(f'Pending: {cur.fetchone()[0]}')

# Recent big winners
print('')
print('='*60)
print('RECENT BIG WINNERS (>$100)')
print('='*60)
cur.execute("""
    SELECT market_title, side, actual_pnl, resolved_at
    FROM whale_positions
    WHERE outcome = 'won' AND actual_pnl > 100
    ORDER BY resolved_at DESC LIMIT 10
""")
for row in cur.fetchall():
    title, side, pnl, resolved = row
    print(f'+${pnl:,.0f} | {side} | {title[:50]}')

# Consensus picks tracker
print('')
print('='*60)
print('CONSENSUS PICKS TRACKING')
print('='*60)
cur.execute("SELECT COUNT(*) FROM consensus_picks")
total = cur.fetchone()[0]
print(f'Total consensus picks tracked: {total}')

if total > 0:
    cur.execute("""
        SELECT outcome, COUNT(*) 
        FROM consensus_picks 
        GROUP BY outcome
    """)
    for outcome, count in cur.fetchall():
        print(f'  {outcome}: {count}')

conn.close()
