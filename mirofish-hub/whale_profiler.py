"""
Whale Profiler - Deep Individual Analysis
==========================================
Builds detailed profiles for each whale including:
- Specialty detection (sports teams, categories)
- Win streaks and hot hands
- Time patterns (when do they bet, when do they win)
- Size patterns
- Follow score (should we copy this whale?)
"""
import sqlite3
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import json
import re

DB_PATH = 'data/whale_hunter.db'

def get_connection():
    return sqlite3.connect(DB_PATH)

def extract_keywords(title):
    """Extract meaningful keywords from market title."""
    if not title:
        return []
    
    title_lower = title.lower()
    keywords = []
    
    # NBA teams
    nba_teams = ['lakers', 'celtics', 'warriors', 'bucks', 'bulls', 'knicks', 
                 'nets', 'heat', 'suns', 'nuggets', 'mavericks', 'clippers',
                 'rockets', 'spurs', 'sixers', '76ers', 'raptors', 'jazz',
                 'pistons', 'pacers', 'hawks', 'hornets', 'magic', 'wizards',
                 'cavaliers', 'cavs', 'thunder', 'blazers', 'kings', 'pelicans',
                 'grizzlies', 'timberwolves', 'wolves']
    for team in nba_teams:
        if team in title_lower:
            keywords.append(f'NBA:{team.title()}')
    
    # MLB teams
    mlb_teams = ['yankees', 'dodgers', 'mets', 'red sox', 'white sox', 'cubs',
                 'cardinals', 'braves', 'astros', 'phillies', 'padres', 'mariners',
                 'rays', 'guardians', 'rangers', 'orioles', 'twins', 'brewers',
                 'pirates', 'reds', 'royals', 'tigers', 'athletics', 'angels',
                 'rockies', 'marlins', 'nationals', 'diamondbacks', 'giants']
    for team in mlb_teams:
        if team in title_lower:
            keywords.append(f'MLB:{team.title()}')
    
    # Categories
    if any(x in title_lower for x in ['trump', 'biden', 'election', 'congress', 'senate', 'president']):
        keywords.append('CAT:Politics')
    if any(x in title_lower for x in ['iran', 'israel', 'ukraine', 'russia', 'war', 'military', 'nuclear']):
        keywords.append('CAT:Geopolitics')
    if any(x in title_lower for x in ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto']):
        keywords.append('CAT:Crypto')
    if any(x in title_lower for x in ['counter-strike', 'esports', 'dota', 'league of legends']):
        keywords.append('CAT:Esports')
    if any(x in title_lower for x in ['tennis', 'open', 'atp', 'wta']):
        keywords.append('CAT:Tennis')
    if any(x in title_lower for x in ['spread:', 'o/u', 'over/under']):
        keywords.append('TYPE:Spread')
    
    # Sports general
    if any(x in title_lower for x in nba_teams) or 'nba' in title_lower:
        keywords.append('SPORT:NBA')
    if any(x in title_lower for x in mlb_teams) or 'mlb' in title_lower:
        keywords.append('SPORT:MLB')
    
    return keywords


def build_whale_profile(address, conn):
    """Build comprehensive profile for a single whale."""
    cur = conn.cursor()
    
    # Get whale basic info
    cur.execute('''
        SELECT display_name, elite_score, pnl, num_trades, win_rate_raw,
               brier_score, insider_flags, insider_score, categories,
               tracked_bets, winning_bets, tracked_accuracy
        FROM tracked_whales WHERE address = ?
    ''', (address,))
    whale_row = cur.fetchone()
    
    if not whale_row:
        return None
    
    profile = {
        'address': address,
        'name': whale_row[0] or address[:12],
        'elite_score': whale_row[1] or 0,
        'pnl': whale_row[2] or 0,
        'num_trades': whale_row[3] or 0,
        'win_rate': whale_row[4] or 0,
        'brier_score': whale_row[5],
        'insider_flags': whale_row[6],
        'insider_score': whale_row[7] or 0,
        'tracked_bets': whale_row[9] or 0,
        'winning_bets': whale_row[10] or 0,
        'tracked_accuracy': whale_row[11] or 0,
    }
    
    # Get all positions for this whale
    cur.execute('''
        SELECT market_title, side, size_usd, outcome, detected_at, entry_price
        FROM whale_positions 
        WHERE address = ?
        ORDER BY detected_at
    ''', (address,))
    positions = cur.fetchall()
    
    if not positions:
        profile['specialty'] = None
        profile['patterns'] = {}
        return profile
    
    # Analyze specialties
    keyword_outcomes = defaultdict(lambda: {'won': 0, 'lost': 0, 'total': 0})
    day_outcomes = defaultdict(lambda: {'won': 0, 'lost': 0})
    hour_outcomes = defaultdict(lambda: {'won': 0, 'lost': 0})
    side_outcomes = {'YES': {'won': 0, 'lost': 0}, 'NO': {'won': 0, 'lost': 0}}
    size_outcomes = defaultdict(lambda: {'won': 0, 'lost': 0})
    
    streak_current = 0
    streak_max = 0
    streaks = []
    last_outcome = None
    
    for title, side, size, outcome, detected_at, entry_price in positions:
        keywords = extract_keywords(title)
        
        for kw in keywords:
            keyword_outcomes[kw]['total'] += 1
            if outcome == 'won':
                keyword_outcomes[kw]['won'] += 1
            elif outcome == 'lost':
                keyword_outcomes[kw]['lost'] += 1
        
        # Time patterns
        if detected_at:
            try:
                dt = datetime.fromisoformat(detected_at.replace('Z', '+00:00'))
                dow = dt.strftime('%a')
                hour = dt.hour
                day_outcomes[dow]['won' if outcome == 'won' else 'lost'] += 1 if outcome in ('won', 'lost') else 0
                hour_outcomes[hour]['won' if outcome == 'won' else 'lost'] += 1 if outcome in ('won', 'lost') else 0
            except:
                pass
        
        # Side patterns
        if side in ('YES', 'NO') and outcome in ('won', 'lost'):
            side_outcomes[side]['won' if outcome == 'won' else 'lost'] += 1
        
        # Size patterns
        if size and outcome in ('won', 'lost'):
            if size < 100:
                tier = 'small'
            elif size < 500:
                tier = 'medium'
            elif size < 2000:
                tier = 'large'
            else:
                tier = 'whale'
            size_outcomes[tier]['won' if outcome == 'won' else 'lost'] += 1
        
        # Streak tracking
        if outcome in ('won', 'lost'):
            if outcome == last_outcome:
                streak_current += 1
            else:
                if streak_current > 0 and last_outcome == 'won':
                    streaks.append(streak_current)
                streak_current = 1
            streak_max = max(streak_max, streak_current if outcome == 'won' else 0)
            last_outcome = outcome
    
    # Find specialties (high concentration + good win rate)
    specialties = []
    for kw, data in keyword_outcomes.items():
        if data['total'] >= 5:  # Minimum 5 bets on this keyword
            total_resolved = data['won'] + data['lost']
            if total_resolved >= 3:
                wr = data['won'] / total_resolved
                concentration = data['total'] / len(positions)
                if concentration >= 0.1 or data['total'] >= 10:  # 10%+ focus or 10+ bets
                    specialties.append({
                        'keyword': kw,
                        'bets': data['total'],
                        'won': data['won'],
                        'lost': data['lost'],
                        'win_rate': wr,
                        'concentration': concentration
                    })
    
    # Sort by win rate
    specialties.sort(key=lambda x: (x['win_rate'], x['bets']), reverse=True)
    
    profile['specialties'] = specialties[:5]  # Top 5
    profile['total_positions'] = len(positions)
    profile['max_win_streak'] = streak_max
    profile['avg_win_streak'] = sum(streaks) / len(streaks) if streaks else 0
    
    # Best day/hour
    best_day = max(day_outcomes.items(), key=lambda x: x[1]['won']/(x[1]['won']+x[1]['lost']) if (x[1]['won']+x[1]['lost']) > 0 else 0, default=(None, {}))
    profile['best_day'] = best_day[0] if best_day[1].get('won', 0) + best_day[1].get('lost', 0) >= 3 else None
    
    # Side preference
    yes_total = side_outcomes['YES']['won'] + side_outcomes['YES']['lost']
    no_total = side_outcomes['NO']['won'] + side_outcomes['NO']['lost']
    if yes_total > 0 and no_total > 0:
        yes_wr = side_outcomes['YES']['won'] / yes_total
        no_wr = side_outcomes['NO']['won'] / no_total
        profile['better_side'] = 'YES' if yes_wr > no_wr else 'NO'
        profile['side_edge'] = abs(yes_wr - no_wr)
    else:
        profile['better_side'] = None
        profile['side_edge'] = 0
    
    # Calculate FOLLOW SCORE (0-100)
    # Factors: win rate, consistency, specialty strength, insider score
    follow_score = 0
    
    # Win rate contribution (max 30)
    if profile['tracked_accuracy'] > 0:
        follow_score += min(30, profile['tracked_accuracy'] * 30)
    elif profile['win_rate'] > 0:
        follow_score += min(30, profile['win_rate'] * 30)
    
    # Elite score contribution (max 20)
    follow_score += min(20, profile['elite_score'] / 5)
    
    # Specialty bonus (max 20)
    if specialties:
        best_spec = specialties[0]
        if best_spec['win_rate'] >= 0.7 and best_spec['bets'] >= 5:
            follow_score += 20
        elif best_spec['win_rate'] >= 0.6:
            follow_score += 10
    
    # Insider score contribution (max 15)
    follow_score += min(15, profile['insider_score'] / 5)
    
    # Streak bonus (max 10)
    if profile['max_win_streak'] >= 5:
        follow_score += 10
    elif profile['max_win_streak'] >= 3:
        follow_score += 5
    
    # Sample size penalty
    if profile['tracked_bets'] < 10:
        follow_score *= 0.5
    elif profile['tracked_bets'] < 20:
        follow_score *= 0.75
    
    profile['follow_score'] = min(100, follow_score)
    
    return profile


def find_single_team_specialists(conn, min_bets=5, min_concentration=0.3):
    """Find whales who focus heavily on single teams."""
    cur = conn.cursor()
    
    cur.execute('SELECT DISTINCT address FROM whale_positions')
    addresses = [r[0] for r in cur.fetchall()]
    
    specialists = []
    
    for addr in addresses:
        cur.execute('''
            SELECT market_title FROM whale_positions 
            WHERE address = ? AND market_title IS NOT NULL
        ''', (addr,))
        titles = [r[0] for r in cur.fetchall()]
        
        if len(titles) < min_bets:
            continue
        
        # Count team mentions
        team_counts = Counter()
        for title in titles:
            keywords = extract_keywords(title)
            for kw in keywords:
                if kw.startswith('NBA:') or kw.startswith('MLB:'):
                    team_counts[kw] += 1
        
        if not team_counts:
            continue
        
        # Check for concentration
        most_common = team_counts.most_common(1)[0]
        team, count = most_common
        concentration = count / len(titles)
        
        if concentration >= min_concentration and count >= min_bets:
            # Get whale name
            cur.execute('SELECT display_name FROM tracked_whales WHERE address = ?', (addr,))
            name_row = cur.fetchone()
            name = name_row[0] if name_row else addr[:12]
            
            # Get win rate on this team
            cur.execute('''
                SELECT outcome FROM whale_positions 
                WHERE address = ? AND market_title LIKE ?
            ''', (addr, f'%{team.split(":")[1]}%'))
            outcomes = [r[0] for r in cur.fetchall()]
            won = outcomes.count('won')
            lost = outcomes.count('lost')
            wr = won / (won + lost) if (won + lost) > 0 else 0
            
            specialists.append({
                'address': addr,
                'name': name,
                'team': team,
                'bets': count,
                'total_bets': len(titles),
                'concentration': concentration,
                'won': won,
                'lost': lost,
                'win_rate': wr
            })
    
    return sorted(specialists, key=lambda x: x['concentration'], reverse=True)


def find_hot_hands(conn, min_streak=3):
    """Find whales currently on winning streaks."""
    cur = conn.cursor()
    
    cur.execute('SELECT DISTINCT address FROM whale_positions')
    addresses = [r[0] for r in cur.fetchall()]
    
    hot_hands = []
    
    for addr in addresses:
        cur.execute('''
            SELECT outcome, detected_at FROM whale_positions 
            WHERE address = ? AND outcome IN ('won', 'lost')
            ORDER BY detected_at DESC
            LIMIT 20
        ''', (addr,))
        recent = cur.fetchall()
        
        if not recent:
            continue
        
        # Count current streak
        current_streak = 0
        for outcome, _ in recent:
            if outcome == 'won':
                current_streak += 1
            else:
                break
        
        if current_streak >= min_streak:
            cur.execute('SELECT display_name, elite_score, pnl FROM tracked_whales WHERE address = ?', (addr,))
            info = cur.fetchone()
            name = info[0] if info else addr[:12]
            
            hot_hands.append({
                'address': addr,
                'name': name,
                'streak': current_streak,
                'elite_score': info[1] if info else 0,
                'pnl': info[2] if info else 0
            })
    
    return sorted(hot_hands, key=lambda x: x['streak'], reverse=True)


def save_profiles_to_db(profiles, conn):
    """Save whale profiles to database."""
    cur = conn.cursor()
    
    # Create profiles table if not exists
    cur.execute('''
        CREATE TABLE IF NOT EXISTS whale_profiles (
            address TEXT PRIMARY KEY,
            name TEXT,
            follow_score REAL,
            specialties TEXT,
            max_win_streak INTEGER,
            better_side TEXT,
            best_day TEXT,
            profile_json TEXT,
            updated_at TEXT
        )
    ''')
    
    for profile in profiles:
        cur.execute('''
            INSERT OR REPLACE INTO whale_profiles 
            (address, name, follow_score, specialties, max_win_streak, better_side, best_day, profile_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            profile['address'],
            profile['name'],
            profile.get('follow_score', 0),
            json.dumps(profile.get('specialties', [])),
            profile.get('max_win_streak', 0),
            profile.get('better_side'),
            profile.get('best_day'),
            json.dumps(profile),
            datetime.now().isoformat()
        ))
    
    conn.commit()
    print(f"Saved {len(profiles)} profiles to database")


def main():
    conn = get_connection()
    cur = conn.cursor()
    
    print('=' * 70)
    print('WHALE PROFILER - Building Individual Profiles')
    print('=' * 70)
    
    # Get all tracked whales
    cur.execute('SELECT address FROM tracked_whales WHERE elite_score > 0 ORDER BY elite_score DESC')
    addresses = [r[0] for r in cur.fetchall()]
    print(f'\nBuilding profiles for {len(addresses)} whales...')
    
    profiles = []
    for i, addr in enumerate(addresses):
        profile = build_whale_profile(addr, conn)
        if profile:
            profiles.append(profile)
        if (i + 1) % 50 == 0:
            print(f'  Processed {i+1}/{len(addresses)}...')
    
    # Sort by follow score
    profiles.sort(key=lambda x: x.get('follow_score', 0), reverse=True)
    
    # Save to database
    save_profiles_to_db(profiles, conn)
    
    # Print top profiles
    print('\n' + '=' * 70)
    print('TOP 20 WHALES BY FOLLOW SCORE')
    print('=' * 70)
    print(f'\n{"Name":<20} {"Follow":<8} {"WinRate":<8} {"Streak":<8} {"Specialty"}')
    print('-' * 70)
    for p in profiles[:20]:
        spec = p['specialties'][0]['keyword'] if p.get('specialties') else '-'
        wr = f"{p['tracked_accuracy']*100:.0f}%" if p['tracked_accuracy'] else f"{p['win_rate']*100:.0f}%"
        print(f"{p['name'][:18]:<20} {p['follow_score']:<8.0f} {wr:<8} {p['max_win_streak']:<8} {spec}")
    
    # Find single-team specialists
    print('\n' + '=' * 70)
    print('SINGLE TEAM SPECIALISTS')
    print('=' * 70)
    specialists = find_single_team_specialists(conn)
    print(f'\n{"Name":<20} {"Team":<20} {"Bets":<6} {"Focus%":<8} {"WinRate"}')
    print('-' * 65)
    for s in specialists[:15]:
        wr = f"{s['win_rate']*100:.0f}%"
        print(f"{s['name'][:18]:<20} {s['team']:<20} {s['bets']:<6} {s['concentration']*100:<8.0f} {wr}")
    
    # Find hot hands
    print('\n' + '=' * 70)
    print('HOT HANDS (Current Win Streaks)')
    print('=' * 70)
    hot_hands = find_hot_hands(conn)
    print(f'\n{"Name":<25} {"Streak":<8} {"Elite":<8} {"PnL"}')
    print('-' * 55)
    for h in hot_hands[:15]:
        pnl = f"${h['pnl']:,.0f}" if h['pnl'] else '$0'
        print(f"{h['name'][:23]:<25} {h['streak']:<8} {h['elite_score']:<8.0f} {pnl}")
    
    conn.close()
    print('\n' + '=' * 70)
    print('PROFILER COMPLETE')
    print('=' * 70)


if __name__ == '__main__':
    main()
