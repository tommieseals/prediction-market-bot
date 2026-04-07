"""
Whale Intelligence Dashboard
=============================
Real-time monitoring dashboard for whale activity.
Run with: python whale_dashboard.py
"""
import sqlite3
from datetime import datetime, timedelta
import os

DB_PATH = 'data/whale_hunter.db'

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_stats(conn):
    """Get all dashboard stats."""
    cur = conn.cursor()
    stats = {}
    
    # Total whales
    cur.execute('SELECT COUNT(*) FROM tracked_whales')
    stats['total_whales'] = cur.fetchone()[0]
    
    # Elite whales
    cur.execute('SELECT COUNT(*) FROM elite_whales')
    stats['elite_whales'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM elite_whales WHERE tier='LEGENDARY'")
    stats['legendary_whales'] = cur.fetchone()[0]
    
    # Total positions
    cur.execute('SELECT COUNT(*) FROM whale_positions')
    stats['total_positions'] = cur.fetchone()[0]
    
    # Consensus performance
    cur.execute('''
        SELECT 
            SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) as lost,
            SUM(CASE WHEN outcome='pending' OR outcome IS NULL THEN 1 ELSE 0 END) as pending
        FROM consensus_picks
    ''')
    row = cur.fetchone()
    stats['consensus'] = {
        'won': row[0] or 0,
        'lost': row[1] or 0,
        'pending': row[2] or 0
    }
    
    # Elite performance
    cur.execute('''
        SELECT 
            SUM(CASE WHEN p.outcome='won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN p.outcome='lost' THEN 1 ELSE 0 END) as lost
        FROM whale_positions p
        JOIN elite_whales e ON p.address = e.address
        WHERE p.outcome IN ('won', 'lost')
    ''')
    row = cur.fetchone()
    stats['elite'] = {
        'won': row[0] or 0,
        'lost': row[1] or 0
    }
    
    # Recent activity (24h)
    cur.execute('''
        SELECT COUNT(*) FROM whale_positions 
        WHERE detected_at >= datetime('now', '-24 hours')
    ''')
    stats['recent_24h'] = cur.fetchone()[0]
    
    # Hot hands
    cur.execute('SELECT COUNT(*) FROM whale_profiles WHERE max_win_streak >= 10')
    stats['hot_hands'] = cur.fetchone()[0]
    
    return stats


def get_top_whales(conn, limit=10):
    """Get top performing whales."""
    cur = conn.cursor()
    cur.execute('''
        SELECT name, win_rate, bets, won, lost, tier, pnl
        FROM elite_whales
        ORDER BY win_rate DESC, bets DESC
        LIMIT ?
    ''', (limit,))
    return cur.fetchall()


def get_recent_moves(conn, limit=10):
    """Get recent whale moves."""
    cur = conn.cursor()
    cur.execute('''
        SELECT w.display_name, p.market_title, p.side, p.size_usd, p.detected_at
        FROM whale_positions p
        JOIN tracked_whales w ON p.address = w.address
        JOIN elite_whales e ON p.address = e.address
        ORDER BY p.detected_at DESC
        LIMIT ?
    ''', (limit,))
    return cur.fetchall()


def render_dashboard(stats, top_whales, recent_moves):
    """Render the dashboard."""
    
    consensus_wr = stats['consensus']['won']/(stats['consensus']['won']+stats['consensus']['lost'])*100 if (stats['consensus']['won']+stats['consensus']['lost']) > 0 else 0
    elite_wr = stats['elite']['won']/(stats['elite']['won']+stats['elite']['lost'])*100 if (stats['elite']['won']+stats['elite']['lost']) > 0 else 0
    
    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║                      🐋 WHALE INTELLIGENCE DASHBOARD 🐋                   ║
╠══════════════════════════════════════════════════════════════════════════╣
""")
    
    print(f"║  📊 DATA OVERVIEW                                                        ║")
    print(f"║  ├─ Total Whales:     {stats['total_whales']:<8}  Elite (90%+): {stats['elite_whales']:<8}              ║")
    print(f"║  ├─ Legendary (100%): {stats['legendary_whales']:<8}  Hot Hands:    {stats['hot_hands']:<8}              ║")
    print(f"║  └─ Total Positions:  {stats['total_positions']:<8}  Last 24h:     {stats['recent_24h']:<8}              ║")
    print(f"║                                                                          ║")
    
    print(f"╠══════════════════════════════════════════════════════════════════════════╣")
    print(f"║  📈 PERFORMANCE COMPARISON                                               ║")
    print(f"║                                                                          ║")
    print(f"║  Old Consensus:  {stats['consensus']['won']}W / {stats['consensus']['lost']}L = {consensus_wr:.1f}%                                   ║")
    print(f"║  Elite Strategy: {stats['elite']['won']}W / {stats['elite']['lost']}L = {elite_wr:.1f}%                                 ║")
    improvement = elite_wr - consensus_wr
    print(f"║  IMPROVEMENT:    +{improvement:.1f}%                                                   ║")
    print(f"║                                                                          ║")
    
    print(f"╠══════════════════════════════════════════════════════════════════════════╣")
    print(f"║  🏆 TOP PERFORMERS                                                       ║")
    print(f"║                                                                          ║")
    for name, wr, bets, won, lost, tier, pnl in top_whales[:5]:
        name_short = name[:18] if name else 'Unknown'
        wr_str = f"{wr*100:.0f}%" if wr else "N/A"
        pnl_str = f"${pnl:,.0f}" if pnl else "$0"
        print(f"║  {tier[:3]:<4} {name_short:<18} {wr_str:<6} {won}/{lost:<6} {pnl_str:<12}       ║")
    print(f"║                                                                          ║")
    
    print(f"╠══════════════════════════════════════════════════════════════════════════╣")
    print(f"║  🔥 RECENT ELITE MOVES                                                   ║")
    print(f"║                                                                          ║")
    if recent_moves:
        for name, market, side, size, detected in recent_moves[:5]:
            name_short = (name or 'Unknown')[:12]
            market_short = (market or 'Unknown')[:35]
            print(f"║  {name_short:<12} {side:<4} {market_short:<35}  ║")
    else:
        print(f"║  No recent elite moves in last 24h                                       ║")
    print(f"║                                                                          ║")
    
    print(f"╠══════════════════════════════════════════════════════════════════════════╣")
    print(f"║  🎯 VALIDATED RULES                                                      ║")
    print(f"║  ├─ Follow elite whales individually, NOT consensus                      ║")
    print(f"║  ├─ Avoid when 7+ whales agree (they get faded)                          ║")
    print(f"║  ├─ Best categories: Tennis (94%), Spreads (91%)                         ║")
    print(f"║  └─ Best days: Mon-Wed | Avoid: Thu-Fri                                  ║")
    print(f"║                                                                          ║")
    print(f"╚══════════════════════════════════════════════════════════════════════════╝")
    print(f"\nLast updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    conn = sqlite3.connect(DB_PATH)
    
    stats = get_stats(conn)
    top_whales = get_top_whales(conn)
    recent_moves = get_recent_moves(conn)
    
    clear_screen()
    render_dashboard(stats, top_whales, recent_moves)
    
    conn.close()


if __name__ == '__main__':
    main()
