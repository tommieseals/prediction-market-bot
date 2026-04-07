#!/usr/bin/env python3
"""
REFRESH DASHBOARD — Standalone script to refresh dashboard data

Run this via Task Scheduler every 30 minutes to ensure fresh data.
Also called automatically after every fast/full scan.

Usage:
    python refresh_dashboard.py          # Export and sync
    python refresh_dashboard.py --verify # Just verify freshness
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

def refresh():
    """Export fresh data and sync to Mac Mini."""
    print("=" * 50)
    print("[REFRESH] Dashboard Data Refresh")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 50)
    
    base_dir = Path(__file__).parent
    
    # Step 1: Export fresh data
    print("\n[1/3] Exporting fresh data...")
    result = subprocess.run(
        [sys.executable, str(base_dir / "export_whale_data.py")],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        print(f"  [FAIL] Export failed: {result.stderr}")
        return False
    print("  [OK] Export complete")
    
    # Step 2: Verify freshness
    print("\n[2/3] Verifying freshness...")
    result = subprocess.run(
        [sys.executable, str(base_dir / "verify_freshness.py")],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        print(f"  [FAIL] Freshness check failed!")
        print(result.stdout)
        return False
    print("  [OK] All data is fresh")
    
    # Step 3: Sync to Mac Mini
    print("\n[3/3] Syncing to Mac Mini...")
    json_file = base_dir / "data" / "whale_positions.json"
    result = subprocess.run(
        ["scp", "-o", "ConnectTimeout=15", str(json_file),
         "tommie@100.88.105.106:~/clawd/dashboard/data/whale_positions.json"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        print(f"  [WARN] SCP failed: {result.stderr}")
        # Don't fail completely - local export succeeded
    else:
        print("  [OK] Synced to Mac Mini")
    
    print("\n" + "=" * 50)
    print("[OK] Dashboard refresh complete!")
    print("=" * 50)
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Dashboard Refresh")
    parser.add_argument("--verify", action="store_true", help="Just verify, don't refresh")
    args = parser.parse_args()
    
    if args.verify:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "verify_freshness.py")],
            timeout=30
        )
        return result.returncode == 0
    else:
        return refresh()


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
