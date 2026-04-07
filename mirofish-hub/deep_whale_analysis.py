"""
Deep Whale Intelligence Analysis
================================
Analyzing ALL collected data to find edges
"""
import sqlite3
from collections import defaultdict
from datetime import datetime
import json

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print('=' * 70)
print('DEEP WHALE INTELLIGENCE ANALYSIS')
print('=' * 70)

# First, what data do we have?
print('\n📊 DATA INVENTORY')
print('-' * 50)
cur.execute('SELECT COUNT(*) FROM tracked_whales')
print(f'Tracked whales: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM whale_positions')
print(f'Whale positions: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM consensus_picks')
print(f'Consensus picks: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM trade_signals')
print(f'Trade signals: {cur.fetchone()[0]}')

# Check whale_positions structure
cur.execute('PRAGMA table_info(whale_positions)')
cols = [r[1] for r in cur.fetchall()]
print(f'\nWhale positions columns: {cols}')

# Get sample position
cur.execute('SELECT * FROM whale_positions LIMIT 1')
sample = cur.fetchone()
if sample:
    print(f'Sample position: {sample[:5]}...')

# 1. DAY OF WEEK ANALYSIS
print('\n' + '=' * 70)
print('1. DAY OF WEEK ANALYSIS')
print('=' * 70)

cur.execute('''
    SELECT 
        strftime('%w', created_at) as dow,
        COUNT(*) as total,
        SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as won,
        SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as lost
    FROM consensus_picks 
    WHERE outcome IN ('won', 'lost')
    GROUP BY dow
    ORDER BY dow
''')
days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
print(f'\n{"Day":<10} {"Won":<6} {"Lost":<6} {"Win%":<8} {"Sample":<8} {"Verdict"}')
print('-' * 55)
for row in cur.fetchall():
    dow, total, won, lost = row
    if dow is None:
        continue
    day_name = days[int(dow)]
    wr = won/(won+lost)*100 if (won+lost) > 0 else 0
    verdict = 'GOOD' if wr >= 55 else 'BAD' if wr < 45 else 'MEH'
    print(f'{day_name:<10} {won:<6} {lost:<6} {wr:<8.1f} {total:<8} {verdict}')

# 2. HOUR OF DAY ANALYSIS  
print('\n' + '=' * 70)
print('2. HOUR OF DAY ANALYSIS')
print('=' * 70)

cur.execute('''
    SELECT 
        strftime('%H', created_at) as hour,
        COUNT(*) as total,
        SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as won,
        SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as lost
    FROM consensus_picks 
    WHERE outcome IN ('won', 'lost')
    GROUP BY hour
    ORDER BY hour
''')
print(f'\n{"Hour":<10} {"Won":<6} {"Lost":<6} {"Win%":<8} {"Sample":<8} {"Verdict"}')
print('-' * 55)
for row in cur.fetchall():
    hour, total, won, lost = row
    if hour is None:
        continue
    wr = won/(won+lost)*100 if (won+lost) > 0 else 0
    verdict = 'BEST' if wr >= 70 else 'GOOD' if wr >= 55 else 'BAD' if wr < 45 else 'MEH'
    print(f'{hour}:00      {won:<6} {lost:<6} {wr:<8.1f} {total:<8} {verdict}')

# 3. MARKET CATEGORY ANALYSIS
print('\n' + '=' * 70)
print('3. MARKET CATEGORY ANALYSIS')
print('=' * 70)

# Extract category from market title
cur.execute('''
    SELECT market_title, outcome FROM consensus_picks 
    WHERE outcome IN ('won', 'lost')
''')
categories = defaultdict(lambda: {'won': 0, 'lost': 0})
for title, outcome in cur.fetchall():
    title_lower = title.lower() if title else ''
    
    # Detect category
    if any(x in title_lower for x in ['lakers', 'celtics', 'warriors', 'nba', 'basketball', 'bucks', 'pistons', 'bulls']):
        cat = 'NBA'
    elif any(x in title_lower for x in ['open', 'tennis', 'vs.', 'atp', 'wta']):
        if 'open' in title_lower or 'tennis' in title_lower:
            cat = 'Tennis'
        else:
            cat = 'Sports-Other'
    elif any(x in title_lower for x in ['trump', 'biden', 'election', 'president', 'congress', 'senate']):
        cat = 'Politics'
    elif any(x in title_lower for x in ['iran', 'israel', 'ukraine', 'russia', 'war', 'military']):
        cat = 'Geopolitics'
    elif any(x in title_lower for x in ['mlb', 'baseball', 'yankees', 'dodgers', 'mets', 'sox', 'pirates', 'rays', 'cardinals']):
        cat = 'MLB'
    elif any(x in title_lower for x in ['spread', 'o/u', 'over/under']):
        cat = 'Spreads/OU'
    elif any(x in title_lower for x in ['counter-strike', 'esports', 'gaming', 'league of legends', 'dota']):
        cat = 'Esports'
    elif any(x in title_lower for x in ['crypto', 'bitcoin', 'ethereum', 'btc', 'eth']):
        cat = 'Crypto'
    else:
        cat = 'Other'
    
    if outcome == 'won':
        categories[cat]['won'] += 1
    else:
        categories[cat]['lost'] += 1

print(f'\n{"Category":<15} {"Won":<6} {"Lost":<6} {"Win%":<8} {"Sample":<8} {"Verdict"}')
print('-' * 60)
sorted_cats = sorted(categories.items(), key=lambda x: x[1]['won']+x[1]['lost'], reverse=True)
for cat, data in sorted_cats:
    won, lost = data['won'], data['lost']
    total = won + lost
    wr = won/total*100 if total > 0 else 0
    verdict = 'GOOD' if wr >= 55 else 'AVOID' if wr < 45 else 'MEH'
    print(f'{cat:<15} {won:<6} {lost:<6} {wr:<8.1f} {total:<8} {verdict}')

# 4. TOP WHALE ANALYSIS
print('\n' + '=' * 70)
print('4. TOP WHALE PROFILING')
print('=' * 70)

cur.execute('''
    SELECT 
        w.name,
        w.elite_score,
        w.total_pnl,
        COUNT(p.id) as positions,
        w.address
    FROM tracked_whales w
    LEFT JOIN whale_positions p ON w.address = p.whale_address
    GROUP BY w.address
    ORDER BY w.total_pnl DESC
    LIMIT 15
''')
print(f'\n{"Whale":<20} {"Elite":<7} {"PnL":<12} {"Positions":<10}')
print('-' * 55)
for row in cur.fetchall():
    name, elite, pnl, positions, addr = row
    name_short = (name or addr[:10])[:18]
    pnl_str = f'${pnl:,.0f}' if pnl else '$0'
    print(f'{name_short:<20} {elite or 0:<7} {pnl_str:<12} {positions:<10}')

# 5. WHALE SPECIALTY DETECTION (who bets on what)
print('\n' + '=' * 70)
print('5. WHALE SPECIALIZATION DETECTION')
print('=' * 70)

cur.execute('''
    SELECT 
        w.name,
        w.address,
        p.market_title
    FROM tracked_whales w
    JOIN whale_positions p ON w.address = p.whale_address
    ORDER BY w.name
''')
whale_markets = defaultdict(list)
for name, addr, market in cur.fetchall():
    key = name or addr[:10]
    whale_markets[key].append(market or '')

print('\nLooking for specialists (whales who focus on specific markets)...\n')
specialists = []
for whale, markets in whale_markets.items():
    if len(markets) < 3:
        continue
    
    # Count keywords
    keywords = defaultdict(int)
    for m in markets:
        m_lower = m.lower()
        if 'wizards' in m_lower: keywords['Wizards'] += 1
        if 'lakers' in m_lower: keywords['Lakers'] += 1
        if 'celtics' in m_lower: keywords['Celtics'] += 1
        if 'trump' in m_lower: keywords['Trump'] += 1
        if 'iran' in m_lower: keywords['Iran'] += 1
        if 'tennis' in m_lower or 'open' in m_lower: keywords['Tennis'] += 1
        if 'crypto' in m_lower or 'bitcoin' in m_lower: keywords['Crypto'] += 1
        if 'mlb' in m_lower or 'baseball' in m_lower: keywords['MLB'] += 1
    
    # Check for concentration
    for kw, count in keywords.items():
        pct = count / len(markets) * 100
        if pct >= 30 and count >= 3:  # 30%+ focused on one thing
            specialists.append({
                'whale': whale,
                'specialty': kw,
                'concentration': pct,
                'count': count,
                'total_bets': len(markets)
            })

if specialists:
    print(f'{"Whale":<20} {"Specialty":<12} {"Focus%":<8} {"Bets":<6}')
    print('-' * 50)
    for s in sorted(specialists, key=lambda x: x['concentration'], reverse=True)[:10]:
        print(f"{s['whale'][:18]:<20} {s['specialty']:<12} {s['concentration']:<8.0f} {s['count']}/{s['total_bets']}")
else:
    print('No strong specialists detected (need more data)')

# 6. HOT STREAK ANALYSIS
print('\n' + '=' * 70)
print('6. STREAK & CONSISTENCY ANALYSIS')  
print('=' * 70)

# Check if we have outcome data per whale
cur.execute('''
    SELECT w.name, w.brier_score, w.total_pnl, w.elite_score
    FROM tracked_whales w
    WHERE w.elite_score > 0
    ORDER BY w.elite_score DESC
    LIMIT 10
''')
print('\nTop Elite Scorers (skill indicator):')
print(f'{"Whale":<20} {"Brier":<8} {"PnL":<12} {"Elite":<6}')
print('-' * 50)
for row in cur.fetchall():
    name, brier, pnl, elite = row
    name_short = (name or 'Unknown')[:18]
    brier_str = f'{brier:.3f}' if brier else 'N/A'
    pnl_str = f'${pnl:,.0f}' if pnl else '$0'
    print(f'{name_short:<20} {brier_str:<8} {pnl_str:<12} {elite:<6}')

# 7. SUSPICIOUS PATTERN DETECTION
print('\n' + '=' * 70)
print('7. SUSPICIOUS PATTERN DETECTION')
print('=' * 70)

# Look for whales with very high concentration or weird patterns
cur.execute('''
    SELECT 
        w.name,
        w.address,
        w.total_pnl,
        w.brier_score,
        COUNT(DISTINCT p.market_title) as unique_markets,
        COUNT(p.id) as total_positions
    FROM tracked_whales w
    JOIN whale_positions p ON w.address = p.whale_address
    GROUP BY w.address
    HAVING total_positions >= 5
    ORDER BY (total_positions * 1.0 / unique_markets) DESC
''')
print('\nWhales with repetitive betting (same markets):')
print(f'{"Whale":<20} {"Positions":<10} {"Unique":<8} {"Ratio":<8} {"PnL":<12}')
print('-' * 65)
for row in cur.fetchall():
    name, addr, pnl, brier, unique, total = row
    name_short = (name or addr[:10])[:18]
    ratio = total / unique if unique > 0 else 0
    pnl_str = f'${pnl:,.0f}' if pnl else '$0'
    if ratio >= 1.5:  # Betting same markets multiple times
        print(f'{name_short:<20} {total:<10} {unique:<8} {ratio:<8.1f} {pnl_str:<12}')

conn.close()

print('\n' + '=' * 70)
print('ANALYSIS COMPLETE')
print('=' * 70)
