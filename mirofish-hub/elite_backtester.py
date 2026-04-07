"""
Elite Strategy Backtester
=========================
Backtest what our win rate WOULD have been if we only followed elite whales.
Compare to consensus approach.
"""
import sqlite3
from collections import defaultdict
from datetime import datetime

DB_PATH = 'data/whale_hunter.db'


def backtest_elite_only(conn, min_wr=0.90, min_bets=20):
    """
    Simulate following only elite whales.
    Returns what our performance would have been.
    """
    cur = conn.cursor()
    
    # Get elite whales
    cur.execute('''
        SELECT w.address, w.display_name,
               COUNT(*) as bets,
               SUM(CASE WHEN p.outcome='won' THEN 1 ELSE 0 END) as won,
               SUM(CASE WHEN p.outcome='lost' THEN 1 ELSE 0 END) as lost
        FROM tracked_whales w
        JOIN whale_positions p ON w.address = p.address
        WHERE p.outcome IN ('won', 'lost')
        GROUP BY w.address
        HAVING bets >= ? AND (won * 1.0 / (won + lost)) >= ?
    ''', (min_bets, min_wr))
    
    elite_addrs = set()
    for row in cur.fetchall():
        elite_addrs.add(row[0])
    
    print(f"Found {len(elite_addrs)} elite whales (>={min_wr*100:.0f}% WR, >={min_bets} bets)")
    
    # Get all elite whale positions
    placeholders = ','.join(['?' for _ in elite_addrs])
    cur.execute(f'''
        SELECT p.market_title, p.side, p.outcome, p.address, w.display_name
        FROM whale_positions p
        JOIN tracked_whales w ON p.address = w.address
        WHERE p.address IN ({placeholders})
        AND p.outcome IN ('won', 'lost')
    ''', list(elite_addrs))
    
    # Track per-market outcomes (what if we followed any elite whale)
    market_signals = defaultdict(lambda: {'YES': [], 'NO': []})
    
    for market, side, outcome, addr, name in cur.fetchall():
        market_signals[market][side].append({
            'outcome': outcome,
            'whale': name
        })
    
    # Simulate strategy: Follow when elite whale makes a move
    results = {
        'any_elite': {'won': 0, 'lost': 0},
        'legendary_only': {'won': 0, 'lost': 0},
        'consensus_3plus': {'won': 0, 'lost': 0},
    }
    
    # Get legendary whales
    cur.execute('''
        SELECT address FROM elite_whales WHERE tier = 'LEGENDARY'
    ''')
    legendary_addrs = set(r[0] for r in cur.fetchall())
    
    for market, sides in market_signals.items():
        for side, positions in sides.items():
            if not positions:
                continue
            
            # Any elite whale strategy
            outcome = positions[0]['outcome']
            results['any_elite'][outcome] += 1
            
            # Check if any legendary whale
            # (would need to join with positions to check)
    
    return results


def compare_strategies(conn):
    """Compare different strategies."""
    cur = conn.cursor()
    
    print('=' * 70)
    print('STRATEGY BACKTESTER')
    print('=' * 70)
    
    # Strategy 1: Old consensus (all picks)
    cur.execute('''
        SELECT 
            SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as lost
        FROM consensus_picks
        WHERE outcome IN ('won', 'lost')
    ''')
    consensus = cur.fetchone()
    consensus_wr = consensus[0]/(consensus[0]+consensus[1])*100 if (consensus[0]+consensus[1]) > 0 else 0
    
    print(f'\n📊 STRATEGY COMPARISON')
    print('-' * 50)
    print(f'{"Strategy":<30} {"W/L":<12} {"Win Rate"}')
    print('-' * 50)
    print(f'{"Old Consensus (all)":<30} {consensus[0]}/{consensus[1]:<8} {consensus_wr:.1f}%')
    
    # Strategy 2: 3-5 whales only
    cur.execute('''
        SELECT 
            SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as lost
        FROM consensus_picks
        WHERE outcome IN ('won', 'lost')
        AND whale_count >= 3 AND whale_count <= 5
    ''')
    filtered = cur.fetchone()
    filtered_wr = filtered[0]/(filtered[0]+filtered[1])*100 if (filtered[0]+filtered[1]) > 0 else 0
    print(f'{"3-5 Whales Only":<30} {filtered[0]}/{filtered[1]:<8} {filtered_wr:.1f}%')
    
    # Strategy 3: 70-89% confidence only
    cur.execute('''
        SELECT 
            SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as lost
        FROM consensus_picks
        WHERE outcome IN ('won', 'lost')
        AND confidence >= 70 AND confidence < 90
    ''')
    conf = cur.fetchone()
    conf_wr = conf[0]/(conf[0]+conf[1])*100 if (conf[0]+conf[1]) > 0 else 0
    print(f'{"70-89% Confidence":<30} {conf[0]}/{conf[1]:<8} {conf_wr:.1f}%')
    
    # Strategy 4: Combined filter
    cur.execute('''
        SELECT 
            SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as lost
        FROM consensus_picks
        WHERE outcome IN ('won', 'lost')
        AND whale_count >= 3 AND whale_count <= 5
        AND confidence >= 70 AND confidence < 90
    ''')
    combined = cur.fetchone()
    combined_wr = combined[0]/(combined[0]+combined[1])*100 if (combined[0]+combined[1]) > 0 else 0
    print(f'{"Combined Filter":<30} {combined[0]}/{combined[1]:<8} {combined_wr:.1f}%')
    
    # Strategy 5: Individual elite whale positions
    cur.execute('''
        SELECT 
            SUM(CASE WHEN p.outcome='won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN p.outcome='lost' THEN 1 ELSE 0 END) as lost
        FROM whale_positions p
        JOIN elite_whales e ON p.address = e.address
        WHERE p.outcome IN ('won', 'lost')
        AND e.win_rate >= 0.90
    ''')
    elite = cur.fetchone()
    if elite and (elite[0] or elite[1]):
        elite_wr = elite[0]/(elite[0]+elite[1])*100 if (elite[0]+elite[1]) > 0 else 0
        print(f'{"Elite Whale Positions (90%+)":<30} {elite[0]}/{elite[1]:<8} {elite_wr:.1f}%')
    
    # Strategy 6: Legendary only
    cur.execute('''
        SELECT 
            SUM(CASE WHEN p.outcome='won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN p.outcome='lost' THEN 1 ELSE 0 END) as lost
        FROM whale_positions p
        JOIN elite_whales e ON p.address = e.address
        WHERE p.outcome IN ('won', 'lost')
        AND e.tier = 'LEGENDARY'
    ''')
    legendary = cur.fetchone()
    if legendary and (legendary[0] or legendary[1]):
        leg_wr = legendary[0]/(legendary[0]+legendary[1])*100 if (legendary[0]+legendary[1]) > 0 else 0
        print(f'{"LEGENDARY Only (100% WR)":<30} {legendary[0]}/{legendary[1]:<8} {leg_wr:.1f}%')
    
    print('-' * 50)
    
    # Calculate improvement potential
    print(f'\n📈 IMPROVEMENT POTENTIAL')
    print('-' * 50)
    if elite and (elite[0] or elite[1]):
        improvement = elite_wr - consensus_wr
        print(f'Elite vs Consensus: +{improvement:.1f}%')
    if legendary and (legendary[0] or legendary[1]):
        leg_improvement = leg_wr - consensus_wr
        print(f'Legendary vs Consensus: +{leg_improvement:.1f}%')


def main():
    conn = sqlite3.connect(DB_PATH)
    compare_strategies(conn)
    conn.close()


if __name__ == '__main__':
    main()
