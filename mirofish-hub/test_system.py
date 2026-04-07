"""
System Test
===========
Verify all whale intelligence components work correctly.
"""
import sqlite3
import os
import sys

DB_PATH = 'data/whale_hunter.db'

def test_database():
    """Test database connectivity and tables."""
    print("Testing database...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    required_tables = [
        'tracked_whales',
        'whale_positions', 
        'whale_profiles',
        'elite_whales',
        'consensus_picks',
        'whale_watchlist'
    ]
    
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing = {r[0] for r in cur.fetchall()}
    
    for table in required_tables:
        if table in existing:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  ✅ {table}: {count} rows")
        else:
            print(f"  ❌ {table}: MISSING")
            return False
    
    conn.close()
    return True


def test_elite_whales():
    """Test elite whale data."""
    print("\nTesting elite whales...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM elite_whales WHERE tier='LEGENDARY'")
    legendary = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM elite_whales WHERE win_rate >= 0.90")
    elite = cur.fetchone()[0]
    
    print(f"  Legendary (100%): {legendary}")
    print(f"  Elite (90%+): {elite}")
    
    conn.close()
    return legendary >= 10 and elite >= 20


def test_performance_data():
    """Test performance calculations."""
    print("\nTesting performance data...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Consensus
    cur.execute('''
        SELECT 
            SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END),
            SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END)
        FROM consensus_picks WHERE outcome IN ('won', 'lost')
    ''')
    c = cur.fetchone()
    c_wr = c[0]/(c[0]+c[1])*100 if (c[0]+c[1]) > 0 else 0
    print(f"  Consensus: {c[0]}W/{c[1]}L = {c_wr:.1f}%")
    
    # Elite
    cur.execute('''
        SELECT 
            SUM(CASE WHEN p.outcome='won' THEN 1 ELSE 0 END),
            SUM(CASE WHEN p.outcome='lost' THEN 1 ELSE 0 END)
        FROM whale_positions p
        JOIN elite_whales e ON p.address = e.address
        WHERE p.outcome IN ('won', 'lost')
    ''')
    e = cur.fetchone()
    e_wr = e[0]/(e[0]+e[1])*100 if (e[0]+e[1]) > 0 else 0
    print(f"  Elite: {e[0]}W/{e[1]}L = {e_wr:.1f}%")
    
    conn.close()
    return e_wr > c_wr


def test_tools():
    """Test that all tools exist."""
    print("\nTesting tools...")
    
    tools = [
        'whale_dashboard.py',
        'elite_tracker.py',
        'elite_signals.py',
        'market_scanner.py',
        'morning_report.py',
        'whale_profiler.py',
        'whale_intel_v2.py',
        'category_analyzer.py',
        'performance_tracker.py',
        'elite_backtester.py',
        'whale_compare.py',
        'whale_watchlist.py',
        'improved_consensus.py',
        'strategy_improver.py'
    ]
    
    all_exist = True
    for tool in tools:
        if os.path.exists(tool):
            print(f"  ✅ {tool}")
        else:
            print(f"  ❌ {tool}: MISSING")
            all_exist = False
    
    return all_exist


def main():
    print("=" * 60)
    print("WHALE INTELLIGENCE SYSTEM TEST")
    print("=" * 60)
    
    results = []
    
    results.append(("Database", test_database()))
    results.append(("Elite Whales", test_elite_whales()))
    results.append(("Performance", test_performance_data()))
    results.append(("Tools", test_tools()))
    
    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    
    all_pass = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_pass = False
    
    print()
    if all_pass:
        print("🎉 ALL TESTS PASSED - System is ready!")
        return 0
    else:
        print("⚠️ SOME TESTS FAILED - Check issues above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
