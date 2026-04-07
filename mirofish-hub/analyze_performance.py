import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print("=" * 60)
print("CONSENSUS PICKS PERFORMANCE ANALYSIS")
print("=" * 60)

# Overall performance
cur.execute('''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN outcome = 'WON' THEN 1 ELSE 0 END) as won,
        SUM(CASE WHEN outcome = 'LOST' THEN 1 ELSE 0 END) as lost,
        SUM(CASE WHEN outcome IS NULL OR outcome = '' OR outcome = 'PENDING' THEN 1 ELSE 0 END) as pending
    FROM consensus_picks
''')
row = cur.fetchone()
total, won, lost, pending = row
resolved = won + lost
print(f"\n📊 OVERALL STATS")
print(f"Total Picks: {total}")
print(f"Won: {won} | Lost: {lost} | Pending: {pending}")
if resolved > 0:
    win_rate = won / resolved * 100
    print(f"Win Rate: {win_rate:.1f}% ({won}/{resolved} resolved)")

# By whale count (do more whales = better?)
print(f"\n🐋 BY WHALE COUNT")
cur.execute('''
    SELECT 
        whale_count,
        COUNT(*) as total,
        SUM(CASE WHEN outcome = 'WON' THEN 1 ELSE 0 END) as won,
        SUM(CASE WHEN outcome = 'LOST' THEN 1 ELSE 0 END) as lost
    FROM consensus_picks
    WHERE outcome IN ('WON', 'LOST')
    GROUP BY whale_count
    ORDER BY whale_count
''')
for row in cur.fetchall():
    wc, total, won, lost = row
    wr = won/(won+lost)*100 if (won+lost)>0 else 0
    print(f"  {wc} whales: {won}W/{lost}L ({wr:.0f}%)")

# By side (YES vs NO)
print(f"\n📈 BY SIDE")
cur.execute('''
    SELECT 
        side,
        COUNT(*) as total,
        SUM(CASE WHEN outcome = 'WON' THEN 1 ELSE 0 END) as won,
        SUM(CASE WHEN outcome = 'LOST' THEN 1 ELSE 0 END) as lost
    FROM consensus_picks
    WHERE outcome IN ('WON', 'LOST')
    GROUP BY side
''')
for row in cur.fetchall():
    side, total, won, lost = row
    wr = won/(won+lost)*100 if (won+lost)>0 else 0
    print(f"  {side}: {won}W/{lost}L ({wr:.0f}%)")

# By confidence level
print(f"\n🎯 BY CONFIDENCE")
cur.execute('''
    SELECT 
        CASE 
            WHEN confidence >= 0.9 THEN 'Very High (90%+)'
            WHEN confidence >= 0.8 THEN 'High (80-90%)'
            WHEN confidence >= 0.7 THEN 'Medium (70-80%)'
            ELSE 'Low (<70%)'
        END as conf_level,
        COUNT(*) as total,
        SUM(CASE WHEN outcome = 'WON' THEN 1 ELSE 0 END) as won,
        SUM(CASE WHEN outcome = 'LOST' THEN 1 ELSE 0 END) as lost
    FROM consensus_picks
    WHERE outcome IN ('WON', 'LOST')
    GROUP BY conf_level
    ORDER BY conf_level DESC
''')
for row in cur.fetchall():
    conf, total, won, lost = row
    wr = won/(won+lost)*100 if (won+lost)>0 else 0
    print(f"  {conf}: {won}W/{lost}L ({wr:.0f}%)")

# Recent losses - what went wrong?
print(f"\n❌ RECENT LOSSES (Last 10)")
cur.execute('''
    SELECT market_title, side, confidence, whale_count, avg_entry_price, created_at
    FROM consensus_picks
    WHERE outcome = 'LOST'
    ORDER BY created_at DESC
    LIMIT 10
''')
for row in cur.fetchall():
    title = row[0][:55] if row[0] else "Unknown"
    print(f"  • {title}...")
    print(f"    {row[1]} @ {row[4]:.2f} | {row[2]:.0%} conf | {row[3]} whales")

# Recent wins - what worked?
print(f"\n✅ RECENT WINS (Last 10)")
cur.execute('''
    SELECT market_title, side, confidence, whale_count, avg_entry_price, created_at
    FROM consensus_picks
    WHERE outcome = 'WON'
    ORDER BY created_at DESC
    LIMIT 10
''')
for row in cur.fetchall():
    title = row[0][:55] if row[0] else "Unknown"
    print(f"  • {title}...")
    print(f"    {row[1]} @ {row[4]:.2f} | {row[2]:.0%} conf | {row[3]} whales")

conn.close()
