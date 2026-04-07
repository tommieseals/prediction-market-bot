#!/usr/bin/env python3
"""
WHALE CLUSTER — Graph-Based Wallet Clustering

Detects multi-account operators on Polymarket using:
  - Market overlap (Jaccard similarity)
  - Trade-side consistency
  - Category preference similarity
  - Timing synchronization
  - BFS connected components for cluster detection

Pure Python — no networkx dependency.
"""

import json
import sqlite3
import logging
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path

logger = logging.getLogger("whale_cluster")


# ── Wallet Behavior Summary ───────────────────────────────────

def build_wallet_behavior(
    address: str,
    positions: List[Dict],
    closed_positions: List[Dict],
    activity: List[Dict]
) -> Dict:
    """
    Build a behavior summary for a wallet.
    Used as input for similarity comparisons.
    """
    # Markets traded (by conditionId)
    markets = set()
    for p in positions + closed_positions:
        cid = p.get("conditionId", "")
        if cid:
            markets.add(cid)

    # Sides taken (conditionId → side direction)
    sides = {}
    for p in positions:
        cid = p.get("conditionId", "")
        price = float(p.get("avgPrice", 0.5) or 0.5)
        if cid:
            sides[cid] = "YES" if price > 0.5 else "NO"

    # Trade timestamps
    timestamps = []
    for a in activity:
        ts = a.get("timestamp")
        if ts:
            try:
                timestamps.append(float(ts))
            except (ValueError, TypeError):
                pass

    # Category inference from titles
    categories = defaultdict(int)
    for p in closed_positions:
        title = (p.get("title", "") or "").lower()
        if any(w in title for w in ["president", "election", "vote", "senate"]):
            categories["politics"] += 1
        elif any(w in title for w in ["crypto", "bitcoin", "ethereum", "btc"]):
            categories["crypto"] += 1
        elif any(w in title for w in ["nfl", "nba", "mlb", "game", "match", "score"]):
            categories["sports"] += 1
        elif any(w in title for w in ["fed", "rate", "gdp", "inflation", "economy"]):
            categories["economics"] += 1
        else:
            categories["other"] += 1

    return {
        "address": address,
        "markets": markets,
        "sides": sides,
        "timestamps": sorted(timestamps),
        "categories": dict(categories),
    }


# ── Similarity Calculation ─────────────────────────────────────

def jaccard_similarity(set_a: Set, set_b: Set) -> float:
    """Jaccard index: |A ∩ B| / |A ∪ B|"""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def category_cosine_similarity(cats_a: Dict[str, int],
                                cats_b: Dict[str, int]) -> float:
    """Cosine similarity between category frequency vectors."""
    all_cats = set(cats_a.keys()) | set(cats_b.keys())
    if not all_cats:
        return 0.0

    dot_product = sum(cats_a.get(c, 0) * cats_b.get(c, 0) for c in all_cats)
    mag_a = sum(v ** 2 for v in cats_a.values()) ** 0.5
    mag_b = sum(v ** 2 for v in cats_b.values()) ** 0.5

    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot_product / (mag_a * mag_b)


def timing_sync_score(ts_a: List[float], ts_b: List[float],
                       window_seconds: float = 300) -> float:
    """
    Fraction of trades that occurred within `window_seconds` of each other.
    Uses sorted merge for efficiency.
    """
    if not ts_a or not ts_b:
        return 0.0

    synced = 0
    j = 0

    for ta in ts_a:
        while j < len(ts_b) and ts_b[j] < ta - window_seconds:
            j += 1
        # Check if any ts_b entry is within window
        k = j
        while k < len(ts_b) and ts_b[k] <= ta + window_seconds:
            synced += 1
            break
            k += 1

    # Normalize by the smaller set
    return synced / max(min(len(ts_a), len(ts_b)), 1)


def compute_wallet_similarity(wallet_a: Dict, wallet_b: Dict) -> float:
    """
    Multi-factor similarity score between two wallets.

    Weights:
      0.40 — Market overlap (Jaccard on conditionIds)
      0.30 — Side consistency (same side on shared markets)
      0.20 — Category preference (cosine similarity)
      0.10 — Timing synchronization (trades within 5 min)

    Returns: weighted score 0.0 - 1.0
    """
    scores = {}

    # 1. Market overlap (most important signal)
    market_sim = jaccard_similarity(wallet_a["markets"], wallet_b["markets"])
    scores["market_overlap"] = market_sim

    # 2. Side consistency on shared markets
    shared_markets = wallet_a["markets"] & wallet_b["markets"]
    if shared_markets:
        same_side = sum(
            1 for m in shared_markets
            if wallet_a["sides"].get(m) == wallet_b["sides"].get(m)
            and wallet_a["sides"].get(m) is not None
        )
        scores["side_consistency"] = same_side / len(shared_markets)
    else:
        scores["side_consistency"] = 0.0

    # 3. Category preference
    scores["category_sim"] = category_cosine_similarity(
        wallet_a["categories"], wallet_b["categories"]
    )

    # 4. Timing sync
    scores["timing_sync"] = timing_sync_score(
        wallet_a["timestamps"], wallet_b["timestamps"]
    )

    # Weighted average
    weighted = (
        scores["market_overlap"] * 0.40 +
        scores["side_consistency"] * 0.30 +
        scores["category_sim"] * 0.20 +
        scores["timing_sync"] * 0.10
    )

    return round(weighted, 4)


# ── Graph Clustering ───────────────────────────────────────────

def build_similarity_graph(
    wallets: Dict[str, Dict],
    threshold: float = 0.5
) -> Dict[str, List[Tuple[str, float]]]:
    """
    Build adjacency list from pairwise wallet similarities.
    Only creates edges where similarity >= threshold.

    O(n^2) — acceptable for n < 200 wallets per scan.
    """
    addresses = list(wallets.keys())
    graph = defaultdict(list)

    for i, addr_a in enumerate(addresses):
        for j in range(i + 1, len(addresses)):
            addr_b = addresses[j]
            sim = compute_wallet_similarity(wallets[addr_a], wallets[addr_b])

            if sim >= threshold:
                graph[addr_a].append((addr_b, sim))
                graph[addr_b].append((addr_a, sim))
                logger.debug(
                    f"Edge: {addr_a[:10]}—{addr_b[:10]} sim={sim:.3f}"
                )

    return dict(graph)


def find_clusters(
    graph: Dict[str, List[Tuple[str, float]]],
    min_size: int = 2
) -> List[List[str]]:
    """
    Find connected components using BFS.
    Returns list of clusters (each = list of addresses), sorted by size.
    Filters out clusters smaller than min_size.
    """
    visited = set()
    clusters = []

    all_nodes = set(graph.keys())
    for neighbors in graph.values():
        for addr, _ in neighbors:
            all_nodes.add(addr)

    for start in all_nodes:
        if start in visited:
            continue

        # BFS
        cluster = []
        queue = [start]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            cluster.append(node)
            for neighbor, _ in graph.get(node, []):
                if neighbor not in visited:
                    queue.append(neighbor)

        if len(cluster) >= min_size:
            clusters.append(sorted(cluster))

    # Sort by cluster size descending
    return sorted(clusters, key=len, reverse=True)


def summarize_cluster(
    cluster: List[str],
    wallets: Dict[str, Dict],
    pnl_lookup: Dict[str, float] = None
) -> Dict:
    """
    Summarize a detected cluster.
    """
    # Shared markets
    if cluster:
        shared = wallets.get(cluster[0], {}).get("markets", set()).copy()
        for addr in cluster[1:]:
            shared &= wallets.get(addr, {}).get("markets", set())
    else:
        shared = set()

    # Combined PnL
    combined_pnl = 0.0
    if pnl_lookup:
        combined_pnl = sum(pnl_lookup.get(addr, 0) for addr in cluster)

    return {
        "cluster_id": f"cluster_{hash(tuple(cluster)) % 10000:04d}",
        "addresses": cluster,
        "size": len(cluster),
        "shared_markets": len(shared),
        "combined_pnl": combined_pnl,
        "likely_operator": len(cluster) >= 3,
        "detected_at": datetime.now().isoformat(),
    }


# ── Persistence ────────────────────────────────────────────────

def save_clusters(clusters: List[Dict], db_path: str):
    """Save detected clusters to SQLite."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whale_clusters (
            cluster_id TEXT PRIMARY KEY,
            addresses TEXT,
            size INTEGER,
            shared_markets INTEGER,
            combined_pnl REAL,
            likely_operator INTEGER,
            detected_at TEXT,
            last_updated TEXT
        )
    """)

    now = datetime.now().isoformat()
    for cluster in clusters:
        conn.execute("""
            INSERT OR REPLACE INTO whale_clusters
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cluster["cluster_id"],
            json.dumps(cluster["addresses"]),
            cluster["size"],
            cluster["shared_markets"],
            cluster["combined_pnl"],
            1 if cluster["likely_operator"] else 0,
            cluster["detected_at"],
            now,
        ))

    conn.commit()
    conn.close()


def load_clusters(db_path: str) -> List[Dict]:
    """Load clusters from SQLite."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whale_clusters (
            cluster_id TEXT PRIMARY KEY,
            addresses TEXT,
            size INTEGER,
            shared_markets INTEGER,
            combined_pnl REAL,
            likely_operator INTEGER,
            detected_at TEXT,
            last_updated TEXT
        )
    """)
    cursor = conn.execute("SELECT * FROM whale_clusters ORDER BY size DESC")
    clusters = []
    for row in cursor.fetchall():
        clusters.append({
            "cluster_id": row[0],
            "addresses": json.loads(row[1]),
            "size": row[2],
            "shared_markets": row[3],
            "combined_pnl": row[4],
            "likely_operator": bool(row[5]),
            "detected_at": row[6],
            "last_updated": row[7],
        })
    conn.close()
    return clusters


# ── CLI Test ───────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("WHALE CLUSTER — Graph-Based Wallet Clustering")
    print("=" * 60)

    from polymarket_api import PolymarketAPI

    api = PolymarketAPI(rate_limit=1.0)

    # Get top 10 wallets
    print("\nFetching leaderboard (top 10)...")
    leaders = api.get_leaderboard(limit=10)

    if not leaders:
        print("No leaderboard data. Exiting.")
        api.close()
        exit(1)

    wallets = {}
    pnl_lookup = {}

    for entry in leaders:
        addr = entry.get("proxyWallet") or entry.get("address", "")
        name = entry.get("userName") or addr[:10]
        pnl = float(entry.get("pnl", 0) or 0)

        print(f"  Building behavior for {name}...", end=" ")

        positions = api.get_positions(addr)
        closed = api.get_closed_positions(addr)
        activity = api.get_activity(addr)

        behavior = build_wallet_behavior(addr, positions, closed, activity)
        wallets[addr] = behavior
        pnl_lookup[addr] = pnl

        print(f"markets={len(behavior['markets'])}, "
              f"activity={len(behavior['timestamps'])}")

    # Build graph
    print(f"\nBuilding similarity graph (threshold=0.3)...")
    graph = build_similarity_graph(wallets, threshold=0.3)
    print(f"  Edges: {sum(len(v) for v in graph.values()) // 2}")

    # Find clusters
    clusters_raw = find_clusters(graph, min_size=2)
    print(f"  Clusters found: {len(clusters_raw)}")

    for cluster_addrs in clusters_raw:
        summary = summarize_cluster(cluster_addrs, wallets, pnl_lookup)
        names = []
        for a in cluster_addrs:
            for e in leaders:
                if e.get("proxyWallet") == a or e.get("address") == a:
                    names.append(e.get("userName", a[:10]))
                    break
        print(f"\n  Cluster {summary['cluster_id']}:")
        print(f"    Wallets: {', '.join(names)}")
        print(f"    Shared markets: {summary['shared_markets']}")
        print(f"    Combined PnL: ${summary['combined_pnl']:,.2f}")
        print(f"    Likely operator: {'YES' if summary['likely_operator'] else 'No'}")

    if not clusters_raw:
        print("  No clusters detected (wallets are independent)")

    api.close()
    print("\n[OK] Clustering complete")
