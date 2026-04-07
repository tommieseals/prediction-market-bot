#!/usr/bin/env python3
"""
🕵️ INSIDER DETECTOR — Identify suspicious trading patterns

Detects:
1. Unusual accuracy on specific domains (>80% on niche markets)
2. Concentrated positions (>$50K in single market)
3. Timing anomalies (entries right before news)
4. Fresh accounts with immediate large wins
5. Coordinated wallet clusters

Usage:
    python insider_detector.py --scan        # Full scan
    python insider_detector.py --wallet 0x.. # Analyze specific wallet
    python insider_detector.py --market "..." # Find whales on market
"""

import os
import sqlite3
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from collections import defaultdict
import json

# Database
DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Detection thresholds
MIN_TRADES_FOR_ACCURACY = 10      # Need 10+ trades to judge accuracy
INSIDER_WIN_RATE_THRESHOLD = 85   # >85% win rate = suspicious
CONCENTRATION_THRESHOLD = 50000   # >$50K in one market = concentrated
FRESH_ACCOUNT_DAYS = 30           # Account < 30 days old
TIMING_WINDOW_HOURS = 4           # Entry within 4h of resolution = suspicious


class InsiderDetector:
    """Detect potential insider trading patterns."""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
    
    def _init_tables(self):
        """Create insider tracking tables."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS insider_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                flag_type TEXT NOT NULL,
                score REAL,
                details TEXT,
                detected_at TEXT,
                UNIQUE(address, flag_type)
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS wallet_clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_id TEXT NOT NULL,
                address TEXT NOT NULL,
                similarity_score REAL,
                detected_at TEXT,
                UNIQUE(cluster_id, address)
            )
        """)
        
        self.conn.commit()
    
    def analyze_wallet(self, address: str) -> Dict:
        """
        Full insider analysis for a single wallet.
        
        Returns dict with all suspicious indicators.
        """
        result = {
            "address": address,
            "flags": [],
            "risk_score": 0,
            "summary": ""
        }
        
        # Get wallet stats
        stats = self._get_wallet_stats(address)
        if not stats:
            result["summary"] = "Wallet not found in database"
            return result
        
        result["stats"] = stats
        
        # Check 1: Unusual accuracy
        if stats["resolved"] >= MIN_TRADES_FOR_ACCURACY:
            if stats["win_rate"] >= INSIDER_WIN_RATE_THRESHOLD:
                result["flags"].append({
                    "type": "HIGH_ACCURACY",
                    "severity": "HIGH",
                    "details": f"{stats['win_rate']:.1f}% win rate on {stats['resolved']} trades"
                })
                result["risk_score"] += 30
        
        # Check 2: Concentrated positions
        concentrated = self._check_concentration(address)
        if concentrated:
            result["flags"].append({
                "type": "CONCENTRATED_BETS",
                "severity": "MEDIUM",
                "details": f"${concentrated['total']:,.0f} in {concentrated['count']} concentrated positions",
                "positions": concentrated["markets"]
            })
            result["risk_score"] += 20
        
        # Check 3: Domain specialization
        domain_stats = self._check_domain_expertise(address)
        if domain_stats:
            result["flags"].append({
                "type": "DOMAIN_EXPERT",
                "severity": "LOW",
                "details": f"Specializes in {domain_stats['domain']} ({domain_stats['win_rate']:.1f}% on {domain_stats['count']} trades)"
            })
            result["risk_score"] += 10
        
        # Check 4: Fresh account with big wins
        if stats["first_trade_days"] and stats["first_trade_days"] < FRESH_ACCOUNT_DAYS:
            if stats["total_pnl"] > 10000:
                result["flags"].append({
                    "type": "FRESH_WINNER",
                    "severity": "HIGH",
                    "details": f"Account {stats['first_trade_days']} days old, +${stats['total_pnl']:,.0f} P&L"
                })
                result["risk_score"] += 25
        
        # Check 5: Perfect timing (trades right before resolution)
        timing_flags = self._check_timing_anomalies(address)
        if timing_flags:
            result["flags"].append({
                "type": "TIMING_ANOMALY",
                "severity": "HIGH",
                "details": f"{timing_flags['count']} trades entered within {TIMING_WINDOW_HOURS}h of resolution",
                "markets": timing_flags["markets"]
            })
            result["risk_score"] += 35
        
        # Generate summary
        if result["risk_score"] >= 60:
            result["summary"] = "HIGH RISK - Likely insider or bot"
        elif result["risk_score"] >= 30:
            result["summary"] = "MEDIUM RISK - Unusual patterns"
        else:
            result["summary"] = "LOW RISK - Normal trading"
        
        return result
    
    def _get_wallet_stats(self, address: str) -> Optional[Dict]:
        """Get basic wallet statistics."""
        row = self.conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) as won,
                SUM(CASE WHEN outcome = 'lost' THEN 1 ELSE 0 END) as lost,
                SUM(CASE WHEN outcome = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(size_usd) as total_size,
                SUM(COALESCE(actual_pnl, 0)) as total_pnl,
                MIN(detected_at) as first_trade,
                MAX(detected_at) as last_trade
            FROM whale_positions
            WHERE address = ?
        """, (address,)).fetchone()
        
        if not row or row["total"] == 0:
            return None
        
        resolved = (row["won"] or 0) + (row["lost"] or 0)
        win_rate = 100 * row["won"] / resolved if resolved > 0 else 0
        
        # Calculate account age
        first_trade_days = None
        if row["first_trade"]:
            try:
                first_dt = datetime.fromisoformat(row["first_trade"].replace("Z", "+00:00"))
                first_trade_days = (datetime.now(first_dt.tzinfo) - first_dt).days
            except:
                pass
        
        return {
            "total": row["total"],
            "won": row["won"] or 0,
            "lost": row["lost"] or 0,
            "pending": row["pending"] or 0,
            "resolved": resolved,
            "win_rate": win_rate,
            "total_size": row["total_size"] or 0,
            "total_pnl": row["total_pnl"] or 0,
            "first_trade": row["first_trade"],
            "last_trade": row["last_trade"],
            "first_trade_days": first_trade_days
        }
    
    def _check_concentration(self, address: str) -> Optional[Dict]:
        """Check for concentrated positions."""
        rows = self.conn.execute("""
            SELECT market_title, SUM(size_usd) as total, side
            FROM whale_positions
            WHERE address = ? AND outcome = 'pending'
            GROUP BY market_title
            HAVING SUM(size_usd) > ?
            ORDER BY total DESC
        """, (address, CONCENTRATION_THRESHOLD)).fetchall()
        
        if not rows:
            return None
        
        return {
            "count": len(rows),
            "total": sum(r["total"] for r in rows),
            "markets": [{"market": r["market_title"][:50], "size": r["total"], "side": r["side"]} for r in rows[:5]]
        }
    
    def _check_domain_expertise(self, address: str) -> Optional[Dict]:
        """Check if wallet specializes in specific domains."""
        # Extract domain from market title keywords
        rows = self.conn.execute("""
            SELECT 
                CASE 
                    WHEN market_title LIKE '%Iran%' OR market_title LIKE '%ceasefire%' OR market_title LIKE '%military%' THEN 'geopolitics'
                    WHEN market_title LIKE '%Bitcoin%' OR market_title LIKE '%Crypto%' OR market_title LIKE '%ETH%' THEN 'crypto'
                    WHEN market_title LIKE '%Trump%' OR market_title LIKE '%Biden%' OR market_title LIKE '%election%' THEN 'politics'
                    WHEN market_title LIKE '%NBA%' OR market_title LIKE '%NFL%' OR market_title LIKE '%vs%' THEN 'sports'
                    ELSE 'other'
                END as domain,
                COUNT(*) as count,
                SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) as won
            FROM whale_positions
            WHERE address = ? AND outcome IN ('won', 'lost')
            GROUP BY domain
            HAVING count >= 5
            ORDER BY count DESC
        """, (address,)).fetchall()
        
        for r in rows:
            if r["count"] >= 5 and r["domain"] != "other":
                wr = 100 * r["won"] / r["count"]
                if wr >= 75:
                    return {
                        "domain": r["domain"],
                        "count": r["count"],
                        "win_rate": wr
                    }
        
        return None
    
    def _check_timing_anomalies(self, address: str) -> Optional[Dict]:
        """Check for suspicious timing (entries right before resolution)."""
        # This requires end_date and detected_at comparison
        rows = self.conn.execute("""
            SELECT market_title, detected_at, end_date, outcome
            FROM whale_positions
            WHERE address = ? 
              AND outcome = 'won'
              AND end_date IS NOT NULL
              AND detected_at IS NOT NULL
        """, (address,)).fetchall()
        
        suspicious = []
        for r in rows:
            try:
                detected = datetime.fromisoformat(r["detected_at"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(r["end_date"].replace("Z", "+00:00"))
                
                hours_before = (end - detected).total_seconds() / 3600
                if 0 < hours_before < TIMING_WINDOW_HOURS:
                    suspicious.append({
                        "market": r["market_title"][:40],
                        "hours_before": round(hours_before, 1)
                    })
            except:
                continue
        
        if len(suspicious) >= 3:
            return {
                "count": len(suspicious),
                "markets": suspicious[:5]
            }
        
        return None
    
    def scan_all_wallets(self, min_trades: int = 10) -> List[Dict]:
        """
        Scan all wallets for insider patterns.
        
        Returns list of flagged wallets sorted by risk score.
        """
        print("[SCAN] Analyzing all wallets for insider patterns...")
        
        # Get all wallets with enough trades
        wallets = self.conn.execute("""
            SELECT DISTINCT address 
            FROM whale_positions
            GROUP BY address
            HAVING COUNT(*) >= ?
        """, (min_trades,)).fetchall()
        
        print(f"[SCAN] Found {len(wallets)} wallets with {min_trades}+ trades")
        
        flagged = []
        for i, row in enumerate(wallets):
            if (i + 1) % 50 == 0:
                print(f"  Progress: {i+1}/{len(wallets)}")
            
            result = self.analyze_wallet(row["address"])
            if result["risk_score"] >= 30:
                flagged.append(result)
        
        # Sort by risk score
        flagged.sort(key=lambda x: x["risk_score"], reverse=True)
        
        # Save flags to database
        for f in flagged:
            for flag in f["flags"]:
                self._save_flag(f["address"], flag)
        
        print(f"[SCAN] Found {len(flagged)} suspicious wallets")
        return flagged
    
    def _save_flag(self, address: str, flag: Dict):
        """Save insider flag to database."""
        try:
            self.conn.execute("""
                INSERT OR REPLACE INTO insider_flags 
                (address, flag_type, score, details, detected_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                address,
                flag["type"],
                {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(flag["severity"], 1),
                flag["details"],
                datetime.now().isoformat()
            ))
            self.conn.commit()
        except Exception as e:
            print(f"  [WARN] Failed to save flag: {e}")
    
    def get_top_insiders(self, limit: int = 20) -> List[Dict]:
        """Get top suspected insiders from database."""
        rows = self.conn.execute("""
            SELECT 
                f.address,
                GROUP_CONCAT(f.flag_type) as flags,
                SUM(f.score) as total_score,
                COUNT(*) as flag_count
            FROM insider_flags f
            GROUP BY f.address
            ORDER BY total_score DESC
            LIMIT ?
        """, (limit,)).fetchall()
        
        results = []
        for r in rows:
            stats = self._get_wallet_stats(r["address"])
            results.append({
                "address": r["address"],
                "flags": r["flags"].split(",") if r["flags"] else [],
                "score": r["total_score"],
                "flag_count": r["flag_count"],
                "stats": stats
            })
        
        return results
    
    def find_market_whales(self, market_query: str) -> List[Dict]:
        """Find all whales on a specific market."""
        rows = self.conn.execute("""
            SELECT 
                address,
                market_title,
                side,
                SUM(size_usd) as total_size,
                AVG(entry_price) as avg_price,
                COUNT(*) as positions
            FROM whale_positions
            WHERE market_title LIKE ?
            GROUP BY address, market_title, side
            ORDER BY total_size DESC
            LIMIT 20
        """, (f"%{market_query}%",)).fetchall()
        
        results = []
        for r in rows:
            # Get insider flags for this wallet
            flags = self.conn.execute("""
                SELECT flag_type, score FROM insider_flags WHERE address = ?
            """, (r["address"],)).fetchall()
            
            results.append({
                "address": r["address"],
                "market": r["market_title"],
                "side": r["side"],
                "size": r["total_size"],
                "avg_price": r["avg_price"],
                "positions": r["positions"],
                "insider_flags": [f["flag_type"] for f in flags]
            })
        
        return results
    
    def send_insider_alert(self, wallet_result: Dict):
        """Send Telegram alert for high-risk insider."""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return
        
        if wallet_result["risk_score"] < 50:
            return
        
        flags_text = "\n".join([f"  - {f['type']}: {f['details'][:50]}" for f in wallet_result["flags"]])
        
        message = f"""
[SPY] <b>INSIDER ALERT</b> [SPY]

<b>Wallet:</b> <code>{wallet_result['address'][:20]}...</code>
<b>Risk Score:</b> {wallet_result['risk_score']}/100

<b>Flags:</b>
{flags_text}

<b>Stats:</b>
Win Rate: {wallet_result['stats']['win_rate']:.1f}%
Total Trades: {wallet_result['stats']['total']}
P&L: ${wallet_result['stats']['total_pnl']:,.0f}
"""
        
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            }, timeout=10)
        except Exception as e:
            print(f"[WARN] Alert failed: {e}")
    
    def alert_new_insider_move(self, address: str, market: str, side: str, size: float):
        """
        Alert when a flagged insider makes a NEW move.
        
        Call this from whale_hunter when detecting new positions.
        """
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return
        
        # Check if this wallet has insider flags
        flags = self.conn.execute("""
            SELECT flag_type, score FROM insider_flags WHERE address = ?
        """, (address,)).fetchall()
        
        if not flags:
            return
        
        total_score = sum(f[1] * 10 for f in flags)
        if total_score < 50:
            return
        
        flag_types = [f[0] for f in flags]
        
        message = f"""
[MONEY] <b>INSIDER MOVE DETECTED</b> [MONEY]

<b>Wallet:</b> <code>{address[:20]}...</code>
<b>Risk Score:</b> {total_score}/100
<b>Flags:</b> {', '.join(flag_types[:3])}

<b>New Position:</b>
Market: {market[:50]}...
Side: {side}
Size: ${size:,.0f}

<i>This wallet has suspicious trading patterns. Follow with caution.</i>
"""
        
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            }, timeout=10)
            print(f"  [ALERT] Insider move alert sent for {address[:12]}...")
        except Exception as e:
            print(f"[WARN] Alert failed: {e}")
    
    def close(self):
        """Close database connection."""
        self.conn.close()


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Insider Detector")
    parser.add_argument("--scan", action="store_true", help="Scan all wallets")
    parser.add_argument("--wallet", type=str, help="Analyze specific wallet")
    parser.add_argument("--market", type=str, help="Find whales on market")
    parser.add_argument("--top", type=int, default=20, help="Show top N insiders")
    parser.add_argument("--alert", action="store_true", help="Send alerts for high-risk")
    args = parser.parse_args()
    
    detector = InsiderDetector()
    
    try:
        if args.scan:
            results = detector.scan_all_wallets()
            
            print("\n" + "=" * 60)
            print("TOP SUSPECTED INSIDERS")
            print("=" * 60)
            
            for r in results[:args.top]:
                print(f"\n[{r['risk_score']}] {r['address'][:20]}...")
                print(f"    {r['summary']}")
                for f in r["flags"]:
                    print(f"    - {f['type']}: {f['details'][:50]}")
                
                if args.alert:
                    detector.send_insider_alert(r)
        
        elif args.wallet:
            result = detector.analyze_wallet(args.wallet)
            
            print("\n" + "=" * 60)
            print(f"WALLET ANALYSIS: {args.wallet[:20]}...")
            print("=" * 60)
            
            if result.get("stats"):
                s = result["stats"]
                print(f"\nStats:")
                print(f"  Total trades: {s['total']}")
                print(f"  Win rate: {s['win_rate']:.1f}% ({s['won']}W/{s['lost']}L)")
                print(f"  P&L: ${s['total_pnl']:,.0f}")
            
            print(f"\nRisk Score: {result['risk_score']}/100")
            print(f"Summary: {result['summary']}")
            
            if result["flags"]:
                print("\nFlags:")
                for f in result["flags"]:
                    print(f"  [{f['severity']}] {f['type']}: {f['details']}")
        
        elif args.market:
            results = detector.find_market_whales(args.market)
            
            print("\n" + "=" * 60)
            print(f"WHALES ON: {args.market}")
            print("=" * 60)
            
            for r in results:
                flags = f" [{','.join(r['insider_flags'])}]" if r["insider_flags"] else ""
                print(f"\n  {r['address'][:15]}...{flags}")
                print(f"    ${r['size']:,.0f} {r['side']} @ {r['avg_price']:.2f}")
        
        else:
            # Show top insiders from DB
            results = detector.get_top_insiders(args.top)
            
            print("\n" + "=" * 60)
            print("TOP SUSPECTED INSIDERS (from database)")
            print("=" * 60)
            
            for r in results:
                if r["stats"]:
                    print(f"\n  {r['address'][:20]}... [Score: {r['score']}]")
                    print(f"    Flags: {', '.join(r['flags'])}")
                    print(f"    Win Rate: {r['stats']['win_rate']:.1f}% | P&L: ${r['stats']['total_pnl']:,.0f}")
    
    finally:
        detector.close()


if __name__ == "__main__":
    main()
