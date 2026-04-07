#!/usr/bin/env python3
"""Test position detection directly"""
import sqlite3
from datetime import datetime
from polymarket_api import PolymarketAPI
# from whale_scorer import score_whale

print("=" * 60)
print("POSITION DETECTION DEBUG")
print("=" * 60)

# Connect to DB
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Get top 5 elite whales
cur.execute("""
    SELECT address, display_name, elite_score 
    FROM tracked_whales 
    WHERE elite_score >= 60 
    ORDER BY elite_score DESC 
    LIMIT 5
""")
top_whales = cur.fetchall()
print(f"\nTop 5 elite whales (score >= 60):")
for addr, name, score in top_whales:
    print(f"  {name or addr[:20]}: {score:.1f}")

# Initialize API
api = PolymarketAPI()

print("\n" + "-" * 60)
print("Checking open positions for each whale...")
print("-" * 60)

for addr, name, score in top_whales[:3]:  # Just top 3
    display = name or addr[:20]
    print(f"\n{display} (score={score:.1f}):")
    
    try:
        # Get open positions directly from API
        positions = api.get_positions(addr)
        open_pos = [p for p in positions if p.get('outcome') is None or p.get('outcome') == '']
        print(f"  Total positions from API: {len(positions)}")
        print(f"  Open positions: {len(open_pos)}")
        
        if open_pos:
            for p in open_pos[:2]:
                title = (p.get('title') or p.get('question') or '?')[:40]
                side = p.get('outcome') or p.get('side') or '?'
                size = p.get('size', 0)
                print(f"    - {title}... ({side})")
        
        # Check what we have in DB for this whale
        cur.execute("""
            SELECT COUNT(*) FROM whale_positions 
            WHERE address = ? AND outcome = 'pending'
        """, (addr,))
        db_pending = cur.fetchone()[0]
        print(f"  In DB (pending): {db_pending}")
        
    except Exception as e:
        print(f"  ERROR: {e}")

api.close()
conn.close()

print("\n" + "=" * 60)
print("DONE")
