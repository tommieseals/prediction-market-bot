"""Quick whale hunter status check"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print("=== WHALE HUNTER STATUS ===")
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print()

# Whales
cur.execute('SELECT COUNT(*) FROM tracked_whales')
print(f"Whales tracked: {cur.fetchone()[0]}")

# Positions
cur.execute('SELECT COUNT(*) FROM whale_positions')
total_pos = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM whale_positions WHERE resolved_at IS NULL")
pending = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM whale_positions WHERE resolved_at IS NOT NULL AND actual_pnl > 0")
won = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM whale_positions WHERE resolved_at IS NOT NULL AND actual_pnl <= 0")
lost = cur.fetchone()[0]
print(f"Positions: {total_pos} total ({pending} pending, {won}W/{lost}L)")

# Consensus picks
cur.execute('SELECT COUNT(*) FROM consensus_picks')
total_picks = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM consensus_picks WHERE won IS NOT NULL')
resolved = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM consensus_picks WHERE won = 1')
wins = cur.fetchone()[0]
print(f"Consensus picks: {total_picks} ({resolved} resolved, {wins} wins)")

# Signals
cur.execute('SELECT COUNT(*) FROM trade_signals')
signals = cur.fetchone()[0]
print(f"Trade signals: {signals}")

# MiroFish results
cur.execute('SELECT COUNT(*) FROM mirofish_results')
mf_results = cur.fetchone()[0]
print(f"MiroFish validations: {mf_results}")

# Recent whale moves
print("\n=== RECENT WHALE MOVES (last 12h) ===")
cur.execute("""
    SELECT tw.display_name, wp.market_title, wp.side, wp.size_usd, wp.entry_price, wp.detected_at
    FROM whale_positions wp
    JOIN tracked_whales tw ON wp.address = tw.address
    WHERE wp.detected_at > datetime('now', '-12 hours')
    ORDER BY wp.detected_at DESC
    LIMIT 5
""")
rows = cur.fetchall()
if rows:
    for row in rows:
        username, title, side, size, price, ts = row
        title_short = (title[:35] + '...') if title and len(title) > 35 else (title or 'Unknown')
        size = size or 0
        price = price or 0
        print(f"  {username}: {side} ${size:.0f} @ {price:.2f} - {title_short}")
else:
    print("  No recent moves in last 12 hours")

# Top consensus picks
print("\n=== TOP CONSENSUS PICKS (pending) ===")
cur.execute("""
    SELECT market_title, whale_count, confidence, created_at
    FROM consensus_picks
    WHERE won IS NULL
    ORDER BY whale_count DESC, confidence DESC
    LIMIT 5
""")
rows = cur.fetchall()
if rows:
    for row in rows:
        title, wc, conf, created = row
        title_short = (title[:40] + '...') if title and len(title) > 40 else (title or 'Unknown')
        conf_pct = (conf or 0) / 100 if conf and conf > 1 else (conf or 0)
        print(f"  [{wc} whales, {conf}%] {title_short}")
else:
    print("  No pending picks")

conn.close()
