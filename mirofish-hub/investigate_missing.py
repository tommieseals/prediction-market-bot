#!/usr/bin/env python3
"""
Deep investigation of missing consensus picks.
Markets from screenshots:
1. Spread: Nuggets (-5.5) - 4 whales, 50% NO, Elite 58
2. Thunder vs. Celtics - 4 whales, 75% YES, Elite 59.6
3. Magic vs. Cavaliers: O/U 229.5 - 5 whales, 80% NO, Elite 68.2
"""
import sqlite3
from datetime import datetime
import json

DB_PATH = 'C:/Users/USER/clawd/mirofish-hub/data/whale_hunter.db'
c = sqlite3.connect(DB_PATH)
c.row_factory = sqlite3.Row

print("=" * 70)
print("DEEP INVESTIGATION: MISSING CONSENSUS PICKS")
print("=" * 70)
print(f"Time: {datetime.now()}")
print()

# Markets to investigate
markets = [
    "Nuggets",
    "Thunder vs. Celtics", 
    "Magic vs. Cavaliers"
]

# 1. CHECK CONSENSUS_PICKS TABLE
print("\n" + "=" * 70)
print("1. CONSENSUS_PICKS TABLE")
print("=" * 70)

for market in markets:
    picks = c.execute("""
        SELECT id, market_title, side, confidence, whale_count, outcome, end_date, created_at
        FROM consensus_picks 
        WHERE market_title LIKE ?
        ORDER BY created_at DESC
        LIMIT 5
    """, (f"%{market}%",)).fetchall()
    
    print(f"\n### {market} ###")
    if picks:
        for p in picks:
            print(f"  ID: {p['id']}")
            print(f"  Title: {p['market_title']}")
            print(f"  Side: {p['side']} | Confidence: {p['confidence']}%")
            print(f"  Whales: {p['whale_count']} | Outcome: {p['outcome']}")
            print(f"  End: {p['end_date']} | Created: {p['created_at']}")
            print()
    else:
        print("  NOT FOUND IN CONSENSUS_PICKS!")

# 2. CHECK WHALE_POSITIONS TABLE
print("\n" + "=" * 70)
print("2. WHALE_POSITIONS TABLE")
print("=" * 70)

for market in markets:
    positions = c.execute("""
        SELECT id, address, market_title, side, size_usd, entry_price, outcome, end_date, detected_at
        FROM whale_positions 
        WHERE market_title LIKE ?
        ORDER BY detected_at DESC
        LIMIT 10
    """, (f"%{market}%",)).fetchall()
    
    print(f"\n### {market} ###")
    if positions:
        yes_count = sum(1 for p in positions if p['side'] == 'YES')
        no_count = sum(1 for p in positions if p['side'] == 'NO')
        total_size = sum(p['size_usd'] or 0 for p in positions)
        print(f"  Positions: {len(positions)} ({yes_count}Y / {no_count}N)")
        print(f"  Total Size: ${total_size:,.2f}")
        for p in positions[:5]:
            whale_short = p['address'][:12] + "..."
            print(f"    {whale_short} | {p['side']} @ ${p['entry_price']:.2f} | ${p['size_usd']:,.0f} | {p['outcome']} | end:{p['end_date']}")
    else:
        print("  NOT FOUND IN WHALE_POSITIONS!")

# 3. CHECK END_DATES AND EXPIRY LOGIC
print("\n" + "=" * 70)
print("3. END DATE ANALYSIS")
print("=" * 70)

for market in markets:
    result = c.execute("""
        SELECT DISTINCT end_date, outcome
        FROM whale_positions 
        WHERE market_title LIKE ?
    """, (f"%{market}%",)).fetchall()
    
    print(f"\n### {market} ###")
    for r in result:
        end_date = r['end_date']
        outcome = r['outcome']
        print(f"  End Date: {end_date} | Outcome: {outcome}")
        
        # Check if end_date is in the past
        if end_date:
            try:
                if 'T' in end_date:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                else:
                    end_dt = datetime.fromisoformat(end_date)
                now = datetime.now(end_dt.tzinfo) if end_dt.tzinfo else datetime.now()
                if end_dt < now:
                    print(f"  ⚠️ END DATE IN THE PAST!")
            except Exception as e:
                print(f"  Parse error: {e}")

# 4. CHECK IF POSITIONS WERE MARKED EXPIRED/RESOLVED
print("\n" + "=" * 70)
print("4. OUTCOME STATUS BREAKDOWN")
print("=" * 70)

outcome_stats = c.execute("""
    SELECT outcome, COUNT(*) as cnt
    FROM whale_positions
    WHERE market_title LIKE '%Nuggets%' 
       OR market_title LIKE '%Thunder vs. Celtics%'
       OR market_title LIKE '%Magic vs. Cavaliers%'
    GROUP BY outcome
""").fetchall()

for o in outcome_stats:
    print(f"  {o['outcome'] or 'NULL'}: {o['cnt']} positions")

# 5. CHECK RECENT POSITION UPDATES (deletions/changes)
print("\n" + "=" * 70)
print("5. RECENT CHANGES TO THESE MARKETS")
print("=" * 70)

recent = c.execute("""
    SELECT market_title, side, outcome, detected_at, end_date
    FROM whale_positions
    WHERE (market_title LIKE '%Nuggets%' 
       OR market_title LIKE '%Thunder vs. Celtics%'
       OR market_title LIKE '%Magic vs. Cavaliers%')
    ORDER BY detected_at DESC
    LIMIT 15
""").fetchall()

for r in recent:
    print(f"  {r['detected_at']} | {r['market_title'][:40]} | {r['side']} | {r['outcome']}")

# 6. CHECK CONSENSUS API LOGIC
print("\n" + "=" * 70)
print("6. CONSENSUS FILTERING LOGIC CHECK")
print("=" * 70)

# Check what consensus would currently return
all_pending = c.execute("""
    SELECT market_title, whale_count, confidence, outcome, end_date
    FROM consensus_picks
    WHERE outcome = 'pending'
    ORDER BY confidence DESC
    LIMIT 20
""").fetchall()

print(f"Total pending consensus picks: {len(all_pending)}")
print("\nTop pending picks:")
for p in all_pending[:10]:
    print(f"  {p['confidence']}% | {p['whale_count']} whales | {p['market_title'][:50]}")

# 7. SPECIFIC SEARCH FOR THE EXACT MARKETS
print("\n" + "=" * 70)
print("7. EXACT MARKET SEARCH")
print("=" * 70)

# Spread: Nuggets (-5.5)
nuggets_spread = c.execute("""
    SELECT * FROM whale_positions WHERE market_title LIKE '%Spread%Nuggets%5.5%'
""").fetchall()
print(f"Nuggets Spread (-5.5): {len(nuggets_spread)} positions found")

# Thunder vs Celtics (exact)
thunder = c.execute("""
    SELECT * FROM whale_positions WHERE market_title = 'Thunder vs. Celtics'
""").fetchall()
print(f"Thunder vs. Celtics (exact match): {len(thunder)} positions found")

# O/U 229.5
ou = c.execute("""
    SELECT * FROM whale_positions WHERE market_title LIKE '%O/U 229.5%'
""").fetchall()
print(f"O/U 229.5: {len(ou)} positions found")

# 8. CHECK FOR ANY FILTERING BY END_DATE IN API
print("\n" + "=" * 70)
print("8. API ENDPOINT FILTER CHECK")
print("=" * 70)

# Check what the API would return with live market filter
live_markets = c.execute("""
    SELECT DISTINCT market_title, end_date
    FROM whale_positions
    WHERE end_date > datetime('now')
      AND (market_title LIKE '%Nuggets%' 
           OR market_title LIKE '%Thunder vs. Celtics%'
           OR market_title LIKE '%Cavaliers%')
    ORDER BY end_date
""").fetchall()

print(f"Markets with end_date > now: {len(live_markets)}")
for m in live_markets:
    print(f"  {m['end_date']} | {m['market_title'][:50]}")

expired_markets = c.execute("""
    SELECT DISTINCT market_title, end_date
    FROM whale_positions
    WHERE end_date <= datetime('now')
      AND (market_title LIKE '%Nuggets%' 
           OR market_title LIKE '%Thunder vs. Celtics%'
           OR market_title LIKE '%Cavaliers%')
    ORDER BY end_date DESC
""").fetchall()

print(f"\nMarkets with end_date <= now (EXPIRED): {len(expired_markets)}")
for m in expired_markets[:10]:
    print(f"  {m['end_date']} | {m['market_title'][:50]}")

print("\n" + "=" * 70)
print("INVESTIGATION COMPLETE")
print("=" * 70)
