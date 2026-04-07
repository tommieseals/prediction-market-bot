"""
Whale Comparison Tool
=====================
Compare performance and patterns between any two whales.
"""
import sqlite3
from collections import defaultdict

DB_PATH = 'data/whale_hunter.db'


def get_whale_stats(conn, name_or_addr):
    """Get comprehensive stats for a whale."""
    cur = conn.cursor()
    
    # Try to find by name first, then address
    cur.execute('''
        SELECT address, display_name, elite_score, pnl, win_rate_raw, 
               brier_score, insider_flags, insider_score, num_trades,
               tracked_bets, winning_bets, tracked_accuracy
        FROM tracked_whales
        WHERE display_name LIKE ? OR address LIKE ?
        LIMIT 1
    ''', (f'%{name_or_addr}%', f'%{name_or_addr}%'))
    
    row = cur.fetchone()
    if not row:
        return None
    
    addr = row[0]
    stats = {
        'address': addr,
        'name': row[1] or addr[:12],
        'elite_score': row[2] or 0,
        'pnl': row[3] or 0,
        'win_rate': row[4] or 0,
        'brier_score': row[5],
        'insider_flags': row[6],
        'insider_score': row[7] or 0,
        'num_trades': row[8] or 0,
        'tracked_bets': row[9] or 0,
        'winning_bets': row[10] or 0,
        'tracked_accuracy': row[11] or 0
    }
    
    # Get position stats
    cur.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as lost,
            AVG(size_usd) as avg_size
        FROM whale_positions
        WHERE address = ?
        AND outcome IN ('won', 'lost')
    ''', (addr,))
    
    pos_row = cur.fetchone()
    stats['positions'] = {
        'total': pos_row[0] or 0,
        'won': pos_row[1] or 0,
        'lost': pos_row[2] or 0,
        'avg_size': pos_row[3] or 0
    }
    
    # Calculate actual win rate from positions
    if stats['positions']['won'] + stats['positions']['lost'] > 0:
        stats['actual_wr'] = stats['positions']['won'] / (stats['positions']['won'] + stats['positions']['lost'])
    else:
        stats['actual_wr'] = 0
    
    # Get category breakdown
    cur.execute('''
        SELECT market_title, outcome FROM whale_positions
        WHERE address = ? AND outcome IN ('won', 'lost')
    ''', (addr,))
    
    categories = defaultdict(lambda: {'won': 0, 'lost': 0})
    for title, outcome in cur.fetchall():
        if not title:
            continue
        t = title.lower()
        if 'tennis' in t or 'open' in t:
            cat = 'Tennis'
        elif 'spread' in t or 'o/u' in t:
            cat = 'Spreads'
        elif any(x in t for x in ['nba', 'lakers', 'celtics']):
            cat = 'NBA'
        else:
            cat = 'Other'
        categories[cat][outcome] += 1
    
    stats['categories'] = dict(categories)
    
    # Get current streak
    cur.execute('''
        SELECT outcome FROM whale_positions
        WHERE address = ? AND outcome IN ('won', 'lost')
        ORDER BY detected_at DESC
    ''', (addr,))
    
    outcomes = [r[0] for r in cur.fetchall()]
    streak = 0
    for o in outcomes:
        if o == 'won':
            streak += 1
        else:
            break
    stats['current_streak'] = streak
    
    # Get max streak
    max_streak = 0
    temp = 0
    for o in outcomes:
        if o == 'won':
            temp += 1
            max_streak = max(max_streak, temp)
        else:
            temp = 0
    stats['max_streak'] = max_streak
    
    return stats


def compare_whales(stats1, stats2):
    """Print comparison between two whales."""
    print('=' * 70)
    print('WHALE COMPARISON')
    print('=' * 70)
    
    # Header
    print(f'\n{"Metric":<25} {stats1["name"]:<20} {stats2["name"]:<20}')
    print('-' * 65)
    
    # Basic stats
    print(f'{"Elite Score":<25} {stats1["elite_score"]:<20.0f} {stats2["elite_score"]:<20.0f}')
    print(f'{"PnL":<25} ${stats1["pnl"]:,.0f}{" ":<13} ${stats2["pnl"]:,.0f}')
    print(f'{"Tracked Win Rate":<25} {stats1["actual_wr"]*100:.1f}%{" ":<17} {stats2["actual_wr"]*100:.1f}%')
    print(f'{"Total Bets":<25} {stats1["positions"]["total"]:<20} {stats2["positions"]["total"]:<20}')
    print(f'{"W/L":<25} {stats1["positions"]["won"]}/{stats1["positions"]["lost"]}{" ":<14} {stats2["positions"]["won"]}/{stats2["positions"]["lost"]}')
    print(f'{"Current Streak":<25} {stats1["current_streak"]:<20} {stats2["current_streak"]:<20}')
    print(f'{"Max Streak":<25} {stats1["max_streak"]:<20} {stats2["max_streak"]:<20}')
    
    if stats1.get('insider_score') or stats2.get('insider_score'):
        print(f'{"Insider Score":<25} {stats1["insider_score"]:<20.0f} {stats2["insider_score"]:<20.0f}')
    
    # Category breakdown
    print(f'\n{"Category Performance":<25}')
    print('-' * 65)
    
    all_cats = set(stats1['categories'].keys()) | set(stats2['categories'].keys())
    for cat in sorted(all_cats):
        s1 = stats1['categories'].get(cat, {'won': 0, 'lost': 0})
        s2 = stats2['categories'].get(cat, {'won': 0, 'lost': 0})
        
        s1_wr = s1['won']/(s1['won']+s1['lost'])*100 if (s1['won']+s1['lost']) > 0 else 0
        s2_wr = s2['won']/(s2['won']+s2['lost'])*100 if (s2['won']+s2['lost']) > 0 else 0
        
        s1_str = f"{s1['won']}/{s1['lost']} ({s1_wr:.0f}%)"
        s2_str = f"{s2['won']}/{s2['lost']} ({s2_wr:.0f}%)"
        
        print(f'{cat:<25} {s1_str:<20} {s2_str:<20}')
    
    # Winner
    print('\n' + '=' * 65)
    if stats1['actual_wr'] > stats2['actual_wr']:
        print(f'WINNER: {stats1["name"]} ({stats1["actual_wr"]*100:.1f}% vs {stats2["actual_wr"]*100:.1f}%)')
    elif stats2['actual_wr'] > stats1['actual_wr']:
        print(f'WINNER: {stats2["name"]} ({stats2["actual_wr"]*100:.1f}% vs {stats1["actual_wr"]*100:.1f}%)')
    else:
        print('TIE - Same win rate!')


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('whale1', nargs='?', help='First whale name/address')
    parser.add_argument('whale2', nargs='?', help='Second whale name/address')
    args = parser.parse_args()
    
    conn = sqlite3.connect(DB_PATH)
    
    if not args.whale1 or not args.whale2:
        # Show top whales if no args
        cur = conn.cursor()
        cur.execute('''
            SELECT display_name FROM tracked_whales 
            WHERE elite_score > 0 
            ORDER BY elite_score DESC 
            LIMIT 10
        ''')
        print("Usage: python whale_compare.py <whale1> <whale2>")
        print("\nTop whales to compare:")
        for row in cur.fetchall():
            print(f"  - {row[0]}")
        conn.close()
        return
    
    stats1 = get_whale_stats(conn, args.whale1)
    stats2 = get_whale_stats(conn, args.whale2)
    
    if not stats1:
        print(f"Whale not found: {args.whale1}")
        return
    if not stats2:
        print(f"Whale not found: {args.whale2}")
        return
    
    compare_whales(stats1, stats2)
    
    conn.close()


if __name__ == '__main__':
    main()
