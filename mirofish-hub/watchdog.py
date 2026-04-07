#!/usr/bin/env python3
"""
Watchdog - Continuous health monitor for mirofish-hub.
Checks API health, data freshness, stale data, and DB accessibility.
Auto-fixes: restarts API if down, sweeps stale pending data.
Alerts to Telegram on repeated failures.
Includes: startup report, daily summary, DB backup, position archival.
"""
import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, date
from pathlib import Path

import requests

# --- Configuration ---
API_URL = "http://localhost:8081/health"
DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"
BACKUP_DIR = Path(__file__).parent / "data" / "backups"
CHECK_INTERVAL = 300  # 5 minutes
FRESHNESS_LIMIT_MIN = 60  # alert if latest detected_at older than this
FRESHNESS_CRITICAL_MIN = 120  # alert immediately if older than this
FAIL_THRESHOLD = 3  # consecutive failures before alerting
ARCHIVE_AGE_DAYS = 90  # archive positions older than this
MAX_BACKUPS = 7  # keep only this many backups
SCP_TARGET = "tommie@100.88.105.106:~/whale_backup/"

TELEGRAM_BOT_TOKEN = "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU"
TELEGRAM_CHAT_ID = "939543801"

# --- State tracking ---
fail_counts = {
    "api_health": 0,
    "data_freshness": 0,
    "stale_data": 0,
    "db_access": 0,
}

last_summary_date = None  # Track when we last sent a daily summary


def ts():
    """Current timestamp string for logging."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def send_telegram(message):
    """Send alert message to Telegram. Returns True on success."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, data=data, timeout=10)
        if resp.ok:
            print(f"[{ts()}] [OK] Telegram alert sent")
            return True
        else:
            print(f"[{ts()}] [FAIL] Telegram send failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"[{ts()}] [FAIL] Telegram send error: {e}")
        return False


def record_result(check_name, passed, message=""):
    """Track pass/fail counts and alert on repeated failures."""
    if passed:
        if fail_counts[check_name] > 0:
            print(f"[{ts()}] [OK] {check_name} recovered after {fail_counts[check_name]} failure(s)")
        fail_counts[check_name] = 0
    else:
        fail_counts[check_name] += 1
        count = fail_counts[check_name]
        print(f"[{ts()}] [FAIL] {check_name} failed ({count}/{FAIL_THRESHOLD})")
        if count >= FAIL_THRESHOLD:
            alert_msg = (
                f"<b>[WATCHDOG ALERT]</b>\n"
                f"Check: <b>{check_name}</b>\n"
                f"Failures: {count} consecutive\n"
                f"Detail: {message}\n"
                f"Time: {ts()}"
            )
            send_telegram(alert_msg)


# --- Check functions ---

def check_api_health():
    """Check that the API responds 200 on /health."""
    try:
        resp = requests.get(API_URL, timeout=10)
        if resp.status_code == 200:
            print(f"[{ts()}] [OK] API health check passed")
            record_result("api_health", True)
            return True
        else:
            print(f"[{ts()}] [FAIL] API returned status {resp.status_code}")
            record_result("api_health", False, f"HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"[{ts()}] [FAIL] API unreachable: {e}")
        record_result("api_health", False, str(e))
        return False


def auto_fix_api():
    """Attempt to restart the API if it is down."""
    print(f"[{ts()}] [WARN] Attempting API restart...")
    try:
        proc = subprocess.Popen(
            [sys.executable, "whale_api.py"],
            cwd=str(Path(__file__).parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Give it a few seconds to start
        time.sleep(5)
        if proc.poll() is None:
            print(f"[{ts()}] [OK] API process started (PID {proc.pid})")
            return True
        else:
            print(f"[{ts()}] [FAIL] API process exited immediately")
            send_telegram(
                f"<b>[WATCHDOG ALERT]</b>\nAPI restart failed - process exited immediately.\nTime: {ts()}"
            )
            return False
    except Exception as e:
        print(f"[{ts()}] [FAIL] API restart error: {e}")
        send_telegram(
            f"<b>[WATCHDOG ALERT]</b>\nAPI restart exception: {e}\nTime: {ts()}"
        )
        return False


def check_db_access():
    """Check that the database file can be opened and queried."""
    try:
        if not DB_PATH.exists():
            print(f"[{ts()}] [FAIL] Database file not found: {DB_PATH}")
            record_result("db_access", False, "File not found")
            return False
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.execute("SELECT 1")
        conn.close()
        print(f"[{ts()}] [OK] Database accessible")
        record_result("db_access", True)
        return True
    except Exception as e:
        print(f"[{ts()}] [FAIL] Database access error: {e}")
        record_result("db_access", False, str(e))
        return False


def check_data_freshness():
    """Check that the latest whale_positions.detected_at is within the freshness limit."""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT MAX(detected_at) FROM whale_positions")
        row = cur.fetchone()
        conn.close()

        if not row or not row[0]:
            print(f"[{ts()}] [WARN] No whale_positions data found")
            record_result("data_freshness", False, "No data in whale_positions")
            return False

        latest_str = row[0]
        try:
            latest_dt = datetime.fromisoformat(latest_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            latest_dt = datetime.strptime(latest_str, "%Y-%m-%d %H:%M:%S")

        age_minutes = (datetime.now() - latest_dt).total_seconds() / 60.0
        age_hours = age_minutes / 60.0

        if age_minutes <= FRESHNESS_LIMIT_MIN:
            print(f"[{ts()}] [OK] Data freshness: {age_minutes:.0f}min old")
            record_result("data_freshness", True)
            return True
        else:
            msg = f"Latest data is {age_hours:.1f}h old (limit: {FRESHNESS_LIMIT_MIN}min)"
            print(f"[{ts()}] [WARN] {msg}")
            record_result("data_freshness", False, msg)

            # Critical: immediate alert if data is over 2 hours stale
            if age_minutes > FRESHNESS_CRITICAL_MIN:
                send_telegram(
                    f"<b>[WATCHDOG ALERT]</b>\n"
                    f"Data freshness CRITICAL\n"
                    f"Latest detected_at is {age_hours:.1f} hours old.\n"
                    f"Time: {ts()}"
                )
            return False
    except Exception as e:
        print(f"[{ts()}] [FAIL] Freshness check error: {e}")
        record_result("data_freshness", False, str(e))
        return False


def check_stale_data():
    """Check for pending positions past their end_date (should be 0)."""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM whale_positions
            WHERE end_date < datetime('now')
            AND (outcome = 'pending' OR outcome IS NULL)
        """)
        count = cur.fetchone()[0]
        conn.close()

        if count == 0:
            print(f"[{ts()}] [OK] No stale pending positions")
            record_result("stale_data", True)
            return True
        else:
            print(f"[{ts()}] [WARN] Found {count} stale pending positions past end_date")
            record_result("stale_data", False, f"{count} stale pending positions")
            return False
    except Exception as e:
        print(f"[{ts()}] [FAIL] Stale data check error: {e}")
        record_result("stale_data", False, str(e))
        return False


def auto_fix_stale_data():
    """Sweep stale pending positions by marking them as expired."""
    print(f"[{ts()}] [WARN] Sweeping stale pending positions...")
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cur = conn.cursor()
        cur.execute("""
            UPDATE whale_positions
            SET outcome = 'expired', resolved_at = datetime('now')
            WHERE end_date < datetime('now')
            AND (outcome = 'pending' OR outcome IS NULL)
        """)
        affected = cur.rowcount
        conn.commit()
        conn.close()
        print(f"[{ts()}] [OK] Marked {affected} positions as expired")
        return affected
    except Exception as e:
        print(f"[{ts()}] [FAIL] Stale data sweep error: {e}")
        return 0


# --- Startup Report (Task 1) ---

def send_startup_report():
    """Query DB for key stats and send a startup report to Telegram."""
    print(f"[{ts()}] [INFO] Generating startup report...")

    # Gather DB stats
    db_status = "unknown"
    total_whales = 0
    total_positions = 0
    pending_count = 0
    wins = 0
    losses = 0
    last_detected = "N/A"
    db_size_mb = 0.0

    try:
        if DB_PATH.exists():
            db_size_mb = DB_PATH.stat().st_size / (1024 * 1024)
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM tracked_whales")
        total_whales = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM whale_positions")
        total_positions = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'pending' OR outcome IS NULL")
        pending_count = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'won'")
        wins = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'lost'")
        losses = cur.fetchone()[0] or 0

        cur.execute("SELECT MAX(detected_at) FROM whale_positions")
        row = cur.fetchone()
        last_detected = row[0] if row and row[0] else "N/A"

        conn.close()
        db_status = "accessible"
        print(f"[{ts()}] [OK] DB stats gathered")
    except Exception as e:
        db_status = f"error: {e}"
        print(f"[{ts()}] [FAIL] DB stats error: {e}")

    # Check API health
    api_status = "unknown"
    try:
        resp = requests.get(API_URL, timeout=10)
        api_status = "healthy" if resp.status_code == 200 else f"HTTP {resp.status_code}"
    except Exception as e:
        api_status = f"down ({e})"

    total_resolved = wins + losses
    win_rate = (wins / total_resolved * 100) if total_resolved > 0 else 0.0

    msg = (
        f"\U0001F6A8 <b>WATCHDOG STARTUP REPORT</b> \U0001F6A8\n"
        f"\n"
        f"\U0001F4CA <b>Component Status:</b>\n"
        f"  \u2022 API: <b>{api_status}</b>\n"
        f"  \u2022 Database: <b>{db_status}</b> ({db_size_mb:.1f} MB)\n"
        f"\n"
        f"\U0001F40B <b>Whale Stats:</b>\n"
        f"  \u2022 Total whales: <b>{total_whales}</b>\n"
        f"  \u2022 Total positions: <b>{total_positions}</b>\n"
        f"  \u2022 Pending: <b>{pending_count}</b>\n"
        f"  \u2022 Wins: <b>{wins}</b> | Losses: <b>{losses}</b>\n"
        f"  \u2022 Win rate: <b>{win_rate:.1f}%</b>\n"
        f"  \u2022 Last detected: <code>{last_detected}</code>\n"
        f"\n"
        f"\u23F0 Watchdog interval: {CHECK_INTERVAL}s\n"
        f"\U0001F552 Started: {ts()}"
    )

    send_telegram(msg)
    print(f"[{ts()}] [OK] Startup report sent")


# --- Daily Summary (Task 2) ---

def send_daily_summary():
    """Send a daily summary of resolved positions, P&L, and top whale."""
    global last_summary_date
    print(f"[{ts()}] [INFO] Generating daily summary...")

    today_str = date.today().isoformat()  # YYYY-MM-DD

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cur = conn.cursor()

        # Positions resolved today
        cur.execute("""
            SELECT COUNT(*) FROM whale_positions
            WHERE date(resolved_at) = date('now') AND outcome IN ('won', 'lost')
        """)
        resolved_today = cur.fetchone()[0] or 0

        # Wins/losses today
        cur.execute("""
            SELECT
                COUNT(CASE WHEN outcome = 'won' THEN 1 END) as wins,
                COUNT(CASE WHEN outcome = 'lost' THEN 1 END) as losses,
                COALESCE(SUM(actual_pnl), 0) as total_pnl
            FROM whale_positions
            WHERE date(resolved_at) = date('now') AND outcome IN ('won', 'lost')
        """)
        row = cur.fetchone()
        wins_today = row[0] or 0
        losses_today = row[1] or 0
        pnl_today = row[2] or 0.0

        # Top performing whale today (by P&L)
        cur.execute("""
            SELECT
                COALESCE(tw.display_name, wp.address) as whale_name,
                SUM(wp.actual_pnl) as whale_pnl,
                COUNT(*) as trades
            FROM whale_positions wp
            LEFT JOIN tracked_whales tw ON wp.address = tw.address
            WHERE date(wp.resolved_at) = date('now') AND wp.outcome IN ('won', 'lost')
            GROUP BY wp.address
            ORDER BY whale_pnl DESC
            LIMIT 1
        """)
        top_whale_row = cur.fetchone()
        top_whale_name = top_whale_row[0] if top_whale_row else "N/A"
        top_whale_pnl = top_whale_row[1] if top_whale_row else 0
        top_whale_trades = top_whale_row[2] if top_whale_row else 0

        # Overall pending count
        cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'pending' OR outcome IS NULL")
        pending_total = cur.fetchone()[0] or 0

        conn.close()
    except Exception as e:
        print(f"[{ts()}] [FAIL] Daily summary DB error: {e}")
        return

    win_rate_today = (wins_today / (wins_today + losses_today) * 100) if (wins_today + losses_today) > 0 else 0.0
    pnl_emoji = "\U0001F4B0" if pnl_today >= 0 else "\U0001F534"

    msg = (
        f"\U0001F4C5 <b>DAILY SUMMARY - {today_str}</b>\n"
        f"\n"
        f"\U0001F4CA <b>Today's Results:</b>\n"
        f"  \u2022 Resolved: <b>{resolved_today}</b> positions\n"
        f"  \u2022 Wins: <b>{wins_today}</b> | Losses: <b>{losses_today}</b>\n"
        f"  \u2022 Win rate: <b>{win_rate_today:.1f}%</b>\n"
        f"  {pnl_emoji} P&L: <b>${pnl_today:+,.2f}</b>\n"
        f"\n"
        f"\U0001F3C6 <b>Top Whale Today:</b>\n"
        f"  \u2022 {top_whale_name} ({top_whale_trades} trades, ${top_whale_pnl:+,.2f})\n"
        f"\n"
        f"\u23F3 Pending positions: <b>{pending_total}</b>"
    )

    send_telegram(msg)
    last_summary_date = today_str
    print(f"[{ts()}] [OK] Daily summary sent for {today_str}")


# --- Database Backup (Task 3) ---

def backup_database():
    """Backup the database locally and via SCP to Mac Mini."""
    print(f"[{ts()}] [INFO] Starting database backup...")

    # Create backups directory if needed
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Local backup
    date_str = datetime.now().strftime("%Y%m%d")
    backup_filename = f"whale_hunter_{date_str}.db"
    backup_path = BACKUP_DIR / backup_filename

    try:
        shutil.copy2(str(DB_PATH), str(backup_path))
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        print(f"[{ts()}] [OK] Local backup created: {backup_path} ({size_mb:.1f} MB)")
    except Exception as e:
        print(f"[{ts()}] [FAIL] Local backup failed: {e}")
        return

    # Cleanup old backups (keep only last MAX_BACKUPS)
    try:
        backups = sorted(BACKUP_DIR.glob("whale_hunter_*.db"))
        if len(backups) > MAX_BACKUPS:
            for old_backup in backups[:-MAX_BACKUPS]:
                old_backup.unlink()
                print(f"[{ts()}] [INFO] Deleted old backup: {old_backup.name}")
    except Exception as e:
        print(f"[{ts()}] [WARN] Backup cleanup error: {e}")

    # SCP to Mac Mini
    try:
        result = subprocess.run(
            ["scp", str(DB_PATH), SCP_TARGET],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print(f"[{ts()}] [OK] SCP backup to Mac Mini succeeded")
        else:
            print(f"[{ts()}] [WARN] SCP backup failed: {result.stderr.strip()}")
    except FileNotFoundError:
        print(f"[{ts()}] [WARN] SCP not available on this system - skipping remote backup")
    except subprocess.TimeoutExpired:
        print(f"[{ts()}] [WARN] SCP backup timed out after 60s")
    except Exception as e:
        print(f"[{ts()}] [WARN] SCP backup error: {e}")


# --- Position Archival (Task 4) ---

def archive_old_positions():
    """Move expired positions older than ARCHIVE_AGE_DAYS to archive table."""
    print(f"[{ts()}] [INFO] Checking for positions to archive...")

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        cur = conn.cursor()

        # Create archive table with same schema if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS whale_positions_archive AS
            SELECT * FROM whale_positions WHERE 1=0
        """)

        # Find cutoff date
        cutoff = (datetime.now() - timedelta(days=ARCHIVE_AGE_DAYS)).isoformat()

        # Count positions to archive (expired only, older than cutoff)
        cur.execute("""
            SELECT COUNT(*) FROM whale_positions
            WHERE outcome = 'expired'
            AND detected_at < ?
        """, (cutoff,))
        count = cur.fetchone()[0] or 0

        if count == 0:
            print(f"[{ts()}] [OK] No positions to archive (cutoff: {ARCHIVE_AGE_DAYS} days)")
            conn.close()
            return 0

        # Copy to archive
        cur.execute("""
            INSERT INTO whale_positions_archive
            SELECT * FROM whale_positions
            WHERE outcome = 'expired'
            AND detected_at < ?
        """, (cutoff,))

        # Delete from main table
        cur.execute("""
            DELETE FROM whale_positions
            WHERE outcome = 'expired'
            AND detected_at < ?
        """, (cutoff,))

        conn.commit()
        conn.close()

        print(f"[{ts()}] [OK] Archived {count} expired positions older than {ARCHIVE_AGE_DAYS} days")
        return count

    except Exception as e:
        print(f"[{ts()}] [FAIL] Archive error: {e}")
        return 0


# --- Daily tasks runner ---

_last_hourly_run = None


def run_hourly_tasks():
    """Run tasks every hour: resolve predictions, scan arbitrage."""
    global _last_hourly_run
    now = datetime.now()
    if _last_hourly_run and (now - _last_hourly_run).total_seconds() < 3500:
        return  # Already ran this hour

    print(f"[{ts()}] [INFO] Running hourly tasks...")

    # C3: Resolve pending MiroFish predictions
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "resolve_predictions.py")],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "PYTHONUTF8": "1"},
            cwd=str(Path(__file__).parent),
        )
        if result.returncode == 0:
            print(f"[{ts()}] [OK] resolve_predictions completed")
        else:
            print(f"[{ts()}] [WARN] resolve_predictions exit code {result.returncode}")
    except Exception as e:
        print(f"[{ts()}] [WARN] resolve_predictions failed: {e}")

    # C2: Scan for arbitrage opportunities
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "arbitrage_scanner.py"),
             "--min", "3"],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "PYTHONUTF8": "1"},
            cwd=str(Path(__file__).parent),
        )
        if result.returncode == 0:
            # Check if arb found
            if "TOTAL: 0" not in result.stdout:
                print(f"[{ts()}] [TARGET] Arbitrage opportunity detected!")
            else:
                print(f"[{ts()}] [OK] arbitrage_scanner: no opportunities")
        else:
            print(f"[{ts()}] [WARN] arbitrage_scanner exit code {result.returncode}")
    except Exception as e:
        print(f"[{ts()}] [WARN] arbitrage_scanner failed: {e}")

    # MiroFish validation: run consensus_swarm_connector --scan on top 5 picks
    try:
        print(f"[{ts()}] [INFO] Running MiroFish validation on all GREEN consensus picks...")
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "consensus_swarm_connector.py"),
             "--scan", "--top", "10"],
            capture_output=True, text=True, timeout=7200,  # 2h max (7-10 picks × ~25 min each)
            env={**os.environ, "PYTHONUTF8": "1"},
            cwd=str(Path(__file__).parent),
        )
        if result.returncode == 0:
            # Extract signal count from output
            lines = result.stdout.strip().split('\n')
            sig_line = [l for l in lines if 'Signals generated' in l]
            sig_info = sig_line[0] if sig_line else "completed"
            print(f"[{ts()}] [OK] MiroFish validation: {sig_info}")
        else:
            print(f"[{ts()}] [WARN] MiroFish validation exit code {result.returncode}")
            if result.stderr:
                print(f"[{ts()}]   stderr: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print(f"[{ts()}] [WARN] MiroFish validation timed out (600s)")
    except Exception as e:
        print(f"[{ts()}] [WARN] MiroFish validation failed: {e}")

    _last_hourly_run = now
    print(f"[{ts()}] [OK] Hourly tasks complete")


def run_daily_tasks():
    """Run all daily tasks: summary, backup, archival."""
    global last_summary_date
    today = date.today().isoformat()

    if last_summary_date == today:
        return  # Already ran today

    print(f"[{ts()}] [INFO] Running daily tasks for {today}...")

    send_daily_summary()
    backup_database()
    archive_old_positions()

    print(f"[{ts()}] [OK] Daily tasks complete")


# --- Main loop ---

def run_checks():
    """Run all health checks once. Returns True if all passed."""
    print(f"[{ts()}] --- Running watchdog checks ---")
    all_ok = True

    # 1. Database access (must pass before other DB checks)
    db_ok = check_db_access()
    if not db_ok:
        all_ok = False

    # 2. API health
    api_ok = check_api_health()
    if not api_ok:
        all_ok = False
        auto_fix_api()

    # 3. Data freshness (only if DB is accessible)
    if db_ok:
        fresh_ok = check_data_freshness()
        if not fresh_ok:
            all_ok = False

    # 4. Stale data (only if DB is accessible)
    if db_ok:
        stale_ok = check_stale_data()
        if not stale_ok:
            all_ok = False
            auto_fix_stale_data()

    # 5. MiroFish backend health
    try:
        r = requests.get("http://localhost:5001/health", timeout=5)
        if r.status_code == 200:
            print(f"[{ts()}] [OK] MiroFish backend healthy")
        else:
            print(f"[{ts()}] [WARN] MiroFish backend returned {r.status_code}")
    except Exception:
        print(f"[{ts()}] [WARN] MiroFish backend not responding (port 5001)")

    # 6. Ollama health
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            print(f"[{ts()}] [OK] Ollama LLM healthy")
        else:
            print(f"[{ts()}] [WARN] Ollama returned {r.status_code}")
    except Exception:
        print(f"[{ts()}] [WARN] Ollama not responding (port 11434)")

    status = "[OK] All checks passed" if all_ok else "[WARN] Some checks failed"
    print(f"[{ts()}] {status}")
    print()
    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Mirofish-hub watchdog monitor")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run checks once and exit (for testing)",
    )
    args = parser.parse_args()

    print(f"[{ts()}] Watchdog starting (mode: {'once' if args.once else 'loop'})")
    print(f"[{ts()}] DB: {DB_PATH}")
    print(f"[{ts()}] API: {API_URL}")
    print(f"[{ts()}] Check interval: {CHECK_INTERVAL}s")
    print()

    if args.once:
        ok = run_checks()
        sys.exit(0 if ok else 1)

    # Send startup report before main loop
    send_startup_report()

    # Continuous loop
    while True:
        try:
            run_checks()
            run_hourly_tasks()
            run_daily_tasks()
        except Exception as e:
            print(f"[{ts()}] [FAIL] Unexpected error in check loop: {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
