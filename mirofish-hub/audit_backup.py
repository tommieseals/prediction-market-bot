import sqlite3
import os

print("=" * 60)
print("                DATABASE CONTENTS AUDIT")
print("=" * 60)

databases = [
    ("data/whale_hunter.db", "MAIN DATABASE"),
    ("data/orchestrator.db", "Orchestrator"),
    ("data/outcomes.db", "Outcomes"),
    ("data/pharma_signals.db", "Pharma Signals")
]

for db_path, label in databases:
    if not os.path.exists(db_path):
        print(f"\n{label}: NOT FOUND")
        continue
    
    size_kb = os.path.getsize(db_path) / 1024
    print(f"\n{label} ({db_path}) - {size_kb:.1f} KB")
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    
    for (table,) in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM [{table}]")
            count = cur.fetchone()[0]
            print(f"   {table}: {count} rows")
        except Exception as e:
            print(f"   {table}: ERROR - {e}")
    
    conn.close()

print("\n" + "=" * 60)
print("                BACKUP VERIFICATION")
print("=" * 60)

# Compare with backup
backup_base = "C:/Users/USER/Desktop/Whale_Project_Complete_2026-03-23/mirofish-hub"

for db_path, label in databases:
    backup_path = f"{backup_base}/{db_path}"
    orig_path = db_path
    
    if not os.path.exists(orig_path):
        continue
    
    orig_size = os.path.getsize(orig_path)
    
    if os.path.exists(backup_path):
        back_size = os.path.getsize(backup_path)
        match = "✓ EXACT MATCH" if orig_size == back_size else f"⚠ MISMATCH (orig: {orig_size}, backup: {back_size})"
    else:
        match = "✗ MISSING"
    
    print(f"{label}: {match}")
