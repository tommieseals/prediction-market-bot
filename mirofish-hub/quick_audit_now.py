# -*- coding: utf-8 -*-
"""Quick audit script for three-agent analysis - v2"""
import sqlite3
import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print('=' * 60)
print('THREE-AGENT AUDIT: GENERATOR PHASE')
print('=' * 60)

# Tables overview
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f'\nTABLES ({len(tables)}):')
for t in tables:
    cur.execute(f'SELECT COUNT(*) FROM {t}')
    count = cur.fetchone()[0]
    print(f'  {t}: {count:,} rows')

# Key metrics
print('\n' + '=' * 60)
print('KEY METRICS')
print('=' * 60)

# Whale positions
cur.execute("SELECT COUNT(*) FROM whale_positions")
total_pos = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'won'")
pos_won = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'lost'")
pos_lost = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'pending' OR outcome IS NULL")
pos_pending = cur.fetchone()[0]

print(f'\nWhale Positions: {total_pos:,}')
print(f'  Won: {pos_won:,}')
print(f'  Lost: {pos_lost:,}')
print(f'  Pending: {pos_pending:,}')
if pos_won + pos_lost > 0:
    print(f'  Win Rate: {100*pos_won/(pos_won+pos_lost):.1f}%')

# Consensus picks
cur.execute("SELECT COUNT(*) FROM consensus_picks")
total_picks = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM consensus_picks WHERE won = 1")
picks_won = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM consensus_picks WHERE won = 0 AND outcome != 'pending'")
picks_lost = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM consensus_picks WHERE outcome = 'pending' OR outcome IS NULL")
picks_pending = cur.fetchone()[0]

print(f'\nConsensus Picks: {total_picks}')
print(f'  Won: {picks_won}')
print(f'  Lost: {picks_lost}')
print(f'  Pending: {picks_pending}')
if picks_won + picks_lost > 0:
    print(f'  Win Rate: {100*picks_won/(picks_won+picks_lost):.1f}%')

# MiroFish results
cur.execute("SELECT COUNT(*) FROM mirofish_results")
mirofish_count = cur.fetchone()[0]
print(f'\nMiroFish Validated: {mirofish_count} of {total_picks} picks ({100*mirofish_count/max(total_picks,1):.1f}%)')

# Trade signals
cur.execute("SELECT COUNT(*) FROM trade_signals")
signals = cur.fetchone()[0]
print(f'\nTrade Signals: {signals}')

# My trades
cur.execute("SELECT COUNT(*) FROM my_trades")
my_trades = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM our_trades")
our_trades = cur.fetchone()[0]
print(f'\nMy Trades: {my_trades}')
print(f'Our Trades: {our_trades}')

# Recent activity
print('\n' + '=' * 60)
print('RECENT PICKS (Last 5)')
print('=' * 60)

cur.execute("""
SELECT market_title, side, avg_entry_price, whale_count, outcome, created_at 
FROM consensus_picks 
ORDER BY created_at DESC 
LIMIT 5
""")
recent = cur.fetchall()
for r in recent:
    status = '[W]' if r[4] == 'won' else '[L]' if r[4] == 'lost' else '[P]'
    title = r[0][:35] if r[0] else 'Unknown'
    price = r[2] if r[2] else 0
    print(f'  {status} {title}... | {r[1]} @ {price:.2f} | {r[3]} whales')

# ISSUES
print('\n' + '=' * 60)
print('POTENTIAL ISSUES')
print('=' * 60)

# Stale pending positions (end_date in past)
cur.execute("""
SELECT COUNT(*) FROM whale_positions 
WHERE (outcome = 'pending' OR outcome IS NULL)
AND end_date IS NOT NULL 
AND end_date != ''
AND date(end_date) < date('now', '-1 day')
""")
stale = cur.fetchone()[0]
print(f'\n[!] Stale positions (past end_date but still pending): {stale:,}')

# Missing end_dates
cur.execute("SELECT COUNT(*) FROM whale_positions WHERE end_date IS NULL OR end_date = ''")
no_date = cur.fetchone()[0]
print(f'[!] Positions missing end_date: {no_date:,}')

# Duplicate condition_ids in picks
cur.execute("""
SELECT condition_id, COUNT(*) as cnt 
FROM consensus_picks 
GROUP BY condition_id 
HAVING cnt > 1
""")
dupes = cur.fetchall()
print(f'[!] Duplicate picks (same condition_id): {len(dupes)}')

# Signals without corresponding picks
cur.execute("""
SELECT COUNT(*) FROM trade_signals 
WHERE condition_id NOT IN (SELECT condition_id FROM consensus_picks)
""")
orphan_signals = cur.fetchone()[0]
print(f'[!] Orphan signals (no matching pick): {orphan_signals}')

# Positions without valid whale
cur.execute("""
SELECT COUNT(*) FROM whale_positions 
WHERE address NOT IN (SELECT address FROM tracked_whales)
""")
orphan_pos = cur.fetchone()[0]
print(f'[!] Orphan positions (whale not in tracked_whales): {orphan_pos:,}')

# Validation rate issue
if mirofish_count < total_picks * 0.1:
    print(f'\n[CRITICAL] Only {100*mirofish_count/max(total_picks,1):.1f}% of picks MiroFish validated!')
    print('   The three-agent pipeline is not running properly!')

# Check signal_generated field
cur.execute("SELECT COUNT(*) FROM whale_positions WHERE signal_generated = 1")
sig_gen = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM whale_positions WHERE signal_generated = 0")
sig_not = cur.fetchone()[0]
print(f'\n[i] Signal Generated: {sig_gen:,} yes / {sig_not:,} no')

# Check tracked whales stats
print('\n' + '=' * 60)
print('TOP WHALES BY POSITION COUNT')
print('=' * 60)

cur.execute("""
SELECT tw.name, tw.address, COUNT(wp.id) as pos_count,
       SUM(CASE WHEN wp.outcome = 'won' THEN 1 ELSE 0 END) as wins,
       SUM(CASE WHEN wp.outcome = 'lost' THEN 1 ELSE 0 END) as losses
FROM tracked_whales tw
LEFT JOIN whale_positions wp ON tw.address = wp.address
GROUP BY tw.address
ORDER BY pos_count DESC
LIMIT 10
""")
top_whales = cur.fetchall()
for w in top_whales:
    name = w[0] or w[1][:10]
    wr = 100*w[3]/(w[3]+w[4]) if (w[3]+w[4]) > 0 else 0
    print(f'  {name}: {w[2]} positions | {w[3]}W/{w[4]}L ({wr:.0f}%)')

conn.close()

print('\n' + '=' * 60)
print('GENERATOR COMPLETE - Ready for EVALUATOR')
print('=' * 60)
