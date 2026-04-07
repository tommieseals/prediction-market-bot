import sqlite3
import os

db_path = 'C:/Users/USER/clawd/mirofish-hub/data/whale_hunter.db'
if not os.path.exists(db_path):
    db_path = 'C:/Users/USER/clawd/mirofish-hub/whale_hunter.db'
if not os.path.exists(db_path):
    print(f"ERROR: Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Get existing indexes
cur.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY tbl_name")
existing = cur.fetchall()
print('=== EXISTING INDEXES ===')
for idx, tbl in existing:
    print(f'{tbl}: {idx}')

# Get table list
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cur.fetchall()]
print(f'\n=== TABLES ({len(tables)}) ===')
for t in tables:
    cur.execute(f'SELECT COUNT(*) FROM {t}')
    count = cur.fetchone()[0]
    print(f'{t}: {count:,} rows')

# Add indexes if they don't exist
print('\n=== ADDING INDEXES ===')

indexes_to_add = [
    ("idx_whale_positions_outcome", "whale_positions", "outcome"),
    ("idx_whale_positions_wallet", "whale_positions", "wallet_address"),
    ("idx_consensus_picks_created", "consensus_picks", "created_at"),
    ("idx_consensus_picks_outcome", "consensus_picks", "outcome"),
    ("idx_mirofish_results_market", "mirofish_results", "market_id"),
    ("idx_mirofish_results_created", "mirofish_results", "created_at"),
]

for idx_name, table, column in indexes_to_add:
    try:
        cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
        print(f'[OK] {idx_name} on {table}({column})')
    except Exception as e:
        print(f'[WARN] {idx_name}: {e}')

conn.commit()

# Vacuum to reclaim space
print('\n=== VACUUM ===')
conn.execute('VACUUM')
print('[OK] Database vacuumed')

conn.close()
print('\n=== OPTIMIZATION COMPLETE ===')
