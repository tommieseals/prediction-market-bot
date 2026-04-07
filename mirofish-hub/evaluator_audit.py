"""
EVALUATOR: Audit the strategy improvement system
"""
import sqlite3

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print('=' * 60)
print('EVALUATOR: Auditing Strategy Improvement System')
print('=' * 60)

# Check 1: Whale count win rates - is the pattern real?
print('\nCHECK 1: Whale count pattern verification')
print('-' * 40)
cur.execute('''
    SELECT whale_count, 
           SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as w,
           SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as l
    FROM consensus_picks WHERE outcome IN ('won','lost')
    GROUP BY whale_count ORDER BY whale_count
''')
low_whale_w, low_whale_l = 0, 0
high_whale_w, high_whale_l = 0, 0

for wc, w, l in cur.fetchall():
    total = w + l
    wr = w/total*100 if total > 0 else 0
    sig = 'OK' if total >= 5 else 'LOW'
    print(f'  {wc} whales: {w}W/{l}L = {wr:.1f}% (n={total}) [{sig}]')
    if wc <= 5:
        low_whale_w += w
        low_whale_l += l
    else:
        high_whale_w += w
        high_whale_l += l

print()
low_total = low_whale_w + low_whale_l
high_total = high_whale_w + high_whale_l
low_wr = low_whale_w/low_total*100 if low_total > 0 else 0
high_wr = high_whale_w/high_total*100 if high_total > 0 else 0
print(f'  3-5 whales combined: {low_whale_w}W/{low_whale_l}L = {low_wr:.1f}% (n={low_total})')
print(f'  6+ whales combined:  {high_whale_w}W/{high_whale_l}L = {high_wr:.1f}% (n={high_total})')
pattern_real = low_wr > high_wr + 10
print(f'  PATTERN REAL? {pattern_real} (diff: {low_wr - high_wr:.1f}%)')

# Check 2: Filter backtest
print('\nCHECK 2: Filter backtest verification')
print('-' * 40)
cur.execute('''
    SELECT COUNT(*), SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END)
    FROM consensus_picks 
    WHERE outcome IN ('won','lost')
    AND whale_count >= 3 AND whale_count <= 6
    AND confidence >= 55 AND confidence <= 89
''')
filtered = cur.fetchone()
cur.execute('''
    SELECT COUNT(*), SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END)
    FROM consensus_picks WHERE outcome IN ('won','lost')
''')
all_picks = cur.fetchone()

all_wr = all_picks[1]/all_picks[0]*100 if all_picks[0] > 0 else 0
filt_wr = filtered[1]/filtered[0]*100 if filtered[0] > 0 else 0

print(f'  All picks: {all_picks[1]}/{all_picks[0]} = {all_wr:.1f}%')
print(f'  Filtered:  {filtered[1]}/{filtered[0]} = {filt_wr:.1f}%')
print(f'  Improvement: +{filt_wr - all_wr:.1f}%')
print(f'  Sample size: {filtered[0]} trades')
stat_sig = filtered[0] >= 30
print(f'  STATISTICALLY SIGNIFICANT? {stat_sig}')
if not stat_sig:
    print(f'  WARNING: Need {30 - filtered[0]} more trades to validate')

# Check 3: Confidence analysis
print('\nCHECK 3: Confidence bracket analysis')
print('-' * 40)
cur.execute('''
    SELECT 
        CASE 
            WHEN confidence >= 90 THEN '90+'
            WHEN confidence >= 70 THEN '70-89'
            ELSE '<70'
        END as bucket,
        SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as w,
        SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as l
    FROM consensus_picks WHERE outcome IN ('won','lost')
    GROUP BY bucket
''')
for bucket, w, l in cur.fetchall():
    total = w + l
    wr = w/total*100 if total > 0 else 0
    print(f'  {bucket}%: {w}W/{l}L = {wr:.1f}% (n={total})')

# Check 4: YES vs NO
print('\nCHECK 4: Side analysis')
print('-' * 40)
cur.execute('''
    SELECT side,
           SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as w,
           SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as l
    FROM consensus_picks WHERE outcome IN ('won','lost')
    GROUP BY side
''')
for side, w, l in cur.fetchall():
    total = w + l
    wr = w/total*100 if total > 0 else 0
    print(f'  {side}: {w}W/{l}L = {wr:.1f}% (n={total})')

conn.close()

print()
print('=' * 60)
print('EVALUATOR VERDICT')
print('=' * 60)
print()
issues = []
if not pattern_real:
    issues.append('Whale count pattern NOT confirmed')
if not stat_sig:
    issues.append(f'Filter sample too small ({filtered[0]}/30 needed)')
if filt_wr - all_wr < 3:
    issues.append('Filter improvement marginal (<3%)')

if issues:
    print('ISSUES FOUND:')
    for i in issues:
        print(f'  - {i}')
    print()
    print('RECOMMENDATION: NEEDS_REVISION')
    print('  - Continue tracking but DO NOT trust filter yet')
    print('  - Need 30+ filtered trades to validate')
    print('  - Pattern is promising but unproven')
else:
    print('ALL CHECKS PASSED')
    print('RECOMMENDATION: APPROVED for use')
