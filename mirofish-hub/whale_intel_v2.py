"""
Whale Intelligence System v2
============================
Comprehensive whale analysis with:
- Individual profiles
- Team/category specialists
- Hot hands (real streaks)
- Follow recommendations
"""
import sqlite3
from collections import defaultdict, Counter
from datetime import datetime
import json

DB_PATH = 'data/whale_hunter.db'

def get_real_streaks(conn, min_streak=5):
    """Get actual win streaks for all whales."""
    cur = conn.cursor()
    
    cur.execute('SELECT DISTINCT address FROM whale_positions')
    addresses = [r[0] for r in cur.fetchall()]
    
    streaks = []
    for addr in addresses:
        cur.execute('''
            SELECT outcome FROM whale_positions 
            WHERE address = ? AND outcome IN ('won', 'lost')
            ORDER BY detected_at DESC
        ''', (addr,))
        outcomes = [r[0] for r in cur.fetchall()]
        
        if not outcomes:
            continue
        
        # Count current streak
        current = 0
        for o in outcomes:
            if o == 'won':
                current += 1
            else:
                break
        
        # Count max streak
        max_streak = 0
        temp = 0
        for o in outcomes:
            if o == 'won':
                temp += 1
                max_streak = max(max_streak, temp)
            else:
                temp = 0
        
        total_won = outcomes.count('won')
        total = len(outcomes)
        
        if current >= min_streak or max_streak >= min_streak:
            cur.execute('SELECT display_name, elite_score, pnl FROM tracked_whales WHERE address = ?', (addr,))
            info = cur.fetchone()
            streaks.append({
                'address': addr,
                'name': info[0] if info else addr[:12],
                'current_streak': current,
                'max_streak': max_streak,
                'total_won': total_won,
                'total_bets': total,
                'win_rate': total_won / total if total > 0 else 0,
                'elite_score': info[1] if info else 0,
                'pnl': info[2] if info else 0
            })
    
    return sorted(streaks, key=lambda x: x['current_streak'], reverse=True)


def get_team_specialists(conn, min_bets=3, min_concentration=0.2):
    """Find whales who specialize in specific teams."""
    cur = conn.cursor()
    
    # Define teams to look for
    teams = {
        'Lakers': 'lakers',
        'Celtics': 'celtics', 
        'Warriors': 'warriors',
        'Wizards': 'wizards',
        'Knicks': 'knicks',
        'Bulls': 'bulls',
        'Heat': 'heat',
        'Mavericks': 'mavericks',
        'Bucks': 'bucks',
        'Nets': 'nets',
        'Suns': 'suns',
        'Yankees': 'yankees',
        'Dodgers': 'dodgers',
        'Mets': 'mets',
        'Cubs': 'cubs'
    }
    
    specialists = []
    
    cur.execute('SELECT DISTINCT address FROM whale_positions')
    addresses = [r[0] for r in cur.fetchall()]
    
    for addr in addresses:
        cur.execute('''
            SELECT market_title, outcome FROM whale_positions 
            WHERE address = ?
        ''', (addr,))
        positions = cur.fetchall()
        
        if len(positions) < min_bets:
            continue
        
        # Count team mentions
        team_counts = Counter()
        team_outcomes = defaultdict(lambda: {'won': 0, 'lost': 0})
        
        for title, outcome in positions:
            if not title:
                continue
            title_lower = title.lower()
            for team_name, team_key in teams.items():
                if team_key in title_lower:
                    team_counts[team_name] += 1
                    if outcome in ('won', 'lost'):
                        team_outcomes[team_name][outcome] += 1
        
        if not team_counts:
            continue
        
        # Check for concentration
        for team, count in team_counts.most_common(3):
            concentration = count / len(positions)
            if concentration >= min_concentration and count >= min_bets:
                won = team_outcomes[team]['won']
                lost = team_outcomes[team]['lost']
                total = won + lost
                
                cur.execute('SELECT display_name, pnl FROM tracked_whales WHERE address = ?', (addr,))
                info = cur.fetchone()
                
                specialists.append({
                    'address': addr,
                    'name': info[0] if info else addr[:12],
                    'team': team,
                    'bets': count,
                    'total_bets': len(positions),
                    'concentration': concentration,
                    'won': won,
                    'lost': lost,
                    'win_rate': won / total if total > 0 else 0,
                    'pnl': info[1] if info else 0
                })
    
    return sorted(specialists, key=lambda x: (x['concentration'], x['bets']), reverse=True)


def get_category_specialists(conn, min_bets=5):
    """Find whales who specialize in categories."""
    cur = conn.cursor()
    
    categories = {
        'Politics': ['trump', 'biden', 'election', 'congress', 'senate', 'president', 'republican', 'democrat'],
        'Geopolitics': ['iran', 'israel', 'ukraine', 'russia', 'war', 'military', 'nuclear', 'china'],
        'Crypto': ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'solana'],
        'Tennis': ['tennis', 'open', 'atp', 'wta', 'djokovic', 'nadal', 'federer'],
        'Esports': ['counter-strike', 'esports', 'dota', 'league of legends', 'valorant'],
        'Spreads': ['spread:', 'o/u ', 'over/under']
    }
    
    specialists = []
    
    cur.execute('SELECT DISTINCT address FROM whale_positions')
    addresses = [r[0] for r in cur.fetchall()]
    
    for addr in addresses:
        cur.execute('''
            SELECT market_title, outcome FROM whale_positions 
            WHERE address = ?
        ''', (addr,))
        positions = cur.fetchall()
        
        if len(positions) < min_bets:
            continue
        
        cat_outcomes = defaultdict(lambda: {'won': 0, 'lost': 0, 'total': 0})
        
        for title, outcome in positions:
            if not title:
                continue
            title_lower = title.lower()
            for cat, keywords in categories.items():
                if any(kw in title_lower for kw in keywords):
                    cat_outcomes[cat]['total'] += 1
                    if outcome in ('won', 'lost'):
                        cat_outcomes[cat][outcome] += 1
        
        for cat, data in cat_outcomes.items():
            if data['total'] >= min_bets:
                won, lost = data['won'], data['lost']
                total_resolved = won + lost
                if total_resolved >= 3:
                    concentration = data['total'] / len(positions)
                    
                    cur.execute('SELECT display_name, pnl, elite_score FROM tracked_whales WHERE address = ?', (addr,))
                    info = cur.fetchone()
                    
                    specialists.append({
                        'address': addr,
                        'name': info[0] if info else addr[:12],
                        'category': cat,
                        'bets': data['total'],
                        'total_bets': len(positions),
                        'concentration': concentration,
                        'won': won,
                        'lost': lost,
                        'win_rate': won / total_resolved,
                        'elite_score': info[2] if info else 0
                    })
    
    return sorted(specialists, key=lambda x: (x['win_rate'], x['bets']), reverse=True)


def get_best_followers(conn):
    """Get whales with best follow scores from profiles."""
    cur = conn.cursor()
    
    cur.execute('''
        SELECT name, follow_score, specialties, max_win_streak, profile_json
        FROM whale_profiles
        ORDER BY follow_score DESC
        LIMIT 30
    ''')
    
    return [
        {
            'name': r[0],
            'score': r[1],
            'specialties': json.loads(r[2]) if r[2] else [],
            'max_streak': r[3],
            'profile': json.loads(r[4]) if r[4] else {}
        }
        for r in cur.fetchall()
    ]


def main():
    conn = sqlite3.connect(DB_PATH)
    
    print('=' * 70)
    print('WHALE INTELLIGENCE REPORT')
    print(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('=' * 70)
    
    # 1. HOT HANDS
    print('\n' + '=' * 70)
    print('1. HOT HANDS - Current Win Streaks')
    print('=' * 70)
    streaks = get_real_streaks(conn, min_streak=5)
    print(f'\n{"Name":<22} {"Current":<9} {"Max":<6} {"W/L":<10} {"WinRate":<8} {"PnL"}')
    print('-' * 70)
    for s in streaks[:20]:
        wr = f"{s['win_rate']*100:.0f}%"
        wl = f"{s['total_won']}/{s['total_bets']}"
        pnl = f"${s['pnl']:,.0f}" if s['pnl'] else '$0'
        print(f"{s['name'][:20]:<22} {s['current_streak']:<9} {s['max_streak']:<6} {wl:<10} {wr:<8} {pnl}")
    
    # 2. TEAM SPECIALISTS
    print('\n' + '=' * 70)
    print('2. TEAM SPECIALISTS')
    print('=' * 70)
    team_specs = get_team_specialists(conn)
    if team_specs:
        print(f'\n{"Name":<20} {"Team":<12} {"Bets":<6} {"Focus%":<8} {"W/L":<8} {"WinRate"}')
        print('-' * 65)
        for s in team_specs[:20]:
            wr = f"{s['win_rate']*100:.0f}%"
            wl = f"{s['won']}/{s['won']+s['lost']}"
            print(f"{s['name'][:18]:<20} {s['team']:<12} {s['bets']:<6} {s['concentration']*100:<8.0f} {wl:<8} {wr}")
    else:
        print('\nNo strong team specialists found (need more data)')
    
    # 3. CATEGORY SPECIALISTS
    print('\n' + '=' * 70)
    print('3. CATEGORY SPECIALISTS (by win rate)')
    print('=' * 70)
    cat_specs = get_category_specialists(conn)
    print(f'\n{"Name":<20} {"Category":<12} {"Bets":<6} {"W/L":<8} {"WinRate":<8} {"Elite"}')
    print('-' * 65)
    for s in cat_specs[:25]:
        wr = f"{s['win_rate']*100:.0f}%"
        wl = f"{s['won']}/{s['won']+s['lost']}"
        print(f"{s['name'][:18]:<20} {s['category']:<12} {s['bets']:<6} {wl:<8} {wr:<8} {s['elite_score']:.0f}")
    
    # 4. BEST TO FOLLOW
    print('\n' + '=' * 70)
    print('4. BEST WHALES TO FOLLOW (Composite Score)')
    print('=' * 70)
    followers = get_best_followers(conn)
    print(f'\n{"Name":<22} {"Score":<8} {"MaxStreak":<10} {"Top Specialty"}')
    print('-' * 65)
    for f in followers[:20]:
        spec = f['specialties'][0]['keyword'] if f['specialties'] else '-'
        print(f"{f['name'][:20]:<22} {f['score']:<8.0f} {f['max_streak']:<10} {spec}")
    
    # 5. SUSPICIOUS PATTERNS
    print('\n' + '=' * 70)
    print('5. SUSPICIOUS PATTERNS')
    print('=' * 70)
    
    # Perfect records
    print('\n100% Win Rate (Min 10 bets):')
    for s in streaks:
        if s['win_rate'] == 1.0 and s['total_bets'] >= 10:
            print(f"  {s['name'][:25]}: {s['total_bets']} bets, ${s['pnl']:,.0f} PnL")
    
    conn.close()
    
    print('\n' + '=' * 70)
    print('REPORT COMPLETE')
    print('=' * 70)


if __name__ == '__main__':
    main()
