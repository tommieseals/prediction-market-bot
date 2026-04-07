"""
Manual FDA PDUFA Database Populator

Simple script to manually add upcoming FDA PDUFA dates to the database.
No MiroFish dependency - just direct database writes.

Usage:
    python populate_fda_database.py --add
    python populate_fda_database.py --list
    python populate_fda_database.py --clear
"""

import sqlite3
import argparse
from datetime import datetime

DB_PATH = 'C:/Users/USER/clawd/mirofish-hub/outcomes.db'

def create_table():
    """Create fda_catalysts table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS fda_catalysts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            company TEXT NOT NULL,
            drug TEXT NOT NULL,
            pdufa_date TEXT NOT NULL,
            base_probability REAL NOT NULL,
            therapeutic_area TEXT,
            priority_review INTEGER DEFAULT 0,
            orphan_drug INTEGER DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("[OK] Table 'fda_catalysts' ready")

def add_catalyst(ticker, company, drug, pdufa_date, base_prob, 
                 therapeutic_area="", priority_review=False, 
                 orphan_drug=False, notes=""):
    """Add a single FDA catalyst to the database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute('''
        INSERT INTO fda_catalysts 
        (ticker, company, drug, pdufa_date, base_probability, 
         therapeutic_area, priority_review, orphan_drug, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (ticker, company, drug, pdufa_date, base_prob,
          therapeutic_area, 1 if priority_review else 0,
          1 if orphan_drug else 0, notes))
    
    conn.commit()
    conn.close()
    print(f"[OK] Added: ${ticker} {drug} - PDUFA {pdufa_date} - {base_prob}% base")

def list_catalysts():
    """List all FDA catalysts in the database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute('''
        SELECT ticker, drug, pdufa_date, base_probability, 
               priority_review, orphan_drug, notes
        FROM fda_catalysts
        ORDER BY pdufa_date
    ''')
    
    catalysts = cur.fetchall()
    conn.close()
    
    if not catalysts:
        print("No FDA catalysts in database")
        return
    
    print(f"\n{'='*80}")
    print(f"FDA PDUFA Calendar ({len(catalysts)} entries)")
    print(f"{'='*80}\n")
    
    for ticker, drug, pdufa_date, base_prob, priority, orphan, notes in catalysts:
        # Calculate days until PDUFA
        pdufa_dt = datetime.strptime(pdufa_date, '%Y-%m-%d')
        days_out = (pdufa_dt - datetime.now()).days
        
        flags = []
        if priority:
            flags.append("Priority Review")
        if orphan:
            flags.append("Orphan Drug")
        
        print(f"${ticker} — {drug}")
        print(f"  PDUFA: {pdufa_date} (T-{days_out})")
        print(f"  Base: {base_prob}%")
        if flags:
            print(f"  Flags: {', '.join(flags)}")
        if notes:
            print(f"  Notes: {notes}")
        print()

def clear_all():
    """Clear all FDA catalysts from the database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute('DELETE FROM fda_catalysts')
    conn.commit()
    count = cur.rowcount
    conn.close()
    
    print(f"[OK] Cleared {count} entries")

def add_sample_data():
    """Add sample upcoming PDUFA dates (April-May 2026)."""
    create_table()
    
    # These are placeholder examples - replace with real data
    samples = [
        ("RCKT", "Rocket Pharma", "KRESLADI (gene therapy)", "2026-04-15", 75, 
         "Orphan Disease", False, True, "Orphan drug designation"),
        
        ("LNTH", "Lantheus", "LNTH-2501 (imaging agent)", "2026-04-22", 68,
         "Oncology", True, False, "Priority Review - diagnostic imaging"),
        
        ("REPL", "Replimune", "RP1 + nivolumab (oncolytic virus)", "2026-04-28", 71,
         "Oncology", False, False, "Combo therapy with Opdivo"),
        
        ("MRK", "Merck", "KEYNOTE-905 (Keytruda expansion)", "2026-05-07", 55,
         "Oncology", False, False, "Mixed Phase 3 data"),
        
        ("BMY", "Bristol Myers", "Opdivo sBLA (new indication)", "2026-05-12", 80,
         "Oncology", False, False, "Supplemental BLA, high approval rate"),
    ]
    
    for sample in samples:
        add_catalyst(*sample)
    
    print(f"\n[OK] Added {len(samples)} sample catalysts")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FDA PDUFA Database Manager")
    parser.add_argument("--add", action="store_true", help="Add sample PDUFA dates")
    parser.add_argument("--list", action="store_true", help="List all catalysts")
    parser.add_argument("--clear", action="store_true", help="Clear all data")
    parser.add_argument("--create", action="store_true", help="Create table only")
    
    args = parser.parse_args()
    
    if args.create:
        create_table()
    elif args.add:
        add_sample_data()
        list_catalysts()
    elif args.list:
        list_catalysts()
    elif args.clear:
        clear_all()
    else:
        parser.print_help()
