#!/usr/bin/env python3
"""
Export Whale Hunter data to JSON for dashboard consumption.
Run this on RTX and scp the output to Mac Mini dashboard.
"""
import json
import sqlite3
import os
from datetime import datetime
from pathlib import Path

OUTPUT_FILE = "data/whale_positions.json"
DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"

def export_whale_data():
    """Export whale positions from database to JSON."""
    
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return []
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    positions = []
    
    # Join positions with whale info - ONLY FRESH DATA
    # Filter: pending from last 7 days + resolved from last 3 days
    cur.execute("""
        SELECT 
            wp.id,
            wp.address as whale_address,
            tw.display_name as whale,
            tw.elite_score,
            tw.pnl,
            wp.market_title as market,
            wp.condition_id,
            wp.side as position,
            wp.entry_price as price,
            wp.size_usd as size,
            wp.unrealized_pnl,
            wp.detected_at as timestamp,
            wp.signal_generated,
            COALESCE(wp.outcome, 'pending') as outcome,
            wp.actual_pnl,
            tw.tracked_bets,
            tw.winning_bets,
            tw.tracked_accuracy
        FROM whale_positions wp
        LEFT JOIN tracked_whales tw ON wp.address = tw.address
        WHERE 
            -- Pending positions from last 7 days
            (wp.outcome = 'pending' AND wp.detected_at > datetime('now', '-7 days'))
            OR
            -- Recently resolved (won/lost) from last 3 days  
            (wp.outcome IN ('won', 'lost') AND wp.detected_at > datetime('now', '-3 days'))
        ORDER BY 
            CASE WHEN wp.outcome = 'pending' THEN 0
                 WHEN wp.outcome = 'won' THEN 1
                 WHEN wp.outcome = 'lost' THEN 2
                 ELSE 3 END,
            wp.detected_at DESC
        LIMIT 500
    """)
    
    for row in cur.fetchall():
        pos = dict(row)
        # Calculate if new (detected in last 2 hours)
        try:
            detected = datetime.fromisoformat(pos['timestamp'].replace('Z', '+00:00'))
            age_hours = (datetime.now() - detected.replace(tzinfo=None)).total_seconds() / 3600
            is_new = age_hours < 2  # New = less than 2 hours old
        except Exception:
            is_new = False
        
        positions.append({
            "timestamp": pos['timestamp'],
            "whale": pos['whale'] or 'Unknown',
            "whale_address": pos['whale_address'],
            "elite_score": round(pos['elite_score'] or 0, 1),
            "pnl": round(pos['pnl'] or 0, 2),
            "market": pos['market'],
            "condition_id": pos['condition_id'],
            "position": pos['position'].upper() if pos['position'] else 'YES',
            "price": round(pos['price'] or 0, 4),
            "size": round(pos['size'] or 0, 2),
            "unrealized_pnl": round(pos['unrealized_pnl'] or 0, 2),
            "expiry": "",  # Would need market data to get expiry
            "platform": "Polymarket",
            "is_new": is_new,
            "signal_generated": bool(pos['signal_generated']),
            "outcome": pos.get('outcome', 'pending'),
            "actual_pnl": round(pos.get('actual_pnl') or 0, 2) if pos.get('actual_pnl') else None,
        })
    
    # Also get trade signals for additional context
    cur.execute("""
        SELECT 
            ts.whale_address,
            ts.whale_name as whale,
            ts.whale_elite_score as elite_score,
            ts.market_title as market,
            ts.condition_id,
            ts.direction as position,
            ts.whale_entry_price as price,
            ts.position_size as size,
            ts.created_at as timestamp,
            ts.status,
            ts.edge,
            ts.kelly_fraction,
            tw.pnl
        FROM trade_signals ts
        LEFT JOIN tracked_whales tw ON ts.whale_address = tw.address
        WHERE ts.status = 'pending' OR ts.created_at > datetime('now', '-24 hours')
        ORDER BY ts.created_at DESC
        LIMIT 50
    """)
    
    signals = []
    for row in cur.fetchall():
        sig = dict(row)
        signals.append({
            "timestamp": sig['timestamp'],
            "whale": sig['whale'] or 'Unknown',
            "whale_address": sig['whale_address'],
            "elite_score": round(sig['elite_score'] or 0, 1),
            "pnl": round(sig['pnl'] or 0, 2),
            "market": sig['market'],
            "condition_id": sig['condition_id'],
            "position": sig['position'].upper() if sig['position'] else 'YES',
            "price": round(sig['price'] or 0, 4),
            "size": round(sig['size'] or 0, 2),
            "platform": "Polymarket",
            "is_new": True,
            "edge": round(sig['edge'] or 0, 2),
            "kelly": round(sig['kelly_fraction'] or 0, 2),
            "status": sig['status']
        })
    
    # Get whale stats
    cur.execute("""
        SELECT 
            COUNT(*) as whale_count,
            SUM(pnl) as total_pnl,
            AVG(elite_score) as avg_elite
        FROM tracked_whales
        WHERE elite_score >= 20
    """)
    stats = dict(cur.fetchone())
    
    conn.close()
    
    return {
        "positions": positions,
        "signals": signals,
        "stats": {
            "whale_count": stats['whale_count'] or 0,
            "total_pnl": round(stats['total_pnl'] or 0, 2),
            "avg_elite": round(stats['avg_elite'] or 0, 1)
        }
    }

def validate_freshness(positions):
    """
    CRITICAL: Reject any position older than 7 days.
    This prevents stale games from ever appearing on the dashboard.
    """
    now = datetime.now()
    fresh = []
    rejected = 0
    
    for pos in positions:
        ts = pos.get("timestamp", "")
        if not ts:
            rejected += 1
            continue
            
        try:
            detected = datetime.fromisoformat(ts.replace("Z", "").replace("+00:00", ""))
            age_days = (now - detected).days
            
            # HARD LIMIT: Nothing older than 7 days
            if age_days > 7:
                rejected += 1
                continue
                
            fresh.append(pos)
        except Exception:
            rejected += 1
            continue
    
    if rejected > 0:
        print(f"  [FILTER] Rejected {rejected} stale positions (>7 days old)")
    
    return fresh


def main():
    print("=" * 50)
    print("[EXPORT] Whale Data Export")
    print("=" * 50)
    print(f"Time: {datetime.now().isoformat()}")
    
    data = export_whale_data()
    
    # CRITICAL: Validate freshness before saving
    positions = data.get("positions", [])
    print(f"\nRaw positions from DB: {len(positions)}")
    
    fresh_positions = validate_freshness(positions)
    print(f"Fresh positions (<=7 days): {len(fresh_positions)}")
    
    # Also validate signals
    signals = data.get("signals", [])
    fresh_signals = validate_freshness(signals)
    
    output = {
        "updated": datetime.now().isoformat(),
        "positions": fresh_positions,
        "signals": fresh_signals,
        "stats": data.get("stats", {}),
        "count": len(fresh_positions),
        "freshness_validated": True
    }
    
    output_path = Path(__file__).parent / OUTPUT_FILE
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\n[OK] Exported {output['count']} fresh positions to {output_path}")
    print(f"Stats: {output['stats']}")
    print("=" * 50)
    return output_path


if __name__ == "__main__":
    main()
