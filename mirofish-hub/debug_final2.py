#!/usr/bin/env python3
"""Final debug v2 - with full traceback"""
import sys
import traceback
import sqlite3
from datetime import datetime

print("=" * 60)
print("FINAL DEBUG v2")
print("=" * 60)
sys.stdout.flush()

try:
    from whale_hunter_connector import (
        fetch_and_score_whales, rank_traders, detect_new_positions,
        MIN_ELITE_SCORE, MAX_INSIDER_FLAGS, _init_db
    )
    from polymarket_api import PolymarketAPI
    
    _init_db()
    api = PolymarketAPI(rate_limit=0.5)
    
    print("\n[1] Fetching 3 whales...")
    sys.stdout.flush()
    
    whales = fetch_and_score_whales(api, top_n=3)
    print(f"    Got {len(whales)} profiles")
    sys.stdout.flush()
    
    print("\n[2] Ranking...")
    sys.stdout.flush()
    
    ranked = rank_traders(whales, min_trades=5, min_elite_score=MIN_ELITE_SCORE,
                          max_insider_flags=MAX_INSIDER_FLAGS)
    print(f"    {len(ranked)} elite")
    sys.stdout.flush()
    
    print("\n[3] Detecting positions...")
    sys.stdout.flush()
    
    new_positions = detect_new_positions(api, ranked)
    print(f"    Detected {len(new_positions)} new")
    sys.stdout.flush()
    
    api.close()
    
    print("\n[4] DB check...")
    conn = sqlite3.connect('data/whale_hunter.db')
    cur = conn.cursor()
    cur.execute("SELECT MAX(detected_at) FROM whale_positions")
    latest = cur.fetchone()[0]
    print(f"    Latest: {latest}")
    
    cur.execute("SELECT COUNT(*) FROM whale_positions WHERE detected_at > datetime('now', '-5 minutes')")
    recent = cur.fetchone()[0]
    print(f"    Recent: {recent}")
    conn.close()
    
    print("\n" + "=" * 60)
    if recent > 0:
        print("SUCCESS!")
    else:
        print("FAILURE - No new positions added")
    print("=" * 60)
    
except Exception as e:
    print(f"\n!!! EXCEPTION: {type(e).__name__}: {e}")
    traceback.print_exc()
    sys.exit(1)
