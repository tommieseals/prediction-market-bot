#!/usr/bin/env python3
import sqlite3
import json
from pathlib import Path

# Check our trading history
db_path = Path("data/whale_hunter.db")
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

# Check tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

# Check trade_signals for Lakers/Pistons
if 'trade_signals' in tables:
    cur.execute("PRAGMA table_info(trade_signals)")
    cols = [r[1] for r in cur.fetchall()]
    print("trade_signals columns:", cols)
    
    cur.execute("""
        SELECT * FROM trade_signals 
        WHERE LOWER(market_title) LIKE '%lakers%' OR LOWER(market_title) LIKE '%pistons%'
        ORDER BY created_at DESC LIMIT 10
    """)
    rows = cur.fetchall()
    print(f"\nFound {len(rows)} Lakers/Pistons trade signals:")
    for r in rows:
        print(r)

# Also check predictions log
pred_file = Path("whale_hunter_predictions.jsonl")
if pred_file.exists():
    print("\n\nPredictions log:")
    with open(pred_file) as f:
        for line in f:
            if 'lakers' in line.lower() or 'pistons' in line.lower():
                print(line.strip())

conn.close()
