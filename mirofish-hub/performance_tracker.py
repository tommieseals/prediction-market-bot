"""
Performance Tracker
===================
Tracks our actual trading performance over time.
Compares old consensus vs new elite-only approach.
"""
import sqlite3
from datetime import datetime, timedelta
import json

DB_PATH = 'data/whale_hunter.db'


def setup_tracking_tables(conn):
    """Create tracking tables if they don't exist."""
    cur = conn.cursor()
    
    # Daily performance log
    cur.execute('''
        CREATE TABLE IF NOT EXISTS daily_performance (
            date TEXT PRIMARY KEY,
            consensus_won INTEGER DEFAULT 0,
            consensus_lost INTEGER DEFAULT 0,
            elite_won INTEGER DEFAULT 0,
            elite_lost INTEGER DEFAULT 0,
            legendary_won INTEGER DEFAULT 0,
            legendary_lost INTEGER DEFAULT 0,
            notes TEXT
        )
    ''')
    
    # Trade log for our actual trades
    cur.execute('''
        CREATE TABLE IF NOT EXISTS trade_log (
            id INTEGER PRIMARY KEY,
            date TEXT,
            market_title TEXT,
            side TEXT,
            entry_price REAL,
            strategy TEXT,
            signal_source TEXT,
            outcome TEXT,
            pnl REAL,
            notes TEXT,
            created_at TEXT
        )
    ''')
    
    conn.commit()


def record_daily_performance(conn):
    """Record today's performance snapshot."""
    cur = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Get consensus performance
    cur.execute('''
        SELECT 
            SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as lost
        FROM consensus_picks
        WHERE outcome IN ('won', 'lost')
    ''')
    consensus = cur.fetchone()
    
    # Get elite performance
    cur.execute('''
        SELECT 
            SUM(CASE WHEN p.outcome='won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN p.outcome='lost' THEN 1 ELSE 0 END) as lost
        FROM whale_positions p
        JOIN elite_whales e ON p.address = e.address
        WHERE p.outcome IN ('won', 'lost')
    ''')
    elite = cur.fetchone()
    
    # Get legendary performance
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
    
    cur.execute('''
        INSERT OR REPLACE INTO daily_performance 
        (date, consensus_won, consensus_lost, elite_won, elite_lost, legendary_won, legendary_lost)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        today,
        consensus[0] or 0, consensus[1] or 0,
        elite[0] or 0, elite[1] or 0,
        legendary[0] or 0, legendary[1] or 0
    ))
    
    conn.commit()
    return {
        'date': today,
        'consensus': {'won': consensus[0] or 0, 'lost': consensus[1] or 0},
        'elite': {'won': elite[0] or 0, 'lost': elite[1] or 0},
        'legendary': {'won': legendary[0] or 0, 'lost': legendary[1] or 0}
    }


def get_performance_history(conn, days=7):
    """Get performance history."""
    cur = conn.cursor()
    
    cur.execute('''
        SELECT * FROM daily_performance
        ORDER BY date DESC
        LIMIT ?
    ''', (days,))
    
    return cur.fetchall()


def calculate_win_rates(won, lost):
    """Calculate win rate percentage."""
    total = won + lost
    return won / total * 100 if total > 0 else 0


def print_performance_report(conn):
    """Print comprehensive performance report."""
    print('=' * 70)
    print('PERFORMANCE TRACKER')
    print('=' * 70)
    
    # Record today's performance
    today = record_daily_performance(conn)
    
    # Current stats
    print('\n📊 CURRENT PERFORMANCE')
    print('-' * 50)
    
    strategies = [
        ('Consensus', today['consensus']),
        ('Elite (90%+)', today['elite']),
        ('Legendary (100%)', today['legendary'])
    ]
    
    print(f'{"Strategy":<25} {"W/L":<12} {"Win Rate":<10} {"vs Consensus"}')
    print('-' * 60)
    
    consensus_wr = calculate_win_rates(today['consensus']['won'], today['consensus']['lost'])
    
    for name, data in strategies:
        wr = calculate_win_rates(data['won'], data['lost'])
        diff = wr - consensus_wr
        diff_str = f"+{diff:.1f}%" if diff > 0 else f"{diff:.1f}%"
        print(f"{name:<25} {data['won']}/{data['lost']:<8} {wr:.1f}%      {diff_str if name != 'Consensus' else 'baseline'}")
    
    # Historical trend (if available)
    history = get_performance_history(conn)
    if len(history) > 1:
        print('\n📈 PERFORMANCE TREND (Last 7 days)')
        print('-' * 50)
        print(f'{"Date":<12} {"Cons WR":<10} {"Elite WR":<10} {"Legend WR"}')
        for row in history:
            date, c_won, c_lost, e_won, e_lost, l_won, l_lost, notes = row
            c_wr = calculate_win_rates(c_won, c_lost)
            e_wr = calculate_win_rates(e_won, e_lost)
            l_wr = calculate_win_rates(l_won, l_lost)
            print(f"{date:<12} {c_wr:<10.1f} {e_wr:<10.1f} {l_wr:.1f}")
    
    # Strategy comparison
    print('\n🎯 STRATEGY COMPARISON')
    print('-' * 50)
    elite_improvement = calculate_win_rates(today['elite']['won'], today['elite']['lost']) - consensus_wr
    legendary_improvement = calculate_win_rates(today['legendary']['won'], today['legendary']['lost']) - consensus_wr
    
    print(f"Switching to Elite:     +{elite_improvement:.1f}% win rate improvement")
    print(f"Switching to Legendary: +{legendary_improvement:.1f}% win rate improvement")
    
    # Sample size
    print('\n📏 SAMPLE SIZE')
    print('-' * 50)
    print(f"Consensus trades:  {today['consensus']['won'] + today['consensus']['lost']}")
    print(f"Elite trades:      {today['elite']['won'] + today['elite']['lost']}")
    print(f"Legendary trades:  {today['legendary']['won'] + today['legendary']['lost']}")


def main():
    conn = sqlite3.connect(DB_PATH)
    setup_tracking_tables(conn)
    print_performance_report(conn)
    conn.close()


if __name__ == '__main__':
    main()
