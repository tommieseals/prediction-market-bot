#!/usr/bin/env python3
"""Get whale report from database"""
import sqlite3
import json
import os

db_path = 'data/whale_hunter.db'

if not os.path.exists(db_path):
    print("Database not found, running fresh scan...")
    exit(1)

conn = sqlite3.connect(db_path, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# List tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cur.fetchall()]
print(f"Tables in DB: {tables}")

# Try to find whale data
if 'whale_positions' in tables:
    cur.execute("SELECT * FROM whale_positions LIMIT 5")
    for row in cur.fetchall():
        print(dict(row))
        
if 'predictions' in tables:
    cur.execute("SELECT * FROM predictions ORDER BY timestamp DESC LIMIT 10")
    print("\n=== RECENT PREDICTIONS ===")
    for row in cur.fetchall():
        print(dict(row))

conn.close()
