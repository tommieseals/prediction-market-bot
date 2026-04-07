"""
Category Analyzer
=================
Properly categorize consensus picks and analyze win rates by category.
"""
import sqlite3
import re
from collections import defaultdict

DB_PATH = 'data/whale_hunter.db'

def categorize_market(title):
    """Categorize a market title."""
    if not title:
        return 'Unknown'
    
    t = title.lower()
    
    # Sports - NBA
    nba_teams = ['lakers', 'celtics', 'warriors', 'bucks', 'bulls', 'knicks', 
                 'nets', 'heat', 'suns', 'nuggets', 'mavericks', 'clippers',
                 'rockets', 'spurs', 'sixers', '76ers', 'raptors', 'jazz',
                 'pistons', 'pacers', 'hawks', 'hornets', 'magic', 'wizards',
                 'cavaliers', 'cavs', 'thunder', 'blazers', 'kings', 'pelicans',
                 'grizzlies', 'timberwolves', 'wolves']
    if any(team in t for team in nba_teams) or 'nba' in t:
        if 'spread' in t or 'o/u' in t or 'over/under' in t:
            return 'NBA-Spreads'
        return 'NBA'
    
    # Sports - MLB
    mlb_teams = ['yankees', 'dodgers', 'mets', 'red sox', 'white sox', 'cubs',
                 'cardinals', 'braves', 'astros', 'phillies', 'padres', 'mariners',
                 'rays', 'guardians', 'rangers', 'orioles', 'twins', 'brewers',
                 'pirates', 'reds', 'royals', 'tigers', 'athletics', 'angels',
                 'rockies', 'marlins', 'nationals', 'diamondbacks', 'giants']
    if any(team in t for team in mlb_teams) or 'mlb' in t or 'baseball' in t:
        return 'MLB'
    
    # Sports - Tennis
    if 'open' in t or 'tennis' in t or 'atp' in t or 'wta' in t or ' vs ' in t:
        # Check if it's tennis by looking for typical tennis patterns
        if any(x in t for x in ['miami open', 'australian open', 'french open', 
                                'wimbledon', 'us open', 'indian wells', 'rome',
                                'monte carlo', 'madrid', 'roland garros']):
            return 'Tennis'
        # Player names pattern (First Last vs First Last)
        if re.search(r'\w+\s+\w+\s+vs\.?\s+\w+\s+\w+', t):
            if not any(x in t for x in nba_teams + mlb_teams):
                return 'Tennis'
    
    # Esports
    if any(x in t for x in ['counter-strike', 'csgo', 'cs2', 'dota', 'league of legends',
                            'valorant', 'esports', 'gaming', 'lol']):
        return 'Esports'
    
    # Politics
    if any(x in t for x in ['trump', 'biden', 'election', 'congress', 'senate', 
                            'president', 'republican', 'democrat', 'vote', 'governor',
                            'house of representatives', 'political']):
        return 'Politics'
    
    # Geopolitics
    if any(x in t for x in ['iran', 'israel', 'ukraine', 'russia', 'war', 'military',
                            'nuclear', 'china', 'taiwan', 'conflict', 'invasion',
                            'sanctions', 'missile', 'attack']):
        return 'Geopolitics'
    
    # Crypto
    if any(x in t for x in ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'solana',
                            'dogecoin', 'ripple', 'xrp', 'blockchain']):
        return 'Crypto'
    
    # Spreads/Over-Under (generic)
    if 'spread' in t or 'o/u' in t or 'over/under' in t:
        return 'Spreads'
    
    # If has "vs" it's likely sports
    if ' vs ' in t or ' vs. ' in t:
        return 'Sports-Other'
    
    return 'Other'


def analyze_categories():
    """Analyze win rates by category."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    print('=' * 70)
    print('CATEGORY ANALYSIS')
    print('=' * 70)
    
    # Get all resolved consensus picks
    cur.execute('''
        SELECT market_title, outcome FROM consensus_picks 
        WHERE outcome IN ('won', 'lost')
    ''')
    
    categories = defaultdict(lambda: {'won': 0, 'lost': 0})
    
    for title, outcome in cur.fetchall():
        cat = categorize_market(title)
        categories[cat][outcome] += 1
    
    print('\n📊 CONSENSUS PICKS BY CATEGORY')
    print('-' * 60)
    print(f'{"Category":<20} {"Won":<6} {"Lost":<6} {"Total":<8} {"WinRate":<10} {"Verdict"}')
    print('-' * 60)
    
    for cat, data in sorted(categories.items(), key=lambda x: x[1]['won']+x[1]['lost'], reverse=True):
        won, lost = data['won'], data['lost']
        total = won + lost
        wr = won/total*100 if total > 0 else 0
        verdict = '✅ GOOD' if wr >= 55 else '❌ AVOID' if wr < 45 else '⚠️ MEH'
        print(f'{cat:<20} {won:<6} {lost:<6} {total:<8} {wr:<10.1f} {verdict}')
    
    # Now analyze whale positions by category
    print('\n' + '=' * 70)
    print('WHALE POSITIONS BY CATEGORY (Larger Sample)')
    print('=' * 70)
    
    cur.execute('''
        SELECT market_title, outcome FROM whale_positions 
        WHERE outcome IN ('won', 'lost')
    ''')
    
    whale_cats = defaultdict(lambda: {'won': 0, 'lost': 0})
    
    for title, outcome in cur.fetchall():
        cat = categorize_market(title)
        whale_cats[cat][outcome] += 1
    
    print(f'\n{"Category":<20} {"Won":<8} {"Lost":<8} {"Total":<10} {"WinRate":<10} {"Verdict"}')
    print('-' * 70)
    
    for cat, data in sorted(whale_cats.items(), key=lambda x: x[1]['won']+x[1]['lost'], reverse=True):
        won, lost = data['won'], data['lost']
        total = won + lost
        wr = won/total*100 if total > 0 else 0
        sig = 'SIGNIFICANT' if total >= 100 else 'LOW'
        verdict = '✅ GOOD' if wr >= 55 else '❌ AVOID' if wr < 45 else '⚠️ MEH'
        print(f'{cat:<20} {won:<8} {lost:<8} {total:<10} {wr:<10.1f} {verdict} [{sig}]')
    
    conn.close()
    
    print('\n' + '=' * 70)
    print('ANALYSIS COMPLETE')
    print('=' * 70)


def update_pick_categories():
    """Update consensus picks with proper categories."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Add category column if not exists
    try:
        cur.execute('ALTER TABLE consensus_picks ADD COLUMN category TEXT')
        conn.commit()
    except:
        pass  # Column already exists
    
    # Update categories
    cur.execute('SELECT id, market_title FROM consensus_picks')
    for pick_id, title in cur.fetchall():
        cat = categorize_market(title)
        cur.execute('UPDATE consensus_picks SET category = ? WHERE id = ?', (cat, pick_id))
    
    conn.commit()
    print(f"Updated categories for all consensus picks")
    conn.close()


if __name__ == '__main__':
    update_pick_categories()
    analyze_categories()
