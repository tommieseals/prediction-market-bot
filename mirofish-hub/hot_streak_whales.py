import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/whale_hunter.db')

print('=== WHALES ON HOT STREAKS ===\n')

# Get whales with high win rates from actual resolved positions
hot_whales = conn.execute('''
    SELECT 
        w.display_name,
        w.elite_score,
        w.pnl,
        COUNT(CASE WHEN p.outcome = 'won' THEN 1 END) as wins,
        COUNT(CASE WHEN p.outcome = 'lost' THEN 1 END) as losses,
        COUNT(CASE WHEN p.outcome IN ('won','lost') THEN 1 END) as total
    FROM tracked_whales w
    JOIN whale_positions p ON w.address = p.address
    WHERE w.elite_score >= 70
    GROUP BY w.address
    HAVING total >= 5
    ORDER BY 
        CAST(wins AS FLOAT) / NULLIF(total, 0) DESC,
        w.elite_score DESC
    LIMIT 10
''').fetchall()

for w in hot_whales:
    name, elite, pnl, wins, losses, total = w
    win_rate = (wins / total * 100) if total > 0 else 0
    print(f"HOT: {name}")
    print(f"   Elite: {elite:.1f} | Record: {wins}W-{losses}L ({win_rate:.0f}%) | PnL: ${pnl:,.0f}")
    
    # Get their pending positions
    positions = conn.execute('''
        SELECT market_title, side, entry_price, size_usd, end_date
        FROM whale_positions
        WHERE address IN (SELECT address FROM tracked_whales WHERE display_name = ?)
        AND outcome = 'pending'
        AND end_date > datetime('now')
        ORDER BY size_usd DESC
        LIMIT 5
    ''', (name,)).fetchall()
    
    if positions:
        print("   CURRENT BETS:")
        for p in positions:
            title, side, entry, size, end = p
            exp = end[:10] if end else 'N/A'
            print(f"      {side} @ ${entry:.2f} | ${size:,.0f} | {title[:35]}... | {exp}")
    else:
        print("   (No pending positions)")
    print()

conn.close()
