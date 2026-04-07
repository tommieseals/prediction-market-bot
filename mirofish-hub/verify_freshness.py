#!/usr/bin/env python3
"""Verify that exported data is fresh - no stale games."""

import json
from datetime import datetime
from pathlib import Path

def verify():
    json_path = Path(__file__).parent / "data" / "whale_positions.json"
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    positions = data.get('positions', [])
    now = datetime.now()
    
    print("=" * 50)
    print("[VERIFY] Freshness Check")
    print("=" * 50)
    print(f"Export timestamp: {data.get('updated', 'unknown')}")
    print(f"Total positions: {len(positions)}")
    print(f"Freshness validated: {data.get('freshness_validated', False)}")
    
    # Find oldest and newest
    oldest_age = 0
    oldest_market = ''
    newest_age = 999
    newest_market = ''
    stale_count = 0
    
    for pos in positions:
        ts = pos.get('timestamp', '')
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '').replace('+00:00', ''))
                age_days = (now - dt).days
                
                if age_days > 7:
                    stale_count += 1
                
                if age_days > oldest_age:
                    oldest_age = age_days
                    oldest_market = pos.get('market', '')[:40]
                if age_days < newest_age:
                    newest_age = age_days
                    newest_market = pos.get('market', '')[:40]
            except Exception as e:
                pass
    
    print()
    print(f"Oldest: {oldest_age} days old")
    print(f"  -> {oldest_market}")
    print(f"Newest: {newest_age} days old")
    print(f"  -> {newest_market}")
    print()
    
    if stale_count > 0:
        print(f"[FAIL] {stale_count} STALE POSITIONS FOUND!")
        return False
    else:
        print("[OK] ALL POSITIONS ARE FRESH!")
        return True


if __name__ == "__main__":
    success = verify()
    exit(0 if success else 1)
