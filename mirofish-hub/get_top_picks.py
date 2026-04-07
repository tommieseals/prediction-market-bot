import sqlite3

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

cur.execute('''
    SELECT 
        p.market_title,
        COUNT(*) as whale_count,
        SUM(CASE WHEN p.side = 'YES' THEN 1 ELSE 0 END) as yes_count,
        SUM(CASE WHEN p.side = 'NO' THEN 1 ELSE 0 END) as no_count,
        AVG(w.elite_score) as avg_elite,
        SUM(p.size_usd) as total_size,
        AVG(p.entry_price) as avg_entry,
        GROUP_CONCAT(w.display_name || ':' || p.side || ':' || CAST(w.elite_score AS INT), '|') as whale_details
    FROM whale_positions p
    JOIN tracked_whales w ON p.address = w.address
    WHERE p.outcome = 'pending'
        AND p.end_date > datetime('now')
    GROUP BY p.market_title
    HAVING COUNT(*) >= 2
    ORDER BY 
        CASE WHEN SUM(CASE WHEN p.side = 'YES' THEN 1 ELSE 0 END) = COUNT(*) 
             OR SUM(CASE WHEN p.side = 'NO' THEN 1 ELSE 0 END) = COUNT(*) 
             THEN 1 ELSE 0 END DESC,
        AVG(w.elite_score) DESC,
        SUM(p.size_usd) DESC
    LIMIT 10
''')

results = cur.fetchall()
for i, r in enumerate(results, 1):
    market, whales, yes_c, no_c, elite, size, entry, details = r
    consensus = 'YES' if yes_c > no_c else 'NO' if no_c > yes_c else 'SPLIT'
    pct = max(yes_c, no_c) / whales * 100 if whales > 0 else 0
    unanimous = 'UNANIMOUS' if pct == 100 else ''
    print(f"{i}. {market[:60]}")
    print(f"   {whales} whales: {yes_c}Y/{no_c}N ({pct:.0f}% {consensus}) {unanimous}")
    print(f"   Elite: {elite:.1f} | Size: ${size:,.0f} | Entry: ${entry:.2f}")
    if details:
        print(f"   Whales: {details[:80]}")
    print()

conn.close()
