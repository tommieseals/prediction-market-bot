#!/usr/bin/env python3
"""
CLUSTER ANALYZER — Run clustering on all tracked whales

This builds the similarity graph and finds clusters across all 
tracked whales in the database.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from polymarket_api import PolymarketAPI
from whale_cluster import (
    build_wallet_behavior, build_similarity_graph, 
    find_clusters, summarize_cluster, save_clusters
)

WHALE_DB = Path(__file__).parent / "data" / "whale_hunter.db"

# Telegram alerting
TELEGRAM_BOT_TOKEN = "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU"
TELEGRAM_CHAT_ID = "939543801"

def send_telegram_alert(message: str) -> bool:
    """Send alert to Telegram."""
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, data=data, timeout=10)
        return resp.ok
    except Exception:
        return False


def get_tracked_whales(limit: int = 50):
    """Get all tracked whales from the database."""
    conn = sqlite3.connect(str(WHALE_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.execute("""
        SELECT address, display_name, elite_score, pnl
        FROM tracked_whales
        WHERE elite_score >= 20
        ORDER BY elite_score DESC
        LIMIT ?
    """, (limit,))
    whales = [dict(row) for row in cur.fetchall()]
    conn.close()
    print(f"  [DB] Retrieved {len(whales)} whales from database")
    return whales


def build_behavior_from_db(address: str, api: PolymarketAPI) -> dict:
    """Build wallet behavior from API (cached where possible)."""
    # Check if we have cached behavior in wallet_market_matrix
    conn = sqlite3.connect(str(WHALE_DB))
    cur = conn.execute("""
        SELECT condition_id, side FROM wallet_market_matrix
        WHERE address = ?
    """, (address,))
    rows = cur.fetchall()
    conn.close()
    
    if rows:
        # Use cached data
        markets = set(r[0] for r in rows if r[0])
        sides = {r[0]: r[1] for r in rows if r[0] and r[1]}
        return {
            "address": address,
            "markets": markets,
            "sides": sides,
            "timestamps": [],
            "categories": {},
        }
    
    # Fall back to API
    positions = api.get_positions(address)
    closed = api.get_closed_positions(address, max_total=50)
    activity = api.get_activity(address)
    return build_wallet_behavior(address, positions, closed, activity)


def run_cluster_analysis(threshold: float = 0.25, min_cluster_size: int = 2):
    """Run full cluster analysis on all tracked whales."""
    print("=" * 60)
    print("[CLUSTER] WHALE CLUSTER ANALYSIS")
    print("=" * 60)
    
    # Get tracked whales
    whales = get_tracked_whales(limit=100)
    print(f"\n[INFO] Analyzing {len(whales)} tracked whales...")
    
    api = PolymarketAPI(rate_limit=0.3)
    
    # Build behavior profiles
    wallets = {}
    pnl_lookup = {}
    name_lookup = {}
    
    for i, whale in enumerate(whales):
        addr = whale['address']
        name = whale['display_name'] or addr[:10]
        pnl = whale['pnl'] or 0
        
        print(f"  [{i+1}/{len(whales)}] {name[:20]}...", end=" ", flush=True)
        
        try:
            behavior = build_behavior_from_db(addr, api)
            wallets[addr] = behavior
            pnl_lookup[addr] = pnl
            name_lookup[addr] = name
            print(f"markets={len(behavior['markets'])}")
        except Exception as e:
            print(f"error: {e}")
    
    api.close()
    
    # Build similarity graph
    print(f"\n[GRAPH] Building similarity graph (threshold={threshold})...")
    graph = build_similarity_graph(wallets, threshold=threshold)
    edge_count = sum(len(v) for v in graph.values()) // 2
    print(f"  Edges found: {edge_count}")
    
    # Find clusters
    print(f"\n[CLUSTER] Finding connected components...")
    clusters_raw = find_clusters(graph, min_size=min_cluster_size)
    print(f"  Clusters found: {len(clusters_raw)}")
    
    # Summarize and save
    cluster_summaries = []
    for cluster_addrs in clusters_raw:
        summary = summarize_cluster(cluster_addrs, wallets, pnl_lookup)
        summary['names'] = [name_lookup.get(a, a[:10]) for a in cluster_addrs]
        cluster_summaries.append(summary)
    
    # Save to DB
    save_clusters(cluster_summaries, str(WHALE_DB))
    print(f"\n[OK] Saved {len(cluster_summaries)} clusters to database")
    
    # Display results
    if cluster_summaries:
        print(f"\n{'=' * 60}")
        print("[RESULTS] DETECTED CLUSTERS")
        print(f"{'=' * 60}")
        
        for c in cluster_summaries[:10]:  # Top 10
            print(f"\n  {c['cluster_id']}:")
            print(f"    Wallets: {', '.join(c['names'][:5])}")
            if len(c['names']) > 5:
                print(f"             ...and {len(c['names'])-5} more")
            print(f"    Size: {c['size']} wallets")
            print(f"    Shared markets: {c['shared_markets']}")
            print(f"    Combined PnL: ${c['combined_pnl']:,.2f}")
            if c['likely_operator']:
                print(f"    [!] LIKELY MULTI-ACCOUNT OPERATOR")
        
        # Send Telegram alert for suspicious clusters
        suspicious = [c for c in cluster_summaries if c['likely_operator']]
        if suspicious:
            alert = f"<b>[CLUSTER] Multi-Account Detection</b>\n\n"
            alert += f"Found {len(suspicious)} suspicious clusters:\n\n"
            for c in suspicious[:3]:
                names = ', '.join(c['names'][:3])
                alert += f"- {c['size']} wallets: {names}\n"
                alert += f"  Combined PnL: ${c['combined_pnl']:,.0f}\n\n"
            send_telegram_alert(alert)
    else:
        print("\n  No clusters detected - wallets appear independent")
    
    return cluster_summaries


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Whale Cluster Analyzer")
    parser.add_argument("--threshold", type=float, default=0.25,
                        help="Similarity threshold (0.0-1.0)")
    parser.add_argument("--min-size", type=int, default=2,
                        help="Minimum cluster size")
    args = parser.parse_args()
    
    run_cluster_analysis(threshold=args.threshold, min_cluster_size=args.min_size)
