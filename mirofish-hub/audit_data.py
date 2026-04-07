#!/usr/bin/env python3
"""Full data audit for MiroFish pipeline"""
import sqlite3
import os
from datetime import datetime

def audit():
    print("=" * 60)
    print("MIROFISH PIPELINE DATA AUDIT")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    
    # Check whale_hunter.db
    wh_db = "data/whale_hunter.db"
    if os.path.exists(wh_db):
        conn = sqlite3.connect(wh_db)
        cur = conn.cursor()
        
        print("\n=== WHALE_HUNTER.DB ===")
        
        # All tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"Tables: {tables}")
        
        # Tracked whales
        cur.execute("SELECT COUNT(*) FROM tracked_whales")
        print(f"Tracked whales: {cur.fetchone()[0]}")
        
        # Positions by outcome
        print("\nPositions by outcome:")
        cur.execute("SELECT outcome, COUNT(*) FROM whale_positions GROUP BY outcome ORDER BY COUNT(*) DESC")
        for row in cur.fetchall():
            print(f"  {row[0] or 'NULL'}: {row[1]}")
        
        # Check for end_date column
        cur.execute("PRAGMA table_info(whale_positions)")
        cols = [r[1] for r in cur.fetchall()]
        print(f"\nend_date column exists: {'end_date' in cols}")
        
        # Pending positions with end_date
        if 'end_date' in cols:
            cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome='pending' AND end_date IS NOT NULL")
            print(f"Pending with end_date: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome='pending' AND end_date IS NULL")
            print(f"Pending without end_date: {cur.fetchone()[0]}")
        
        # Consensus picks
        if 'consensus_picks' in tables:
            print("\n=== CONSENSUS PICKS ===")
            cur.execute("PRAGMA table_info(consensus_picks)")
            cols = [r[1] for r in cur.fetchall()]
            print(f"Columns: {cols}")
            
            cur.execute("SELECT COUNT(*) FROM consensus_picks")
            print(f"Total picks: {cur.fetchone()[0]}")
            
            cur.execute("SELECT * FROM consensus_picks ORDER BY created_at DESC LIMIT 3")
            print("\nLatest 3 picks:")
            for row in cur.fetchall():
                print(f"  {row}")
        
        # MiroFish validations
        if 'mirofish_validations' in tables:
            print("\n=== MIROFISH VALIDATIONS ===")
            cur.execute("PRAGMA table_info(mirofish_validations)")
            cols = [r[1] for r in cur.fetchall()]
            print(f"Columns: {cols}")
            
            cur.execute("SELECT COUNT(*) FROM mirofish_validations")
            print(f"Total validations: {cur.fetchone()[0]}")
        else:
            print("\n[!] mirofish_validations table NOT FOUND")
        
        conn.close()
    else:
        print(f"[!] {wh_db} not found!")
    
    # Check orchestrator.db
    orch_db = "data/orchestrator.db"
    if os.path.exists(orch_db):
        print("\n=== ORCHESTRATOR.DB ===")
        conn = sqlite3.connect(orch_db)
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"Tables: {tables}")
        
        if 'connector_runs' in tables:
            cur.execute("SELECT connector, status, started_at, duration_sec FROM connector_runs ORDER BY started_at DESC LIMIT 5")
            print("\nRecent connector runs:")
            for row in cur.fetchall():
                dur = f"{row[3]:.0f}s" if row[3] else "N/A"
                print(f"  {row[0]}: {row[1]} @ {row[2]} ({dur})")
        
        conn.close()
    else:
        print(f"\n[!] {orch_db} not found!")
    
    # Check outcomes.db
    out_db = "outcomes.db"
    if os.path.exists(out_db):
        print("\n=== OUTCOMES.DB ===")
        conn = sqlite3.connect(out_db)
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"Tables: {tables}")
        
        conn.close()
    
    print("\n" + "=" * 60)
    print("AUDIT COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    audit()
