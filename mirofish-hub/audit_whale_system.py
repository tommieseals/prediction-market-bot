#!/usr/bin/env python3
"""
WHALE TRACKER SYSTEM AUDIT
Comprehensive check of all components
"""
import sqlite3
import json
import os
import requests
from pathlib import Path

ISSUES = []

def log_issue(component, severity, description):
    ISSUES.append({"component": component, "severity": severity, "description": description})
    icon = "[RED]" if severity == "HIGH" else "[YELLOW]" if severity == "MEDIUM" else "[GREEN]"
    print(f"  {icon} [{severity}] {description}")

def audit_database():
    print("\n" + "=" * 60)
    print("1. DATABASE AUDIT")
    print("=" * 60)
    
    db_path = Path(__file__).parent / "data" / "whale_hunter.db"
    if not db_path.exists():
        log_issue("database", "HIGH", f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    
    # Check tables exist
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"  Tables found: {tables}")
    
    required_tables = ['whale_positions', 'tracked_whales']
    for t in required_tables:
        if t not in tables:
            log_issue("database", "HIGH", f"Missing required table: {t}")
    
    # Check whale_positions schema
    cur.execute("PRAGMA table_info(whale_positions)")
    pos_cols = [r[1] for r in cur.fetchall()]
    print(f"  whale_positions columns: {pos_cols}")
    
    required_pos_cols = ['id', 'address', 'condition_id', 'market_title', 'side', 
                         'entry_price', 'size_usd', 'detected_at']
    for c in required_pos_cols:
        if c not in pos_cols:
            log_issue("database", "HIGH", f"Missing column in whale_positions: {c}")
    
    # Check outcome tracking columns
    outcome_cols = ['outcome', 'resolved_at', 'actual_pnl']
    for c in outcome_cols:
        if c not in pos_cols:
            log_issue("database", "MEDIUM", f"Missing outcome column: {c}")
    
    # Data integrity checks
    cur.execute("SELECT COUNT(*) FROM whale_positions")
    total_pos = cur.fetchone()[0]
    print(f"  Total positions: {total_pos}")
    
    cur.execute("SELECT COUNT(*) FROM tracked_whales")
    total_whales = cur.fetchone()[0]
    print(f"  Total whales: {total_whales}")
    
    if total_pos == 0:
        log_issue("database", "MEDIUM", "No positions in database")
    
    if total_whales == 0:
        log_issue("database", "MEDIUM", "No whales in database")
    
    # Check for orphaned positions
    cur.execute("""
        SELECT COUNT(*) FROM whale_positions wp 
        LEFT JOIN tracked_whales tw ON wp.address = tw.address 
        WHERE tw.address IS NULL
    """)
    orphaned = cur.fetchone()[0]
    if orphaned > 0:
        log_issue("database", "LOW", f"{orphaned} positions with no matching whale record")
    
    # Check for NULL critical fields
    cur.execute("SELECT COUNT(*) FROM whale_positions WHERE condition_id IS NULL OR condition_id = ''")
    null_cid = cur.fetchone()[0]
    if null_cid > 0:
        log_issue("database", "HIGH", f"{null_cid} positions with NULL/empty condition_id")
    
    cur.execute("SELECT COUNT(*) FROM whale_positions WHERE entry_price IS NULL OR entry_price = 0")
    null_price = cur.fetchone()[0]
    if null_price > 0:
        log_issue("database", "MEDIUM", f"{null_price} positions with NULL/0 entry_price")
    
    # Check outcome status
    cur.execute("SELECT outcome, COUNT(*) FROM whale_positions GROUP BY outcome")
    outcomes = cur.fetchall()
    print(f"  Outcome distribution: {dict(outcomes)}")
    
    conn.close()

def audit_export():
    print("\n" + "=" * 60)
    print("2. EXPORT SCRIPT AUDIT")
    print("=" * 60)
    
    export_script = Path(__file__).parent / "export_whale_data.py"
    if not export_script.exists():
        log_issue("export", "HIGH", "export_whale_data.py not found")
        return
    
    print(f"  Script exists: {export_script}")
    
    # Check if JSON output exists
    json_file = Path(__file__).parent / "whale_positions.json"
    if not json_file.exists():
        log_issue("export", "MEDIUM", "whale_positions.json not found (run export)")
    else:
        # Validate JSON structure
        try:
            with open(json_file) as f:
                data = json.load(f)
            
            print(f"  JSON valid: True")
            print(f"  Positions in export: {len(data.get('positions', []))}")
            print(f"  Last updated: {data.get('updated', 'N/A')}")
            
            # Check required fields in positions
            if data.get('positions'):
                pos = data['positions'][0]
                required = ['timestamp', 'whale', 'market', 'position', 'price', 'size', 'outcome']
                for field in required:
                    if field not in pos:
                        log_issue("export", "MEDIUM", f"Missing field in export: {field}")
        except json.JSONDecodeError as e:
            log_issue("export", "HIGH", f"Invalid JSON: {e}")

def audit_outcome_tracker():
    print("\n" + "=" * 60)
    print("3. OUTCOME TRACKER AUDIT")
    print("=" * 60)
    
    tracker_script = Path(__file__).parent / "whale_outcome_tracker.py"
    if not tracker_script.exists():
        log_issue("outcome_tracker", "HIGH", "whale_outcome_tracker.py not found")
        return
    
    print(f"  Script exists: {tracker_script}")
    
    # Try to import and check
    try:
        from whale_outcome_tracker import WhaleOutcomeTracker
        tracker = WhaleOutcomeTracker()
        status = tracker.get_tracking_status()
        print(f"  Tracking status: {status}")
        
        if status['pending'] == status['total_positions'] and status['total_positions'] > 50:
            log_issue("outcome_tracker", "LOW", "All positions still pending - may need to run resolution")
            
    except Exception as e:
        log_issue("outcome_tracker", "HIGH", f"Failed to import/run: {e}")

def audit_connector():
    print("\n" + "=" * 60)
    print("4. WHALE HUNTER CONNECTOR AUDIT")
    print("=" * 60)
    
    connector = Path(__file__).parent / "whale_hunter_connector.py"
    if not connector.exists():
        log_issue("connector", "HIGH", "whale_hunter_connector.py not found")
        return
    
    print(f"  Script exists: {connector}")
    
    # Check for required functions
    with open(connector) as f:
        content = f.read()
    
    required_funcs = ['sync_dashboard', 'check_outcomes', 'cmd_scan_fast', 'send_telegram_alert']
    for func in required_funcs:
        if f"def {func}" not in content:
            log_issue("connector", "MEDIUM", f"Missing function: {func}")
        else:
            print(f"  Function {func}: ✓")

def audit_dashboard():
    print("\n" + "=" * 60)
    print("5. DASHBOARD AUDIT")
    print("=" * 60)
    
    # Check local HTML
    local_html = Path("C:/Users/USER/clawd/whale-tracker.html")
    if not local_html.exists():
        log_issue("dashboard", "HIGH", "Local whale-tracker.html not found")
    else:
        print(f"  Local HTML exists: {local_html}")
        
        with open(local_html) as f:
            content = f.read()
        
        # Check for required elements
        required = ['whale-table', 'calc-investment', 'formatOutcome', 'data-sort="outcome"']
        for elem in required:
            if elem not in content:
                log_issue("dashboard", "MEDIUM", f"Missing element in HTML: {elem}")
            else:
                print(f"  Element {elem}: ✓")

def audit_mac_mini_sync():
    print("\n" + "=" * 60)
    print("6. MAC MINI SYNC AUDIT")
    print("=" * 60)
    
    import subprocess
    
    # Check SSH connectivity
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "tommie@100.88.105.106", "echo 'connected'"],
            capture_output=True, timeout=10
        )
        if result.returncode == 0:
            print("  SSH to Mac Mini: ✓")
        else:
            log_issue("sync", "HIGH", "Cannot SSH to Mac Mini")
            return
    except Exception as e:
        log_issue("sync", "HIGH", f"SSH check failed: {e}")
        return
    
    # Check if dashboard files exist on Mac Mini
    try:
        result = subprocess.run(
            ["ssh", "tommie@100.88.105.106", 
             "ls -la ~/clawd/dashboard/whale-tracker.html ~/clawd/dashboard/data/whale_positions.json 2>&1"],
            capture_output=True, timeout=15
        )
        output = result.stdout.decode()
        print(f"  Remote files:\n{output}")
        
        if "No such file" in output:
            log_issue("sync", "MEDIUM", "Some dashboard files missing on Mac Mini")
            
    except Exception as e:
        log_issue("sync", "MEDIUM", f"Could not check remote files: {e}")
    
    # Check nav links
    try:
        result = subprocess.run(
            ["ssh", "tommie@100.88.105.106",
             "grep -l 'whale-tracker' ~/clawd/dashboard/*.html 2>/dev/null | wc -l"],
            capture_output=True, timeout=15
        )
        count = int(result.stdout.decode().strip())
        print(f"  Pages with whale-tracker nav link: {count}")
        
        if count < 20:
            log_issue("sync", "LOW", f"Only {count} pages have whale-tracker nav link")
            
    except Exception as e:
        log_issue("sync", "LOW", f"Could not check nav links: {e}")

def audit_api():
    print("\n" + "=" * 60)
    print("7. POLYMARKET API AUDIT")
    print("=" * 60)
    
    # Test Gamma API
    try:
        resp = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"limit": 1},
            timeout=15
        )
        if resp.ok:
            print("  Gamma API: ✓ (accessible)")
        else:
            log_issue("api", "HIGH", f"Gamma API returned {resp.status_code}")
    except Exception as e:
        log_issue("api", "HIGH", f"Gamma API unreachable: {e}")
    
    # Test Data API
    try:
        resp = requests.get(
            "https://data-api.polymarket.com/v1/leaderboard",
            params={"limit": 1},
            timeout=15
        )
        if resp.ok:
            print("  Data API: ✓ (accessible)")
        else:
            log_issue("api", "MEDIUM", f"Data API returned {resp.status_code}")
    except Exception as e:
        log_issue("api", "MEDIUM", f"Data API unreachable: {e}")

def audit_telegram():
    print("\n" + "=" * 60)
    print("8. TELEGRAM ALERTS AUDIT")
    print("=" * 60)
    
    # Check if bot token is configured
    from whale_hunter_connector import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "":
        log_issue("telegram", "HIGH", "Telegram bot token not configured")
    else:
        print(f"  Bot token: {TELEGRAM_BOT_TOKEN[:20]}...")
    
    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == "":
        log_issue("telegram", "HIGH", "Telegram chat ID not configured")
    else:
        print(f"  Chat ID: {TELEGRAM_CHAT_ID}")
    
    # Test API (don't send message)
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe",
            timeout=10
        )
        if resp.ok:
            bot_info = resp.json()
            print(f"  Bot name: {bot_info.get('result', {}).get('username', 'N/A')}")
        else:
            log_issue("telegram", "MEDIUM", "Bot token may be invalid")
    except Exception as e:
        log_issue("telegram", "MEDIUM", f"Could not verify bot: {e}")

def print_summary():
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    
    high = [i for i in ISSUES if i['severity'] == 'HIGH']
    medium = [i for i in ISSUES if i['severity'] == 'MEDIUM']
    low = [i for i in ISSUES if i['severity'] == 'LOW']
    
    print(f"\n[RED] HIGH: {len(high)}")
    for i in high:
        print(f"   - [{i['component']}] {i['description']}")
    
    print(f"\n[YELLOW] MEDIUM: {len(medium)}")
    for i in medium:
        print(f"   - [{i['component']}] {i['description']}")
    
    print(f"\n[GREEN] LOW: {len(low)}")
    for i in low:
        print(f"   - [{i['component']}] {i['description']}")
    
    print(f"\n{'=' * 60}")
    if len(high) == 0:
        print("[OK] NO CRITICAL ISSUES FOUND")
    else:
        print(f"[WARN] {len(high)} CRITICAL ISSUES NEED ATTENTION")
    print("=" * 60)

if __name__ == "__main__":
    print("\n[WHALE] WHALE TRACKER SYSTEM AUDIT")
    print("=" * 60)
    
    audit_database()
    audit_export()
    audit_outcome_tracker()
    audit_connector()
    audit_dashboard()
    audit_mac_mini_sync()
    audit_api()
    audit_telegram()
    print_summary()
