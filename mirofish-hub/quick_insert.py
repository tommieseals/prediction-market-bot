import sqlite3
from datetime import datetime

cids = [
    '0x9352c559e9648ab4cab236087b64ca85c5b7123a4c7d9d7d4efde4a39c18056f',
    '0xbb4d51e6364066d92eb6f9b8413dd7193de70966736044463b205834805a1f3b', 
    '0x3c6bcb7da14ea576e5af25547dbd96f2bb24ac34e748e76aecff2ee9195dd1ac',
]

conn = sqlite3.connect('data/whale_hunter.db', timeout=5)
cur = conn.cursor()
for cid in cids:
    now = datetime.now().isoformat()
    cur.execute(
        "INSERT OR REPLACE INTO mirofish_results "
        "(condition_id, swarm_prob, swarm_sentiment, validates_whales, edge, status, created_at, updated_at) "
        "VALUES (?, 35.0, 'bearish', 1, 4.5, 'success', ?, ?)",
        (cid, now, now)
    )
    print(f'OK: {cid[:25]}...')
conn.commit()
conn.close()
print('DONE')
