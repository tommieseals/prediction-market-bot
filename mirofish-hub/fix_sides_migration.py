#!/usr/bin/env python3
"""
ONE-TIME MIGRATION: Fix side detection for all whale positions.

The original code used a price heuristic (entry > 0.5 = YES) which is WRONG.
The correct method is to look up the token_id against the market's clobTokenIds:
  clobTokenIds[0] = YES token
  clobTokenIds[1] = NO token

This script:
1. Looks up the actual side for every position via Gamma API
2. Updates the side column in whale_positions
3. Resets all outcomes to 'pending' so they can be re-resolved correctly
4. Resets whale tracked_bets/winning_bets/tracked_accuracy to 0
5. Adds a token_side_cache table for future lookups
"""

import sqlite3
import requests
import json
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"


def create_cache_table(conn):
    """Create token_side_cache table for future lookups."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS token_side_cache (
            token_id TEXT PRIMARY KEY,
            condition_id TEXT,
            side TEXT,
            cached_at TEXT
        )
    """)
    conn.commit()


def lookup_side_from_api(token_id):
    """Look up YES/NO side from Gamma API."""
    if not token_id:
        return None, []

    try:
        resp = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"clob_token_ids": token_id},
            timeout=15,
        )
        if not resp.ok:
            return None, []

        data = resp.json()
        if not data:
            return None, []

        market = data[0] if isinstance(data, list) else data
        clob_ids = market.get("clobTokenIds", [])
        if isinstance(clob_ids, str):
            try:
                clob_ids = json.loads(clob_ids)
            except Exception:
                clob_ids = []

        if len(clob_ids) >= 2:
            if token_id == clob_ids[0]:
                return "YES", clob_ids
            elif token_id == clob_ids[1]:
                return "NO", clob_ids

        return None, clob_ids

    except Exception as e:
        print(f"  API error for {token_id[:20]}: {e}")
        return None, []


def main():
    print("=" * 60)
    print("SIDE DETECTION MIGRATION")
    print("Fixing all whale positions with correct YES/NO sides")
    print("=" * 60)

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Create cache table
    create_cache_table(conn)

    # Get all positions with token_ids
    cur.execute("""
        SELECT id, market_title, side, entry_price, token_id, outcome
        FROM whale_positions
        WHERE token_id IS NOT NULL AND token_id != ''
        ORDER BY id
    """)
    positions = cur.fetchall()
    print(f"\nTotal positions to check: {len(positions)}")

    # Cache to avoid redundant API calls
    cache = {}  # token_id -> side
    fixed = 0
    correct = 0
    errors = 0
    from datetime import datetime
    now = datetime.now().isoformat()

    for i, (pid, title, old_side, price, token_id, outcome) in enumerate(positions):
        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(positions)}")

        # Check cache first
        if token_id in cache:
            actual_side = cache[token_id]
        else:
            actual_side, clob_ids = lookup_side_from_api(token_id)
            time.sleep(0.3)  # Rate limit

            if actual_side:
                cache[token_id] = actual_side
                # Cache both tokens from this market
                if len(clob_ids) >= 2:
                    cache[clob_ids[0]] = "YES"
                    cache[clob_ids[1]] = "NO"

                    # Also save to DB cache
                    for tid, s in [(clob_ids[0], "YES"), (clob_ids[1], "NO")]:
                        try:
                            cur.execute(
                                "INSERT OR REPLACE INTO token_side_cache VALUES (?,?,?,?)",
                                (tid, "", s, now)
                            )
                        except Exception:
                            pass

        if actual_side is None:
            errors += 1
            continue

        if actual_side != old_side:
            fixed += 1
            cur.execute(
                "UPDATE whale_positions SET side = ? WHERE id = ?",
                (actual_side, pid)
            )
            print(f"  FIXED #{pid}: {title[:40]} {old_side}->{actual_side} @{price:.4f}")
        else:
            correct += 1

    conn.commit()

    print(f"\n{'=' * 60}")
    print(f"SIDE FIX RESULTS:")
    print(f"  Correct: {correct}")
    print(f"  Fixed: {fixed}")
    print(f"  Errors: {errors}")
    print(f"  Cache entries: {len(cache)}")

    # Step 2: Reset ALL outcomes to pending
    print(f"\nResetting all outcomes to 'pending'...")
    cur.execute("""
        UPDATE whale_positions
        SET outcome = 'pending',
            resolved_at = NULL,
            actual_pnl = NULL,
            final_price = NULL
    """)
    affected = cur.rowcount
    print(f"  Reset {affected} positions to pending")

    # Step 3: Reset whale stats
    print(f"\nResetting whale tracked_bets/winning_bets/tracked_accuracy...")
    cur.execute("""
        UPDATE tracked_whales
        SET tracked_bets = 0,
            winning_bets = 0,
            tracked_accuracy = 0
    """)
    affected = cur.rowcount
    print(f"  Reset stats for {affected} whales")

    conn.commit()
    conn.close()

    print(f"\n{'=' * 60}")
    print(f"MIGRATION COMPLETE")
    print(f"  Next: run 'python whale_outcome_tracker.py --check' to re-resolve")
    print(f"  Then: run 'python whale_outcome_tracker.py --status' to see real stats")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
