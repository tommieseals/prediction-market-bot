import sqlite3
import requests
from collections import Counter
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print("=" * 60)
print("WHALE HUNTER DATABASE DIAGNOSTIC")
print("=" * 60)

# 1. Table stats
print("\n1. TABLE SIZES")
for table in ['tracked_whales', 'whale_positions', 'consensus_picks', 'mirofish_results', 'token_side_cache']:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"   {table}: {count:,} rows")
    except sqlite3.OperationalError as e:  # H12 FIX: DB errors only
        print(f"   {table}: ERROR - {e}")

# 2. Sample condition_ids and verify against Polymarket
print("\n2. CONDITION_ID INTEGRITY CHECK")
cur.execute("""
    SELECT DISTINCT condition_id, market_title 
    FROM whale_positions 
    ORDER BY detected_at DESC 
    LIMIT 20
""")
results = cur.fetchall()

bad_mappings = []
good_mappings = []

for condition_id, market_title in results:
    try:
        r = requests.get(f'https://gamma-api.polymarket.com/markets?conditionId={condition_id}', timeout=15)
        markets = r.json()
        if markets:
            api_question = markets[0].get('question', 'UNKNOWN')
            # Check if titles match (fuzzy)
            db_words = set(market_title.lower().split())
            api_words = set(api_question.lower().split())
            overlap = len(db_words & api_words)
            if overlap < 2:  # Less than 2 words in common = bad mapping
                bad_mappings.append({
                    'db_title': market_title,
                    'api_title': api_question,
                    'condition_id': condition_id[:20] + '...'
                })
            else:
                good_mappings.append(market_title)
        else:
            bad_mappings.append({
                'db_title': market_title,
                'api_title': 'NOT FOUND ON API',
                'condition_id': condition_id[:20] + '...'
            })
    except Exception as e:
        print(f"   Error checking {market_title[:30]}: {e}")

print(f"\n   [OK] Good mappings: {len(good_mappings)}")
print(f"   [BAD] Bad mappings: {len(bad_mappings)}")

if bad_mappings:
    print("\n   BAD MAPPINGS FOUND:")
    for bm in bad_mappings[:10]:
        print(f"   - DB: {bm['db_title'][:50]}")
        print(f"     API: {bm['api_title'][:50]}")
        print(f"     Condition: {bm['condition_id']}")
        print()

# 3. Check token_id validity
print("\n3. TOKEN_ID SPOT CHECK (NBA games)")
cur.execute("""
    SELECT token_id, market_title, side
    FROM whale_positions 
    WHERE market_title LIKE '%Thunder%' OR market_title LIKE '%Celtics%' OR market_title LIKE '%Nuggets%'
    LIMIT 5
""")
for token_id, title, side in cur.fetchall():
    try:
        r = requests.get(f'https://clob.polymarket.com/book?token_id={token_id}', timeout=15)
        book = r.json()
        asks = book.get('asks', [])
        bids = book.get('bids', [])
        if asks or bids:
            best_ask = asks[0]['price'] if asks else 'N/A'
            best_bid = bids[0]['price'] if bids else 'N/A'
            print(f"   {title[:35]} ({side}): ask={best_ask} bid={best_bid}")
        else:
            print(f"   {title[:35]} ({side}): [EMPTY BOOK]")
    except Exception as e:
        print(f"   {title[:35]}: ERROR - {e}")

# 4. Check for duplicate/conflicting entries
print("\n4. DUPLICATE CONDITION_ID CHECK")
cur.execute("""
    SELECT market_title, COUNT(DISTINCT condition_id) as cid_count
    FROM whale_positions
    GROUP BY market_title
    HAVING cid_count > 1
    LIMIT 10
""")
dups = cur.fetchall()
if dups:
    print(f"   WARNING: Markets with multiple condition_ids:")
    for title, count in dups:
        print(f"   - {title}: {count} different condition_ids")
else:
    print("   [OK] No duplicate condition_ids per market")

# 5. Date range check
print("\n5. DATA FRESHNESS")
cur.execute("SELECT MIN(detected_at), MAX(detected_at) FROM whale_positions")
min_date, max_date = cur.fetchone()
print(f"   Oldest position: {min_date}")
print(f"   Newest position: {max_date}")

cur.execute("SELECT COUNT(*) FROM whale_positions WHERE detected_at > datetime('now', '-24 hours')")
recent = cur.fetchone()[0]
print(f"   Positions in last 24h: {recent}")

# 6. Where do condition_ids come from?
print("\n6. CONDITION_ID FORMAT ANALYSIS")
cur.execute("""
    SELECT 
        CASE 
            WHEN condition_id LIKE '0x%' THEN 'hex (0x...)'
            WHEN length(condition_id) > 60 THEN 'long numeric'
            ELSE 'other'
        END as format,
        COUNT(*) as count
    FROM whale_positions
    GROUP BY format
""")
for fmt, count in cur.fetchall():
    print(f"   {fmt}: {count:,}")

# 7. Check actual source of the issue
print("\n7. ROOT CAUSE ANALYSIS")
cur.execute("""
    SELECT market_title, condition_id, token_id, COUNT(*) as cnt
    FROM whale_positions 
    WHERE market_title LIKE '%Thunder%Celtics%'
    GROUP BY condition_id
""")
rows = cur.fetchall()
print(f"   Thunder vs Celtics entries: {len(rows)} unique condition_ids")
for title, cid, tid, cnt in rows:
    print(f"   - condition: {cid[:30]}...")
    print(f"     token: {tid[:30]}...")
    print(f"     count: {cnt}")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
