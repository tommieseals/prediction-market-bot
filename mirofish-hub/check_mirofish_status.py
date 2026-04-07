#!/usr/bin/env python3
"""Check MiroFish validation status"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Check if mirofish_results table exists
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='mirofish_results'")
if cur.fetchone():
    print("[OK] mirofish_results table exists")
    cur.execute("SELECT COUNT(*) FROM mirofish_results")
    count = cur.fetchone()[0]
    print(f"  Entries: {count}")
    if count > 0:
        cur.execute("SELECT * FROM mirofish_results ORDER BY created_at DESC LIMIT 3")
        for row in cur.fetchall():
            print(f"  - {row}")
else:
    print("[MISSING] mirofish_results table DOES NOT EXIST")
    print("  Creating table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mirofish_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            condition_id TEXT,
            market_title TEXT,
            prediction TEXT,
            confidence REAL,
            sim_id TEXT,
            report_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    print("  [OK] Table created")

# Check consensus picks count
cur.execute("SELECT COUNT(*) FROM trade_signals WHERE signal_source LIKE '%consensus%'")
consensus_count = cur.fetchone()[0]
print(f"\nConsensus trade signals: {consensus_count}")

# Check pending positions that could be validated
cur.execute("""
    SELECT COUNT(*) FROM whale_positions 
    WHERE outcome = 'pending' 
    AND end_date > datetime('now')
""")
pending = cur.fetchone()[0]
print(f"Pending positions (live markets): {pending}")

conn.close()
print("\nDone!")
