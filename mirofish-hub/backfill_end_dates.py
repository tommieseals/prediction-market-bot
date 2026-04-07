#!/usr/bin/env python3
"""
BACKFILL END_DATES — Populate missing end_dates from Polymarket API

9,003 of 10,298 positions have NULL end_date, which means the consensus
endpoint can't filter expired markets. This script:

1. Gets all unique condition_ids with missing end_dates
2. Queries Polymarket Gamma API for each market's endDate + closed status
3. Updates whale_positions with end_date
4. Marks already-closed markets as outcome='expired'

Usage:
    python backfill_end_dates.py              # Full backfill
    python backfill_end_dates.py --limit 100  # Only first 100
    python backfill_end_dates.py --stats      # Just show stats
"""

import argparse
import json
import sqlite3
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"
GAMMA_API = "https://gamma-api.polymarket.com"


def get_missing_end_date_markets(limit: int = None):
    """Get unique condition_ids that need end_date backfill."""
    conn = sqlite3.connect(str(DB_PATH))
    query = """
        SELECT condition_id,
               MIN(token_id) as token_id,
               COUNT(*) as position_count,
               MIN(market_title) as sample_title
        FROM whale_positions
        WHERE (end_date IS NULL OR end_date = '')
          AND outcome = 'pending'
        GROUP BY condition_id
        ORDER BY position_count DESC
    """
    if limit:
        query += f" LIMIT {limit}"
    rows = conn.execute(query).fetchall()
    conn.close()
    return rows


def lookup_market(token_id: str, condition_id: str):
    """Query Gamma API for market details."""
    try:
        # Primary: use token_id (most reliable)
        if token_id:
            resp = requests.get(
                f"{GAMMA_API}/markets",
                params={"clob_token_ids": token_id},
                timeout=15,
            )
            if resp.ok:
                data = resp.json()
                if data and isinstance(data, list) and len(data) > 0:
                    return data[0]

        # Fallback: condition_id
        if condition_id:
            resp = requests.get(
                f"{GAMMA_API}/markets",
                params={"condition_id": condition_id},
                timeout=15,
            )
            if resp.ok:
                data = resp.json()
                if data and isinstance(data, list) and len(data) > 0:
                    return data[0]

        return None
    except Exception as e:
        print(f"  API error: {e}")
        return None


def backfill(limit: int = None, dry_run: bool = False):
    """Main backfill routine."""
    markets = get_missing_end_date_markets(limit)
    print(f"Found {len(markets)} unique markets needing end_date backfill")

    if not markets:
        print("Nothing to backfill!")
        return

    updated = 0
    expired = 0
    errors = 0
    skipped = 0

    for i, (condition_id, token_id, pos_count, title) in enumerate(markets):
        if (i + 1) % 25 == 0:
            print(f"  Progress: {i+1}/{len(markets)} "
                  f"(updated={updated}, expired={expired}, errors={errors})")

        time.sleep(0.35)  # Rate limit ~3/sec

        market = lookup_market(token_id, condition_id)
        if not market:
            errors += 1
            continue

        end_date = market.get("endDate", "")
        is_closed = market.get("closed", False)

        if not end_date and not is_closed:
            skipped += 1
            continue

        if not dry_run:
            # Use a fresh connection per write to avoid DB lock contention
            # with the whale_api.py server
            try:
                conn = sqlite3.connect(str(DB_PATH), timeout=10)
                conn.execute("PRAGMA journal_mode=WAL")

                if end_date:
                    conn.execute(
                        "UPDATE whale_positions SET end_date = ? "
                        "WHERE condition_id = ? AND (end_date IS NULL OR end_date = '')",
                        (end_date, condition_id),
                    )
                    updated += 1

                if is_closed:
                    result = conn.execute(
                        "UPDATE whale_positions SET outcome = 'expired' "
                        "WHERE condition_id = ? AND outcome = 'pending'",
                        (condition_id,),
                    )
                    if result.rowcount > 0:
                        expired += result.rowcount

                conn.commit()
                conn.close()
            except sqlite3.OperationalError as e:
                if "locked" in str(e):
                    time.sleep(1)  # Back off and retry
                    try:
                        conn = sqlite3.connect(str(DB_PATH), timeout=10)
                        conn.execute("PRAGMA journal_mode=WAL")
                        if end_date:
                            conn.execute(
                                "UPDATE whale_positions SET end_date = ? "
                                "WHERE condition_id = ? AND (end_date IS NULL OR end_date = '')",
                                (end_date, condition_id),
                            )
                            updated += 1
                        if is_closed:
                            result = conn.execute(
                                "UPDATE whale_positions SET outcome = 'expired' "
                                "WHERE condition_id = ? AND outcome = 'pending'",
                                (condition_id,),
                            )
                            if result.rowcount > 0:
                                expired += result.rowcount
                        conn.commit()
                        conn.close()
                    except Exception:
                        errors += 1
                else:
                    errors += 1

    print(f"\nBackfill complete:")
    print(f"  Markets processed: {len(markets)}")
    print(f"  End dates set:     {updated}")
    print(f"  Positions expired: {expired}")
    print(f"  API errors:        {errors}")
    print(f"  Skipped (no data): {skipped}")


def show_stats():
    """Show current end_date coverage stats."""
    conn = sqlite3.connect(str(DB_PATH))

    total = conn.execute("SELECT COUNT(*) FROM whale_positions").fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM whale_positions WHERE outcome = 'pending'"
    ).fetchone()[0]
    with_date = conn.execute(
        "SELECT COUNT(*) FROM whale_positions "
        "WHERE end_date IS NOT NULL AND end_date != ''"
    ).fetchone()[0]
    without_date = conn.execute(
        "SELECT COUNT(*) FROM whale_positions "
        "WHERE end_date IS NULL OR end_date = ''"
    ).fetchone()[0]
    expired = conn.execute(
        "SELECT COUNT(*) FROM whale_positions WHERE outcome = 'expired'"
    ).fetchone()[0]
    stale = conn.execute(
        "SELECT COUNT(*) FROM whale_positions "
        "WHERE outcome = 'pending' AND end_date IS NOT NULL AND end_date != '' "
        "AND datetime(end_date) < datetime('now')"
    ).fetchone()[0]
    unique_markets = conn.execute(
        "SELECT COUNT(DISTINCT condition_id) FROM whale_positions "
        "WHERE outcome = 'pending' AND (end_date IS NULL OR end_date = '')"
    ).fetchone()[0]

    conn.close()

    print(f"{'='*50}")
    print("END_DATE COVERAGE STATS")
    print(f"{'='*50}")
    print(f"Total positions:       {total:,}")
    print(f"Pending:               {pending:,}")
    print(f"Expired:               {expired:,}")
    print(f"With end_date:         {with_date:,}")
    print(f"Without end_date:      {without_date:,}")
    print(f"Stale (past end_date): {stale:,}")
    print(f"Unique markets to fix: {unique_markets:,}")
    print(f"{'='*50}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill end_dates from Polymarket")
    parser.add_argument("--limit", type=int, help="Limit number of markets to process")
    parser.add_argument("--stats", action="store_true", help="Show stats only")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        show_stats()
        print()
        backfill(limit=args.limit, dry_run=args.dry_run)
        print()
        show_stats()
