#!/usr/bin/env python3
"""Whale Analysis - Find patterns, insiders, and edges"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"

def analyze_whales():
    conn = sqlite3.connect(DB_PATH)
    
    print("=" * 60)
    print("WHALE INTELLIGENCE REPORT")
    print("=" * 60)
    
    # Basic stats
    row = conn.execute("SELECT COUNT(DISTINCT address) FROM whale_positions").fetchone()
    print(f"\nTotal addresss tracked: {row[0]}")
    
    row = conn.execute("SELECT COUNT(*) FROM whale_positions").fetchone()
    print(f"Total positions: {row[0]}")
    
    row = conn.execute("""
        SELECT 
            SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN outcome = 'lost' THEN 1 ELSE 0 END) as lost,
            SUM(CASE WHEN outcome = 'pending' THEN 1 ELSE 0 END) as pending
        FROM whale_positions
    """).fetchone()
    print(f"Outcomes: {row[0]} won, {row[1]} lost, {row[2]} pending")
    
    if row[0] and row[1]:
        overall_wr = 100 * row[0] / (row[0] + row[1])
        print(f"Overall win rate: {overall_wr:.1f}%")
    
    # Top performers (min 20 resolved trades)
    print("\n" + "=" * 60)
    print("TOP PERFORMERS (min 20 resolved trades)")
    print("=" * 60)
    rows = conn.execute("""
        SELECT address, 
               COUNT(*) as trades,
               SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) as wins,
               ROUND(100.0 * SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate
        FROM whale_positions 
        WHERE outcome IN ('won', 'lost')
        GROUP BY address 
        HAVING COUNT(*) >= 20
        ORDER BY win_rate DESC
        LIMIT 15
    """).fetchall()
    
    print(f"{'address':<15} {'Trades':>8} {'Wins':>8} {'WinRate':>10}")
    print("-" * 45)
    for w, t, wins, wr in rows:
        print(f"{w[:14]:<15} {t:>8} {wins:>8} {wr:>9.1f}%")
    
    # Potential insiders (concentrated positions)
    print("\n" + "=" * 60)
    print("POTENTIAL INSIDERS (Large concentrated bets)")
    print("=" * 60)
    rows = conn.execute("""
        SELECT address, market_title, size_usd, entry_price, side
        FROM whale_positions 
        WHERE size_usd > 5000 AND outcome = 'pending'
        ORDER BY size_usd DESC
        LIMIT 10
    """).fetchall()
    
    for w, m, s, p, side in rows:
        print(f"\n  address: {w[:20]}...")
        print(f"  market_title: {m[:50]}...")
        print(f"  Size: ${s:,.0f} | Side: {side} @ {p:.2f}")
    
    # Market category analysis
    print("\n" + "=" * 60)
    print("WIN RATE BY CATEGORY")
    print("=" * 60)
    rows = conn.execute("""
        SELECT category,
               COUNT(*) as total,
               SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) as wins,
               ROUND(100.0 * SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) / 
                     NULLIF(SUM(CASE WHEN outcome IN ('won','lost') THEN 1 ELSE 0 END), 0), 1) as wr
        FROM whale_positions
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category
        HAVING SUM(CASE WHEN outcome IN ('won','lost') THEN 1 ELSE 0 END) >= 10
        ORDER BY wr DESC
    """).fetchall()
    
    print(f"{'Category':<20} {'Total':>8} {'Wins':>8} {'WinRate':>10}")
    print("-" * 50)
    for cat, total, wins, wr in rows:
        if wr:
            print(f"{cat[:19]:<20} {total:>8} {wins:>8} {wr:>9.1f}%")
    
    # Whale clusters (similar positions)
    print("\n" + "=" * 60)
    print("WHALE CONSENSUS (Multiple whales same position)")
    print("=" * 60)
    rows = conn.execute("""
        SELECT market_title, side, COUNT(DISTINCT address) as whale_count, 
               AVG(entry_price) as avg_price, SUM(size_usd) as total_size
        FROM whale_positions
        WHERE outcome = 'pending'
        GROUP BY market_title, side
        HAVING whale_count >= 5
        ORDER BY whale_count DESC, total_size DESC
        LIMIT 10
    """).fetchall()
    
    for m, side, count, price, size in rows:
        print(f"\n  {m[:50]}...")
        print(f"  {count} whales | {side} @ {price:.2f} | Total: ${size:,.0f}")
    
    conn.close()

if __name__ == "__main__":
    analyze_whales()
