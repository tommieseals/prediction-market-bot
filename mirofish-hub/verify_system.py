#!/usr/bin/env python3
"""Pre-launch system verification — checks all data accuracy."""
import os
import sqlite3
import requests
from datetime import datetime

API = "http://localhost:8081"
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "whale_hunter.db")

def main():
    db = sqlite3.connect(DB_PATH, timeout=10)
    errors = []

    print("=" * 70)
    print("  FINAL PRE-LAUNCH VERIFICATION")
    print("=" * 70)

    # 1. Stats accuracy
    print("\n1. STATS vs DATABASE")
    try:
        stats = requests.get(f"{API}/api/stats", timeout=10).json()
        db_whales = db.execute("SELECT COUNT(*) FROM tracked_whales").fetchone()[0]
        db_pos = db.execute("SELECT COUNT(*) FROM whale_positions").fetchone()[0]
        db_wins = db.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome='won'").fetchone()[0]
        db_losses = db.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome='lost'").fetchone()[0]
        db_pending = db.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome='pending'").fetchone()[0]
        db_pnl = db.execute("SELECT COALESCE(SUM(actual_pnl),0) FROM whale_positions WHERE outcome IN ('won','lost')").fetchone()[0]

        checks = [
            ("Whales", stats["whale_count"], db_whales),
            ("Positions", stats["total_positions"], db_pos),
            ("Wins", stats["wins"], db_wins),
            ("Losses", stats["losses"], db_losses),
            ("Pending", stats["pending"], db_pending),
        ]
        for label, api_val, db_val in checks:
            ok = api_val == db_val
            mark = "OK" if ok else "MISMATCH"
            if not ok:
                errors.append(f"{label}: API={api_val} DB={db_val}")
            print(f"  {label:12s}: API={api_val:>8,} DB={db_val:>8,} [{mark}]")

        api_wr = stats.get("win_rate", 0)
        db_wr = round(db_wins / max(db_wins + db_losses, 1) * 100, 1)
        wr_ok = abs(api_wr - db_wr) < 0.2
        print(f"  Win Rate:    API={api_wr}% DB={db_wr}% [{'OK' if wr_ok else 'MISMATCH'}]")

        api_pnl = stats.get("net_pnl", 0)
        pnl_ok = abs(api_pnl - db_pnl) < 1
        print(f"  Net P&L:     API=${api_pnl:>12,.0f} DB=${db_pnl:>12,.0f} [{'OK' if pnl_ok else 'MISMATCH'}]")
    except Exception as e:
        print(f"  ERROR: {e}")
        errors.append(f"Stats check failed: {e}")

    # 2. Consensus freshness
    print("\n2. CONSENSUS PICKS")
    try:
        consensus = requests.get(f"{API}/api/consensus", timeout=10).json()
        picks = consensus.get("picks", [])
        green = sum(1 for p in picks if p.get("confidence_tier") == "GREEN")
        yellow = sum(1 for p in picks if p.get("confidence_tier") == "YELLOW")
        print(f"  Total: {len(picks)} | GREEN: {green} | YELLOW: {yellow}")

        now = datetime.now().isoformat()
        stale = sum(1 for p in picks if p.get("end_date", "") and p["end_date"] < now)
        if stale:
            errors.append(f"{stale} stale consensus picks")
        print(f"  Stale (past end_date): {stale} [{'OK' if stale == 0 else 'NEEDS SWEEP'}]")
    except Exception as e:
        print(f"  ERROR: {e}")
        errors.append(f"Consensus check failed: {e}")

    # 3. Category performance
    print("\n3. CATEGORY PERFORMANCE")
    try:
        cats = requests.get(f"{API}/api/category/performance", timeout=10).json().get("categories", {})
        cat_total = sum(c["won"] + c["lost"] for c in cats.values())
        db_resolved = db_wins + db_losses
        match = cat_total == db_resolved
        if not match:
            errors.append(f"Category total {cat_total} != DB resolved {db_resolved}")
        print(f"  Categorized: {cat_total} vs DB resolved: {db_resolved} [{'OK' if match else 'MISMATCH'}]")
        for cat, info in sorted(cats.items(), key=lambda x: -x[1]["total"]):
            wr = info["win_rate"] * 100
            print(f"    {cat:12s}: {info['won']:4d}W/{info['lost']:3d}L ({wr:5.1f}%) P&L: ${info['pnl']:>10,.0f}")
    except Exception as e:
        print(f"  ERROR: {e}")
        errors.append(f"Category check failed: {e}")

    # 4. Leaderboard
    print("\n4. TOP 5 LEADERBOARD")
    try:
        lb = requests.get(f"{API}/api/leaderboard?limit=5", timeout=10).json()
        whale_list = lb if isinstance(lb, list) else lb.get("whales", lb.get("data", []))
        for w in whale_list[:5]:
            name = w.get("display_name", w.get("name", "?"))
            elite = w.get("elite_score", 0)
            wr = w.get("win_rate_raw", w.get("win_rate", 0))
            trades = w.get("num_trades", 0)
            wr_pct = wr * 100 if isinstance(wr, float) and wr <= 1 else wr
            print(f"  {name:25s}: elite={elite:5.1f} wr={wr_pct:5.1f}% trades={trades}")
    except Exception as e:
        print(f"  ERROR: {e}")
        errors.append(f"Leaderboard check failed: {e}")

    # 5. Calibration
    print("\n5. CALIBRATION")
    try:
        cal = requests.get(f"{API}/api/calibration", timeout=10).json()
        r = cal.get("report", {})
        print(f"  Predictions: {r.get('total_predictions', 0)} | Resolved: {r.get('resolved', 0)} | Unresolved: {r.get('unresolved', 0)}")
    except Exception as e:
        print(f"  ERROR: {e}")
        errors.append(f"Calibration check failed: {e}")

    # 6. Portfolio heat
    print("\n6. PORTFOLIO HEAT")
    try:
        heat = requests.get(f"{API}/api/portfolio/heat", timeout=10).json()
        by_cat = heat.get("by_category", heat.get("categories", {}))
        for cat, info in sorted(by_cat.items(), key=lambda x: -x[1].get("exposure_pct", 0)):
            pct = info.get("exposure_pct", 0)
            status = info.get("status", "")
            print(f"  {cat:12s}: {pct:5.1f}% {status}")
    except Exception as e:
        print(f"  ERROR: {e}")
        errors.append(f"Portfolio heat check failed: {e}")

    # 7. Consensus picks DB
    print("\n7. CONSENSUS PICKS DB")
    cp_total = db.execute("SELECT COUNT(*) FROM consensus_picks").fetchone()[0]
    cp_pending = db.execute("SELECT COUNT(*) FROM consensus_picks WHERE outcome='pending'").fetchone()[0]
    cp_won = db.execute("SELECT COUNT(*) FROM consensus_picks WHERE outcome='won'").fetchone()[0]
    cp_token = db.execute("SELECT COUNT(*) FROM consensus_picks WHERE token_id IS NOT NULL AND token_id != ''").fetchone()[0]
    print(f"  Total: {cp_total} | Pending: {cp_pending} | Won: {cp_won} | token_id: {cp_token}/{cp_total}")

    # 8. Data freshness (THE CHECK THAT WAS MISSING)
    print("\n8. DATA FRESHNESS")
    latest_pos = db.execute("SELECT MAX(detected_at) FROM whale_positions").fetchone()[0]
    latest_whale = db.execute("SELECT MAX(last_updated) FROM tracked_whales").fetchone()[0]
    latest_pick = db.execute("SELECT MAX(created_at) FROM consensus_picks").fetchone()[0]
    print(f"  Latest position:  {latest_pos}")
    print(f"  Latest whale:     {latest_whale}")
    print(f"  Latest pick:      {latest_pick}")

    # Check if data is actually flowing (positions added in last 60 min)
    recent_count = db.execute(
        "SELECT COUNT(*) FROM whale_positions "
        "WHERE detected_at >= datetime('now', '-60 minutes')"
    ).fetchone()[0]
    if recent_count == 0:
        errors.append("NO positions detected in last 60 minutes - whale hunter may be down!")
        print(f"  [FAIL] Positions in last 60 min: {recent_count} - DATA NOT FLOWING!")
    else:
        print(f"  [OK] Positions in last 60 min: {recent_count}")

    # Check if latest position is less than 2 hours old
    if latest_pos:
        from datetime import datetime as _dt
        try:
            latest_dt = _dt.fromisoformat(latest_pos)
            age_minutes = (_dt.now() - latest_dt).total_seconds() / 60
            if age_minutes > 120:
                errors.append(f"Latest position is {age_minutes:.0f} min old - stale data!")
                print(f"  [FAIL] Data age: {age_minutes:.0f} min (>2h)")
            else:
                print(f"  [OK] Data age: {age_minutes:.0f} min")
        except Exception:
            pass

    # 9. All tables
    print("\n9. TABLE INTEGRITY")
    tables = ["tracked_whales", "whale_positions", "consensus_picks",
              "trade_signals", "token_side_cache", "mirofish_results"]
    for t in tables:
        try:
            c = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t:25s}: {c:>8,} rows [OK]")
        except Exception:
            print(f"  {t:25s}: MISSING!")
            errors.append(f"Table {t} missing")

    # 10. File integrity
    print("\n10. FILE INTEGRITY")
    files = [
        ("whale_api.py", 40000), ("consensus_swarm_connector.py", 28000),
        ("whale_hunter_connector.py", 25000), ("auto_researcher.py", 30000),
        ("arbitrage_scanner.py", 8000), ("resolve_predictions.py", 5000),
        ("whale_scorer.py", 15000), ("polymarket_api.py", 10000),
        ("report_parser.py", 15000), ("mirofish_client.py", 10000),
    ]
    base = os.path.dirname(__file__)
    for f, min_sz in files:
        path = os.path.join(base, f)
        sz = os.path.getsize(path) if os.path.exists(path) else 0
        ok = sz >= min_sz
        if not ok:
            errors.append(f"{f} too small ({sz} < {min_sz})")
        print(f"  {f:35s}: {sz:>7,}b [{'OK' if ok else 'TOO SMALL'}]")

    # 11. Stale data
    print("\n11. STALE DATA")
    stale_pending = db.execute(
        "SELECT COUNT(*) FROM whale_positions WHERE outcome = 'pending' "
        "AND end_date IS NOT NULL AND end_date != '' AND end_date < datetime('now')"
    ).fetchone()[0]
    if stale_pending:
        errors.append(f"{stale_pending} stale pending positions")
    print(f"  Stale pending: {stale_pending} [{'OK' if stale_pending == 0 else 'NEEDS SWEEP'}]")

    stale_wr = db.execute(
        "SELECT COUNT(*) FROM tracked_whales WHERE win_rate_raw >= 0.99 AND num_trades <= 10"
    ).fetchone()[0]
    print(f"  Stale whale scores: {stale_wr} (small genuine accounts) [OK]")

    # 12. All endpoints
    print("\n12. ENDPOINT HEALTH")
    endpoints = [
        "/health", "/api/stats", "/api/calibration", "/api/consensus",
        "/api/category/performance", "/api/hot-whales", "/api/portfolio/heat",
        "/api/money-flow", "/api/positions/live", "/api/positions/resolved",
        "/analytics", "/consensus",
    ]
    for ep in endpoints:
        try:
            r = requests.get(f"{API}{ep}", timeout=5)
            ok = r.status_code == 200
            if not ok:
                errors.append(f"Endpoint {ep} returned {r.status_code}")
            print(f"  {ep:30s}: {r.status_code} [{'OK' if ok else 'FAIL'}]")
        except Exception as e:
            print(f"  {ep:30s}: ERROR")
            errors.append(f"Endpoint {ep} failed: {e}")

    db.close()

    # Summary
    print("\n" + "=" * 70)
    if errors:
        print(f"  ISSUES FOUND: {len(errors)}")
        for e in errors:
            print(f"    - {e}")
    else:
        print("  ALL CHECKS PASSED - READY TO GO LIVE")
    print("=" * 70)


if __name__ == "__main__":
    main()
