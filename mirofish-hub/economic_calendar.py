#!/usr/bin/env python3
"""
Economic Calendar Connector
Tracks Fed events, CPI, jobs reports, and other market-moving catalysts.
"""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import requests

DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"

# Major economic events calendar (hardcoded for reliability)
# These are the BIG market movers
ECONOMIC_CALENDAR = [
    # FOMC Meetings 2026 (Fed interest rate decisions)
    {"date": "2026-01-29", "event": "FOMC Meeting", "importance": "HIGH", "category": "fed"},
    {"date": "2026-03-19", "event": "FOMC Meeting", "importance": "HIGH", "category": "fed"},
    {"date": "2026-05-07", "event": "FOMC Meeting", "importance": "HIGH", "category": "fed"},
    {"date": "2026-06-18", "event": "FOMC Meeting", "importance": "HIGH", "category": "fed"},
    {"date": "2026-07-29", "event": "FOMC Meeting", "importance": "HIGH", "category": "fed"},
    {"date": "2026-09-17", "event": "FOMC Meeting", "importance": "HIGH", "category": "fed"},
    {"date": "2026-11-05", "event": "FOMC Meeting", "importance": "HIGH", "category": "fed"},
    {"date": "2026-12-16", "event": "FOMC Meeting", "importance": "HIGH", "category": "fed"},
    
    # CPI Reports (inflation data - released ~10th-15th each month)
    {"date": "2026-03-12", "event": "CPI Report (Feb)", "importance": "HIGH", "category": "inflation"},
    {"date": "2026-04-10", "event": "CPI Report (Mar)", "importance": "HIGH", "category": "inflation"},
    {"date": "2026-05-13", "event": "CPI Report (Apr)", "importance": "HIGH", "category": "inflation"},
    {"date": "2026-06-11", "event": "CPI Report (May)", "importance": "HIGH", "category": "inflation"},
    
    # Jobs Reports (first Friday of each month)
    {"date": "2026-03-06", "event": "Jobs Report (Feb)", "importance": "HIGH", "category": "jobs"},
    {"date": "2026-04-03", "event": "Jobs Report (Mar)", "importance": "HIGH", "category": "jobs"},
    {"date": "2026-05-01", "event": "Jobs Report (Apr)", "importance": "HIGH", "category": "jobs"},
    {"date": "2026-06-05", "event": "Jobs Report (May)", "importance": "HIGH", "category": "jobs"},
    
    # GDP Reports
    {"date": "2026-03-27", "event": "GDP Q4 Final", "importance": "MEDIUM", "category": "gdp"},
    {"date": "2026-04-30", "event": "GDP Q1 Advance", "importance": "HIGH", "category": "gdp"},
    
    # EIA Oil Inventory (every Wednesday 10:30 AM ET)
    {"date": "2026-03-26", "event": "EIA Oil Inventory", "importance": "MEDIUM", "category": "commodities"},
    {"date": "2026-04-02", "event": "EIA Oil Inventory", "importance": "MEDIUM", "category": "commodities"},
    {"date": "2026-04-09", "event": "EIA Oil Inventory", "importance": "MEDIUM", "category": "commodities"},
]

def init_db():
    """Create economic_events table if not exists."""
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS economic_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            event TEXT NOT NULL,
            importance TEXT,
            category TEXT,
            polymarket_slug TEXT,
            our_prediction TEXT,
            actual_result TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, event)
        )
    """)
    conn.commit()
    conn.close()

def load_calendar():
    """Load economic calendar into database."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    
    for event in ECONOMIC_CALENDAR:
        try:
            cur.execute("""
                INSERT OR IGNORE INTO economic_events (date, event, importance, category)
                VALUES (?, ?, ?, ?)
            """, (event['date'], event['event'], event['importance'], event['category']))
        except Exception as e:
            print(f"Error inserting {event}: {e}")
    
    conn.commit()
    conn.close()
    print(f"Loaded {len(ECONOMIC_CALENDAR)} economic events")

def get_upcoming_events(days=14):
    """Get events in the next N days."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    today = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    
    cur.execute("""
        SELECT * FROM economic_events
        WHERE date BETWEEN ? AND ?
        ORDER BY date ASC
    """, (today, future))
    
    events = [dict(row) for row in cur.fetchall()]
    conn.close()
    return events

def find_polymarket_matches(event_name):
    """Search Polymarket for markets related to this event."""
    # Search our tracked positions for related markets
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Build search terms from event name
    terms = []
    if "FOMC" in event_name or "Fed" in event_name:
        terms = ["interest rate", "Fed", "FOMC", "Powell", "rate cut", "rate hike"]
    elif "CPI" in event_name or "inflation" in event_name.lower():
        terms = ["CPI", "inflation", "prices"]
    elif "Jobs" in event_name or "employment" in event_name.lower():
        terms = ["jobs", "unemployment", "employment", "payroll"]
    elif "Oil" in event_name:
        terms = ["oil", "crude", "WTI", "Brent", "petroleum"]
    elif "GDP" in event_name:
        terms = ["GDP", "growth", "recession"]
    
    matches = []
    for term in terms:
        cur.execute("""
            SELECT DISTINCT market_title, condition_id, 
                   COUNT(*) as whale_count,
                   SUM(size_usd) as total_size
            FROM whale_positions
            WHERE market_title LIKE ?
              AND outcome = 'pending'
            GROUP BY condition_id
            ORDER BY total_size DESC
            LIMIT 5
        """, (f"%{term}%",))
        
        for row in cur.fetchall():
            matches.append({
                "market": row['market_title'],
                "condition_id": row['condition_id'],
                "whale_count": row['whale_count'],
                "total_size": row['total_size']
            })
    
    conn.close()
    return matches[:10]  # Top 10 unique matches

def get_commodities_data():
    """Get current commodity prices and related Polymarket bets."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Find oil-related bets
    cur.execute("""
        SELECT 
            market_title,
            side,
            COUNT(DISTINCT address) as whale_count,
            SUM(size_usd) as total_size,
            AVG(entry_price) as avg_entry
        FROM whale_positions wp
        JOIN tracked_whales tw ON wp.address = tw.address
        WHERE (market_title LIKE '%Oil%' OR market_title LIKE '%Crude%' 
               OR market_title LIKE '%WTI%' OR market_title LIKE '%Brent%')
          AND outcome = 'pending'
          AND tw.elite_score >= 50
        GROUP BY condition_id, side
        ORDER BY total_size DESC
        LIMIT 20
    """)
    
    oil_bets = [dict(row) for row in cur.fetchall()]
    
    # Find other commodity bets (gold, silver, gas)
    cur.execute("""
        SELECT 
            market_title,
            side,
            COUNT(DISTINCT address) as whale_count,
            SUM(size_usd) as total_size
        FROM whale_positions wp
        JOIN tracked_whales tw ON wp.address = tw.address
        WHERE (market_title LIKE '%Gold%' OR market_title LIKE '%Silver%' 
               OR market_title LIKE '%Gas%' OR market_title LIKE '%Natural Gas%')
          AND outcome = 'pending'
          AND tw.elite_score >= 50
        GROUP BY condition_id, side
        ORDER BY total_size DESC
        LIMIT 10
    """)
    
    other_commodities = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    return {
        "oil": oil_bets,
        "other": other_commodities,
        "timestamp": datetime.now().isoformat()
    }

def print_calendar():
    """Print upcoming economic events with Polymarket matches."""
    events = get_upcoming_events(days=30)
    
    print("\n" + "="*70)
    print("ECONOMIC CALENDAR - Next 30 Days")
    print("="*70)
    
    for event in events:
        days_away = (datetime.strptime(event['date'], "%Y-%m-%d") - datetime.now()).days
        emoji = "[RED]" if event['importance'] == "HIGH" else "[YELLOW]" if event['importance'] == "MEDIUM" else "⚪"
        
        print(f"\n{emoji} {event['date']} ({days_away}d) - {event['event']}")
        print(f"   Category: {event['category']}")
        
        # Find related Polymarket bets
        matches = find_polymarket_matches(event['event'])
        if matches:
            print("   Related Polymarket bets:")
            for m in matches[:3]:
                print(f"     - {m['market'][:50]}... ({m['whale_count']} whales, ${m['total_size']:,.0f})")

def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--load":
        load_calendar()
    elif len(sys.argv) > 1 and sys.argv[1] == "--commodities":
        data = get_commodities_data()
        print("\nOIL BETS:")
        for bet in data['oil'][:10]:
            print(f"  {bet['side']:3} | {bet['whale_count']} whales | ${bet['total_size']:>10,.0f} | {bet['market_title'][:50]}")
    else:
        load_calendar()
        print_calendar()
        
        print("\n" + "="*70)
        print("COMMODITIES POSITIONS")
        print("="*70)
        data = get_commodities_data()
        print("\nOil bets:")
        for bet in data['oil'][:5]:
            print(f"  {bet['side']:3} | {bet['whale_count']} whales | ${bet['total_size']:>10,.0f} | {bet['market_title'][:50]}")

if __name__ == "__main__":
    main()
