import sqlite3
import requests
from datetime import datetime

print(f"Finding TONIGHT's games (Mar 24-25, 2026)...")
print(f"Current time: {datetime.now()}")

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Get games ending Mar 25 (tonight's games resolve tomorrow)
cur.execute("""
    SELECT market_title, 
           COUNT(*) as whale_count,
           SUM(CASE WHEN side='YES' THEN 1 ELSE 0 END) as yes_count,
           SUM(CASE WHEN side='NO' THEN 1 ELSE 0 END) as no_count,
           SUM(size_usd) as total_size,
           GROUP_CONCAT(DISTINCT token_id) as tokens
    FROM whale_positions 
    WHERE end_date LIKE '2026-03-25%'
    AND (market_title LIKE '%vs.%' OR market_title LIKE '%vs %')
    AND market_title NOT LIKE '%Spread%'
    AND market_title NOT LIKE '%O/U%'
    GROUP BY market_title
    HAVING whale_count >= 2
    ORDER BY total_size DESC
    LIMIT 15
""")

games = cur.fetchall()
print(f"\nFound {len(games)} games with whale activity:\n")

for title, wc, yes, no, size, tokens in games:
    consensus = "YES" if yes > no else "NO" if no > yes else "SPLIT"
    pct = max(yes, no) / wc * 100 if wc > 0 else 0
    
    # Get a token to check price
    token = tokens.split(',')[0] if tokens else ''
    price_str = ""
    if token:
        try:
            r = requests.get(f"https://clob.polymarket.com/book?token_id={token}", timeout=10)
            book = r.json()
            asks = book.get('asks', [])
            bids = book.get('bids', [])
            if asks and bids:
                ask = float(asks[0]['price'])
                bid = float(bids[0]['price'])
                if 0.05 < bid < 0.95:
                    price_str = f" | Ask ${ask:.2f} Bid ${bid:.2f}"
                else:
                    price_str = " | [RESOLVED/ILLIQUID]"
            else:
                price_str = " | [NO BOOK]"
        except (KeyError, ValueError, TypeError, requests.RequestException) as e:  # H12 FIX
            price_str = f" | [ERROR: {type(e).__name__}]"
    
    print(f"{title}")
    print(f"  Whales: {wc} ({yes}Y/{no}N) → {consensus} ({pct:.0f}%)")
    print(f"  Size: ${size:,.0f}{price_str}")
    print()
