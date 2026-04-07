"""
Deep Whale Intelligence Analysis v2
===================================
Using correct schema
"""
import sqlite3
from collections import defaultdict
import json

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print('=' * 70)
print('DEEP WHALE INTELLIGENCE ANALYSIS')
print('=' * 70)

# Data inventory
print('\n📊 DATA INVENTORY')
print('-' * 50)
cur.execute('SELECT COUNT(*) FROM tracked_whales')
print(f'Tracked whales: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM whale_positions')
print(f'Whale positions (bets): {cur.fetchone()[0]}')
cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome IS NOT NULL AND outcome != ''")
print(f'Resolved positions: {cur.fetchone()[0]}')

# 1. DAY OF WEEK ANALYSIS (from consensus_picks which has outcomes)
print('\n' + '=' * 70)
print('1. DAY OF WEEK ANALYSIS (Consensus Picks)')
print('=' * 70)

cur.execute('''
    SELECT 
        strftime('%w', created_at) as dow,
        SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as won,
        SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as lost
    FROM consensus_picks 
    WHERE outcome IN ('won', 'lost')
    GROUP BY dow
    ORDER BY dow
''')
days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
print(f'\n{"Day":<10} {"Won":<6} {"Lost":<6} {"Win%":<8} {"Verdict"}')
print('-' * 45)
for row in cur.fetchall():
    dow, won, lost = row
    if dow is None: continue
    total = won + lost
    wr = won/total*100 if total > 0 else 0
    verdict = 'GOOD' if wr >= 55 else 'AVOID' if wr < 45 else 'MEH'
    print(f'{days[int(dow)]:<10} {won:<6} {lost:<6} {wr:<8.1f} {verdict}')

# 2. HOUR ANALYSIS
print('\n' + '=' * 70)
print('2. HOUR OF DAY ANALYSIS')
print('=' * 70)

cur.execute('''
    SELECT 
        strftime('%H', created_at) as hour,
        SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as won,
        SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as lost
    FROM consensus_picks 
    WHERE outcome IN ('won', 'lost')
    GROUP BY hour
    HAVING (won + lost) >= 3
    ORDER BY (won * 1.0 / (won + lost)) DESC
''')
print(f'\n{"Hour":<10} {"Won":<6} {"Lost":<6} {"Win%":<8} {"Sample":<8} {"Verdict"}')
print('-' * 50)
for row in cur.fetchall():
    hour, won, lost = row
    if hour is None: continue
    total = won + lost
    wr = won/total*100 if total > 0 else 0
    verdict = 'BEST' if wr >= 65 else 'GOOD' if wr >= 55 else 'AVOID' if wr < 45 else 'MEH'
    print(f'{hour}:00      {won:<6} {lost:<6} {wr:<8.1f} {total:<8} {verdict}')

# 3. MARKET CATEGORY ANALYSIS
print('\n' + '=' * 70)
print('3. MARKET CATEGORY ANALYSIS')
print('=' * 70)

cur.execute('SELECT market_title, outcome FROM consensus_picks WHERE outcome IN ("won", "lost")')
categories = defaultdict(lambda: {'won': 0, 'lost': 0})
for title, outcome in cur.fetchall():
    t = (title or '').lower()
    if any(x in t for x in ['nba', 'lakers', 'celtics', 'warriors', 'bucks', 'pistons', 'bulls', 'mavericks', 'knicks']):
        cat = 'NBA'
    elif any(x in t for x in ['mlb', 'yankees', 'dodgers', 'mets', 'sox', 'pirates', 'rays', 'cardinals', 'brewers']):
        cat = 'MLB'
    elif any(x in t for x in ['open', 'atp', 'wta']) and 'tennis' not in t:
        cat = 'Tennis'
    elif any(x in t for x in ['spread', 'o/u', 'over/under']):
        cat = 'Spreads'
    elif any(x in t for x in ['trump', 'biden', 'congress', 'senate', 'election']):
        cat = 'Politics'
    elif any(x in t for x in ['iran', 'israel', 'ukraine', 'russia', 'military', 'war']):
        cat = 'Geopolitics'
    elif any(x in t for x in ['counter-strike', 'esports', 'gaming', 'dota', 'league']):
        cat = 'Esports'
    else:
        cat = 'Other'
    categories[cat]['won' if outcome == 'won' else 'lost'] += 1

print(f'\n{"Category":<15} {"Won":<6} {"Lost":<6} {"Win%":<8} {"Sample":<8} {"Verdict"}')
print('-' * 55)
for cat, d in sorted(categories.items(), key=lambda x: x[1]['won']+x[1]['lost'], reverse=True):
    total = d['won'] + d['lost']
    wr = d['won']/total*100 if total > 0 else 0
    verdict = 'GOOD' if wr >= 55 else 'AVOID' if wr < 45 else 'MEH'
    print(f'{cat:<15} {d["won"]:<6} {d["lost"]:<6} {wr:<8.1f} {total:<8} {verdict}')

# 4. TOP WHALE PROFILING
print('\n' + '=' * 70)
print('4. TOP WHALE PROFILING (by Elite Score)')
print('=' * 70)

cur.execute('''
    SELECT display_name, elite_score, pnl, num_trades, win_rate_raw, 
           brier_score, insider_flags, categories, tracked_accuracy
    FROM tracked_whales
    WHERE elite_score > 0
    ORDER BY elite_score DESC
    LIMIT 15
''')
print(f'\n{"Whale":<20} {"Elite":<7} {"PnL":<12} {"Trades":<8} {"WinRate":<8} {"Insider"}')
print('-' * 70)
for row in cur.fetchall():
    name, elite, pnl, trades, wr, brier, flags, cats, acc = row
    name_short = (name or 'Unknown')[:18]
    pnl_str = f'${pnl:,.0f}' if pnl else '$0'
    wr_str = f'{wr*100:.0f}%' if wr else 'N/A'
    flag_str = flags[:15] if flags else '-'
    print(f'{name_short:<20} {elite:<7.0f} {pnl_str:<12} {trades or 0:<8} {wr_str:<8} {flag_str}')

# 5. INSIDER/SUSPICIOUS WHALES
print('\n' + '=' * 70)
print('5. INSIDER FLAGS ANALYSIS')
print('=' * 70)

cur.execute('''
    SELECT display_name, insider_flags, insider_score, pnl, elite_score, categories
    FROM tracked_whales
    WHERE insider_flags IS NOT NULL AND insider_flags != '' AND insider_flags != '[]'
    ORDER BY insider_score DESC
    LIMIT 15
''')
print(f'\n{"Whale":<18} {"Score":<7} {"PnL":<12} {"Flags"}')
print('-' * 70)
for row in cur.fetchall():
    name, flags, score, pnl, elite, cats = row
    name_short = (name or 'Unknown')[:16]
    pnl_str = f'${pnl:,.0f}' if pnl else '$0'
    print(f'{name_short:<18} {score or 0:<7.0f} {pnl_str:<12} {flags[:40] if flags else "-"}')

# 6. WHALE SPECIALIZATION (who bets on what categories)
print('\n' + '=' * 70)
print('6. WHALE SPECIALISTS (Category Focus)')
print('=' * 70)

cur.execute('''
    SELECT display_name, categories, pnl, elite_score, num_trades
    FROM tracked_whales
    WHERE categories IS NOT NULL AND categories != ''
    ORDER BY pnl DESC
    LIMIT 20
''')
print(f'\n{"Whale":<20} {"Categories":<35} {"PnL":<12}')
print('-' * 70)
for row in cur.fetchall():
    name, cats, pnl, elite, trades = row
    name_short = (name or 'Unknown')[:18]
    cats_short = cats[:33] if cats else '-'
    pnl_str = f'${pnl:,.0f}' if pnl else '$0'
    print(f'{name_short:<20} {cats_short:<35} {pnl_str:<12}')

# 7. SKILL VS LUCK ANALYSIS (Brier Score distribution)
print('\n' + '=' * 70)
print('7. SKILL VS LUCK (Brier Score Analysis)')
print('=' * 70)

cur.execute('''
    SELECT 
        CASE 
            WHEN brier_score < 0.15 THEN 'Elite (<0.15)'
            WHEN brier_score < 0.20 THEN 'Good (0.15-0.20)'
            WHEN brier_score < 0.25 THEN 'Average (0.20-0.25)'
            ELSE 'Below Avg (>0.25)'
        END as tier,
        COUNT(*) as count,
        AVG(pnl) as avg_pnl,
        AVG(elite_score) as avg_elite
    FROM tracked_whales
    WHERE brier_score IS NOT NULL AND brier_score > 0
    GROUP BY tier
    ORDER BY tier
''')
print(f'\n{"Brier Tier":<20} {"Count":<8} {"Avg PnL":<15} {"Avg Elite"}')
print('-' * 55)
for row in cur.fetchall():
    tier, count, avg_pnl, avg_elite = row
    pnl_str = f'${avg_pnl:,.0f}' if avg_pnl else '$0'
    print(f'{tier:<20} {count:<8} {pnl_str:<15} {avg_elite or 0:.1f}')

# 8. POSITION SIZE ANALYSIS
print('\n' + '=' * 70)
print('8. POSITION SIZE VS OUTCOME')
print('=' * 70)

cur.execute('''
    SELECT 
        CASE 
            WHEN size_usd < 100 THEN 'Small (<$100)'
            WHEN size_usd < 500 THEN 'Medium ($100-500)'
            WHEN size_usd < 2000 THEN 'Large ($500-2K)'
            ELSE 'Whale ($2K+)'
        END as size_tier,
        COUNT(*) as total,
        SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) as won,
        SUM(CASE WHEN outcome = 'lost' THEN 1 ELSE 0 END) as lost
    FROM whale_positions
    WHERE outcome IN ('won', 'lost')
    GROUP BY size_tier
''')
print(f'\n{"Size Tier":<18} {"Total":<8} {"Won":<8} {"Lost":<8} {"Win%"}')
print('-' * 50)
for row in cur.fetchall():
    tier, total, won, lost = row
    resolved = won + lost
    wr = won/resolved*100 if resolved > 0 else 0
    print(f'{tier:<18} {total:<8} {won:<8} {lost:<8} {wr:.1f}%')

conn.close()

print('\n' + '=' * 70)
print('ANALYSIS COMPLETE - READY FOR EVALUATOR')
print('=' * 70)
