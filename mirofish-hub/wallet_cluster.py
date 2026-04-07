#!/usr/bin/env python3
"""
🔗 WALLET CLUSTER — Graph-based wallet relationship detection

Identifies:
1. Wallets that bet on the same markets at similar times
2. Wallets with identical position patterns
3. Potential Sybil accounts (same person, multiple wallets)
4. Copy-trading networks

Uses Jaccard similarity on market overlaps.

Usage:
    python wallet_cluster.py --build          # Build cluster graph
    python wallet_cluster.py --find 0x...     # Find related wallets
    python wallet_cluster.py --show           # Show all clusters
"""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple
from pathlib import Path
from collections import defaultdict
import json

# Database
DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"

# Clustering thresholds
MIN_SHARED_MARKETS = 3           # Need 3+ shared markets to consider
SIMILARITY_THRESHOLD = 0.4       # 40%+ Jaccard similarity = related
TIMING_WINDOW_MINUTES = 30       # Trades within 30 min = coordinated


class WalletCluster:
    """Graph-based wallet clustering."""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
    
    def _init_tables(self):
        """Create clustering tables."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS wallet_similarities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_a TEXT NOT NULL,
                wallet_b TEXT NOT NULL,
                similarity REAL,
                shared_markets INTEGER,
                timing_correlation REAL,
                cluster_id TEXT,
                detected_at TEXT,
                UNIQUE(wallet_a, wallet_b)
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS wallet_market_matrix (
                address TEXT NOT NULL,
                condition_id TEXT NOT NULL,
                side TEXT,
                entry_time TEXT,
                PRIMARY KEY(address, condition_id)
            )
        """)
        
        self.conn.commit()
    
    def build_market_matrix(self):
        """Build wallet-market matrix for similarity calculation."""
        print("[BUILD] Building wallet-market matrix...")
        
        # Clear old data
        self.conn.execute("DELETE FROM wallet_market_matrix")
        
        # Insert current positions
        self.conn.execute("""
            INSERT OR REPLACE INTO wallet_market_matrix 
            (address, condition_id, side, entry_time)
            SELECT address, condition_id, side, detected_at
            FROM whale_positions
            WHERE condition_id IS NOT NULL AND condition_id != ''
        """)
        
        self.conn.commit()
        
        count = self.conn.execute("SELECT COUNT(*) FROM wallet_market_matrix").fetchone()[0]
        print(f"[BUILD] Matrix built: {count} wallet-market pairs")
        
        return count
    
    def calculate_similarity(self, wallet_a: str, wallet_b: str) -> Dict:
        """
        Calculate Jaccard similarity between two wallets.
        
        Jaccard = |A ∩ B| / |A ∪ B|
        """
        # Get markets for each wallet
        markets_a = set(r[0] for r in self.conn.execute(
            "SELECT condition_id FROM wallet_market_matrix WHERE address = ?",
            (wallet_a,)
        ).fetchall())
        
        markets_b = set(r[0] for r in self.conn.execute(
            "SELECT condition_id FROM wallet_market_matrix WHERE address = ?",
            (wallet_b,)
        ).fetchall())
        
        if not markets_a or not markets_b:
            return {"similarity": 0, "shared": 0, "timing": 0}
        
        intersection = markets_a & markets_b
        union = markets_a | markets_b
        
        jaccard = len(intersection) / len(union) if union else 0
        
        # Calculate timing correlation for shared markets
        timing_score = 0
        if intersection:
            timing_score = self._calculate_timing_correlation(wallet_a, wallet_b, intersection)
        
        return {
            "similarity": jaccard,
            "shared": len(intersection),
            "timing": timing_score
        }
    
    def _calculate_timing_correlation(self, wallet_a: str, wallet_b: str, 
                                       shared_markets: Set[str]) -> float:
        """
        Calculate timing correlation - how often wallets trade within same window.
        """
        coordinated = 0
        total = len(shared_markets)
        
        for market in shared_markets:
            time_a = self.conn.execute(
                "SELECT entry_time FROM wallet_market_matrix WHERE address = ? AND condition_id = ?",
                (wallet_a, market)
            ).fetchone()
            
            time_b = self.conn.execute(
                "SELECT entry_time FROM wallet_market_matrix WHERE address = ? AND condition_id = ?",
                (wallet_b, market)
            ).fetchone()
            
            if time_a and time_b and time_a[0] and time_b[0]:
                try:
                    dt_a = datetime.fromisoformat(time_a[0].replace("Z", "+00:00"))
                    dt_b = datetime.fromisoformat(time_b[0].replace("Z", "+00:00"))
                    
                    diff_minutes = abs((dt_a - dt_b).total_seconds()) / 60
                    if diff_minutes <= TIMING_WINDOW_MINUTES:
                        coordinated += 1
                except:
                    continue
        
        return coordinated / total if total > 0 else 0
    
    def build_cluster_graph(self, min_trades: int = 10) -> Dict:
        """
        Build full cluster graph for all wallets.
        
        Returns cluster statistics.
        """
        print("[CLUSTER] Building cluster graph...")
        
        # First build the market matrix
        self.build_market_matrix()
        
        # Get all wallets with enough trades
        wallets = [r[0] for r in self.conn.execute("""
            SELECT address FROM wallet_market_matrix 
            GROUP BY address 
            HAVING COUNT(*) >= ?
        """, (min_trades,)).fetchall()]
        
        print(f"[CLUSTER] Analyzing {len(wallets)} wallets...")
        
        # Clear old similarities
        self.conn.execute("DELETE FROM wallet_similarities")
        
        pairs_found = 0
        clusters = defaultdict(set)
        cluster_id = 0
        
        # Compare all pairs (O(n²) but necessary)
        total_pairs = len(wallets) * (len(wallets) - 1) // 2
        checked = 0
        
        for i, wallet_a in enumerate(wallets):
            for wallet_b in wallets[i+1:]:
                checked += 1
                if checked % 1000 == 0:
                    print(f"  Progress: {checked}/{total_pairs} pairs ({pairs_found} related)")
                
                sim = self.calculate_similarity(wallet_a, wallet_b)
                
                if sim["shared"] >= MIN_SHARED_MARKETS and sim["similarity"] >= SIMILARITY_THRESHOLD:
                    # Find or create cluster
                    cid = None
                    for c, members in clusters.items():
                        if wallet_a in members or wallet_b in members:
                            cid = c
                            break
                    
                    if cid is None:
                        cid = f"cluster_{cluster_id}"
                        cluster_id += 1
                    
                    clusters[cid].add(wallet_a)
                    clusters[cid].add(wallet_b)
                    
                    # Save to database
                    self.conn.execute("""
                        INSERT OR REPLACE INTO wallet_similarities
                        (wallet_a, wallet_b, similarity, shared_markets, timing_correlation, cluster_id, detected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        wallet_a, wallet_b,
                        sim["similarity"],
                        sim["shared"],
                        sim["timing"],
                        cid,
                        datetime.now().isoformat()
                    ))
                    
                    pairs_found += 1
        
        self.conn.commit()
        
        print(f"[CLUSTER] Found {pairs_found} related pairs in {len(clusters)} clusters")
        
        return {
            "wallets_analyzed": len(wallets),
            "pairs_found": pairs_found,
            "clusters": len(clusters),
            "largest_cluster": max(len(c) for c in clusters.values()) if clusters else 0
        }
    
    def find_related_wallets(self, address: str) -> List[Dict]:
        """Find all wallets related to a given address."""
        rows = self.conn.execute("""
            SELECT 
                CASE WHEN wallet_a = ? THEN wallet_b ELSE wallet_a END as related,
                similarity,
                shared_markets,
                timing_correlation,
                cluster_id
            FROM wallet_similarities
            WHERE wallet_a = ? OR wallet_b = ?
            ORDER BY similarity DESC
        """, (address, address, address)).fetchall()
        
        results = []
        for r in rows:
            # Get stats for related wallet
            stats = self.conn.execute("""
                SELECT 
                    COUNT(*) as trades,
                    SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) as won,
                    SUM(size_usd) as total_size
                FROM whale_positions
                WHERE address = ?
            """, (r["related"],)).fetchone()
            
            results.append({
                "address": r["related"],
                "similarity": r["similarity"],
                "shared_markets": r["shared_markets"],
                "timing_correlation": r["timing_correlation"],
                "cluster_id": r["cluster_id"],
                "trades": stats["trades"] if stats else 0,
                "won": stats["won"] if stats else 0,
                "total_size": stats["total_size"] if stats else 0
            })
        
        return results
    
    def get_all_clusters(self) -> List[Dict]:
        """Get all clusters with member details."""
        clusters = defaultdict(list)
        
        rows = self.conn.execute("""
            SELECT DISTINCT cluster_id, wallet_a, wallet_b
            FROM wallet_similarities
            WHERE cluster_id IS NOT NULL
        """).fetchall()
        
        for r in rows:
            cid = r["cluster_id"]
            clusters[cid].append(r["wallet_a"])
            clusters[cid].append(r["wallet_b"])
        
        results = []
        for cid, wallets in clusters.items():
            unique_wallets = list(set(wallets))
            
            # Get aggregate stats
            total_size = 0
            total_pnl = 0
            
            for w in unique_wallets[:10]:  # Limit for performance
                row = self.conn.execute("""
                    SELECT SUM(size_usd) as size, SUM(COALESCE(actual_pnl, 0)) as pnl
                    FROM whale_positions WHERE address = ?
                """, (w,)).fetchone()
                if row:
                    total_size += row["size"] or 0
                    total_pnl += row["pnl"] or 0
            
            results.append({
                "cluster_id": cid,
                "size": len(unique_wallets),
                "wallets": unique_wallets[:5],  # First 5 for display
                "total_size": total_size,
                "total_pnl": total_pnl
            })
        
        # Sort by cluster size
        results.sort(key=lambda x: x["size"], reverse=True)
        return results
    
    def get_coordinated_trades(self, cluster_id: str) -> List[Dict]:
        """Get trades where cluster members acted together."""
        # Get cluster members
        members = set()
        rows = self.conn.execute("""
            SELECT wallet_a, wallet_b FROM wallet_similarities
            WHERE cluster_id = ?
        """, (cluster_id,)).fetchall()
        
        for r in rows:
            members.add(r["wallet_a"])
            members.add(r["wallet_b"])
        
        if not members:
            return []
        
        # Find markets where multiple cluster members traded
        placeholders = ",".join("?" * len(members))
        rows = self.conn.execute(f"""
            SELECT 
                market_title,
                condition_id,
                COUNT(DISTINCT address) as member_count,
                GROUP_CONCAT(DISTINCT side) as sides,
                SUM(size_usd) as total_size,
                AVG(entry_price) as avg_price
            FROM whale_positions
            WHERE address IN ({placeholders})
            GROUP BY condition_id
            HAVING member_count >= 2
            ORDER BY member_count DESC, total_size DESC
            LIMIT 20
        """, list(members)).fetchall()
        
        return [dict(r) for r in rows]
    
    def close(self):
        """Close database connection."""
        self.conn.close()


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Wallet Clustering")
    parser.add_argument("--build", action="store_true", help="Build cluster graph")
    parser.add_argument("--find", type=str, help="Find wallets related to address")
    parser.add_argument("--show", action="store_true", help="Show all clusters")
    parser.add_argument("--cluster", type=str, help="Show cluster details")
    parser.add_argument("--min-trades", type=int, default=5, help="Min trades to include")
    args = parser.parse_args()
    
    cluster = WalletCluster()
    
    try:
        if args.build:
            stats = cluster.build_cluster_graph(args.min_trades)
            
            print("\n" + "=" * 60)
            print("CLUSTER BUILD COMPLETE")
            print("=" * 60)
            print(f"Wallets analyzed: {stats['wallets_analyzed']}")
            print(f"Related pairs: {stats['pairs_found']}")
            print(f"Clusters found: {stats['clusters']}")
            print(f"Largest cluster: {stats['largest_cluster']} wallets")
        
        elif args.find:
            results = cluster.find_related_wallets(args.find)
            
            print("\n" + "=" * 60)
            print(f"RELATED WALLETS: {args.find[:20]}...")
            print("=" * 60)
            
            if not results:
                print("No related wallets found")
            else:
                for r in results:
                    print(f"\n  {r['address'][:20]}...")
                    print(f"    Similarity: {r['similarity']:.1%} | Shared: {r['shared_markets']} markets")
                    print(f"    Timing correlation: {r['timing_correlation']:.1%}")
                    print(f"    Cluster: {r['cluster_id']}")
                    print(f"    Stats: {r['trades']} trades, ${r['total_size']:,.0f}")
        
        elif args.show:
            clusters = cluster.get_all_clusters()
            
            print("\n" + "=" * 60)
            print("ALL WALLET CLUSTERS")
            print("=" * 60)
            
            for c in clusters:
                print(f"\n[{c['cluster_id']}] {c['size']} wallets")
                print(f"  Total size: ${c['total_size']:,.0f} | P&L: ${c['total_pnl']:,.0f}")
                for w in c['wallets']:
                    print(f"    - {w[:25]}...")
        
        elif args.cluster:
            trades = cluster.get_coordinated_trades(args.cluster)
            
            print("\n" + "=" * 60)
            print(f"COORDINATED TRADES: {args.cluster}")
            print("=" * 60)
            
            for t in trades:
                print(f"\n  {t['market_title'][:50]}...")
                print(f"    Members: {t['member_count']} | Sides: {t['sides']}")
                print(f"    Total size: ${t['total_size']:,.0f}")
        
        else:
            print("Usage: python wallet_cluster.py [--build|--find|--show|--cluster]")
    
    finally:
        cluster.close()


if __name__ == "__main__":
    main()
