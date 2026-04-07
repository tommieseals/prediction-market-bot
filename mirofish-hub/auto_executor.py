#!/usr/bin/env python3
"""
🤖 AUTO EXECUTOR — Automated Trade Execution for Polymarket

Executes validated signals with:
- Fee-aware profitability check
- Kelly position sizing
- Risk limits (max position size)
- Dry-run mode for testing
- Telegram execution confirmations

Usage:
    from auto_executor import AutoExecutor
    executor = AutoExecutor(dry_run=True)  # Test mode
    result = executor.execute_signal(signal)
"""

import os
import sqlite3
import requests
from datetime import datetime
from typing import Dict, Optional, Tuple
from pathlib import Path
from decimal import Decimal

# Load environment
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# Database
DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"

# Telegram config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ══════════════════════════════════════════════════════════════
# RISK CONFIGURATION
# ══════════════════════════════════════════════════════════════

# Fee structure (Polymarket March 2026+)
TAKER_FEE_PCT = 0.01         # ~1% taker fee
MAKER_REBATE_PCT = 0.0025    # 0.25% maker rebate on limit orders

# Position limits
MIN_PROFITABLE_EDGE = 0.05   # 5% minimum net edge after fees
MAX_POSITION_USD = 25.0      # Max $25 per trade (conservative start)
MIN_POSITION_USD = 2.0       # Min $2 to be worth the gas
MAX_KELLY_FRACTION = 0.25    # Cap Kelly at 25% of bankroll
DEFAULT_BANKROLL = 90.0      # Current wallet balance

# Execution settings
SLIPPAGE_TOLERANCE = 0.02    # 2% max slippage from signal price


class AutoExecutor:
    """
    Automated trade executor for Polymarket signals.
    
    Handles:
    - Fee-aware profitability checks
    - Kelly-based position sizing
    - Trade execution via py-clob-client
    - Execution logging and alerts
    """
    
    def __init__(self, dry_run: bool = True, bankroll: float = DEFAULT_BANKROLL):
        """
        Initialize executor.
        
        Args:
            dry_run: If True, simulate trades without executing
            bankroll: Available capital for position sizing
        """
        self.dry_run = dry_run
        self.bankroll = bankroll
        self.trader = None
        self._init_trader()
        self._init_db()
    
    def _init_trader(self):
        """Initialize Polymarket trader."""
        try:
            from polymarket_trader import PolymarketTrader
            private_key = os.getenv("POLY_PRIVATE_KEY", "")
            proxy = os.getenv("POLY_PROXY", "")
            if private_key:
                self.trader = PolymarketTrader(private_key, proxy if proxy else None)
                print("[EXECUTOR] Trader initialized")
            else:
                print("[EXECUTOR] No private key - dry run only")
        except Exception as e:
            print(f"[EXECUTOR] Trader init failed: {e}")
    
    def _init_db(self):
        """Initialize execution tracking table."""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id TEXT,
                    market TEXT,
                    side TEXT,
                    entry_price REAL,
                    size_usd REAL,
                    shares REAL,
                    edge REAL,
                    kelly REAL,
                    dry_run INTEGER,
                    status TEXT,
                    order_id TEXT,
                    error TEXT,
                    executed_at TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[EXECUTOR] DB init failed: {e}")
    
    def check_profitability(self, edge: float, order_type: str = "limit") -> Dict:
        """
        Check if trade is profitable after fees.
        
        Args:
            edge: Expected edge as decimal (0.08 = 8%)
            order_type: "limit" (maker) or "market" (taker)
        
        Returns:
            Dict with profitability assessment
        """
        if order_type == "market":
            fee = TAKER_FEE_PCT
        else:
            fee = -MAKER_REBATE_PCT  # Negative = we earn rebate
        
        net_edge = edge - fee
        profitable = net_edge >= MIN_PROFITABLE_EDGE
        
        return {
            "profitable": profitable,
            "gross_edge": round(edge, 4),
            "fee": round(fee, 4),
            "net_edge": round(net_edge, 4),
            "min_required": MIN_PROFITABLE_EDGE,
            "recommendation": "EXECUTE" if profitable else "SKIP - edge too thin"
        }
    
    def calculate_position_size(self, signal: Dict) -> Tuple[float, float]:
        """
        Calculate position size using Kelly criterion.
        
        Args:
            signal: Signal dict with kelly fraction and entry_price
        
        Returns:
            Tuple of (size_usd, shares)
        """
        kelly = signal.get("kelly", 0.05)
        entry_price = signal.get("entry_price", 0.5)
        
        # Cap Kelly fraction
        kelly = min(kelly, MAX_KELLY_FRACTION)
        
        # Calculate position
        size_usd = self.bankroll * kelly
        
        # Apply limits
        size_usd = max(MIN_POSITION_USD, min(size_usd, MAX_POSITION_USD))
        
        # Calculate shares
        shares = size_usd / entry_price if entry_price > 0 else 0
        
        return round(size_usd, 2), round(shares, 2)
    
    def execute_signal(self, signal: Dict) -> Dict:
        """
        Execute a validated trading signal.
        
        Args:
            signal: Signal dict from consensus_swarm_connector
        
        Returns:
            Execution result dict
        """
        result = {
            "signal_id": signal.get("signal_id", "unknown"),
            "market": signal.get("market", ""),
            "executed": False,
            "dry_run": self.dry_run,
            "timestamp": datetime.now().isoformat()
        }
        
        # Step 1: Check profitability
        edge_pct = signal.get("edge", 0) / 100  # Convert from % to decimal
        profit_check = self.check_profitability(edge_pct)
        
        if not profit_check["profitable"]:
            result["status"] = "SKIPPED"
            result["reason"] = f"Edge too thin: {profit_check['net_edge']:.1%} < {MIN_PROFITABLE_EDGE:.1%}"
            self._log_execution(result, signal)
            return result
        
        # Step 2: Calculate position size
        size_usd, shares = self.calculate_position_size(signal)
        result["size_usd"] = size_usd
        result["shares"] = shares
        
        if size_usd < MIN_POSITION_USD:
            result["status"] = "SKIPPED"
            result["reason"] = f"Position too small: ${size_usd} < ${MIN_POSITION_USD}"
            self._log_execution(result, signal)
            return result
        
        # Step 3: Get token ID
        token_id = signal.get("token_id") or signal.get("condition_id")
        if not token_id:
            result["status"] = "ERROR"
            result["reason"] = "No token_id in signal"
            self._log_execution(result, signal)
            return result
        
        # Step 4: Execute or simulate
        side = signal.get("side", "YES")
        entry_price = signal.get("entry_price", 0.5)
        
        if self.dry_run:
            result["status"] = "DRY_RUN"
            result["executed"] = True
            result["simulated_order"] = {
                "token_id": token_id,
                "side": "BUY",  # We buy the side (YES/NO) we're betting on
                "price": entry_price,
                "size": shares
            }
            print(f"   [DRY RUN] Would buy {shares:.1f} {side} @ ${entry_price:.2f} = ${size_usd:.2f}")
        else:
            if not self.trader:
                result["status"] = "ERROR"
                result["reason"] = "Trader not initialized"
                self._log_execution(result, signal)
                return result
            
            try:
                # Execute real trade
                order_result = self.trader.place_order(
                    token_id=token_id,
                    side="BUY",
                    price=entry_price,
                    size=shares,
                    edge=edge_pct
                )
                
                if "error" in order_result:
                    result["status"] = "FAILED"
                    result["reason"] = order_result["error"]
                else:
                    result["status"] = "EXECUTED"
                    result["executed"] = True
                    result["order_id"] = order_result.get("order_id", "")
                    result["order_result"] = order_result
                    
            except Exception as e:
                result["status"] = "ERROR"
                result["reason"] = str(e)
        
        # Log and alert
        self._log_execution(result, signal)
        
        if result["executed"]:
            self._send_execution_alert(result, signal)
        
        return result
    
    def _log_execution(self, result: Dict, signal: Dict):
        """Log execution to database."""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30)
            conn.execute("""
                INSERT INTO trade_executions 
                (signal_id, market, side, entry_price, size_usd, shares, 
                 edge, kelly, dry_run, status, order_id, error, executed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.get("signal_id"),
                signal.get("market", "")[:100],
                signal.get("side"),
                signal.get("entry_price"),
                result.get("size_usd", 0),
                result.get("shares", 0),
                signal.get("edge", 0),
                signal.get("kelly", 0),
                1 if result.get("dry_run") else 0,
                result.get("status"),
                result.get("order_id"),
                result.get("reason"),
                result.get("timestamp")
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"   [WARN] Execution log failed: {e}")
    
    def _send_execution_alert(self, result: Dict, signal: Dict):
        """Send Telegram alert for execution."""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return
        
        status_emoji = "✅" if result["status"] == "EXECUTED" else "🔄"
        mode = "[DRY RUN] " if result["dry_run"] else ""
        
        message = f"""
{status_emoji} <b>{mode}TRADE EXECUTED</b> {status_emoji}

<b>Market:</b> {signal.get('market', '')[:50]}
<b>Side:</b> {signal.get('side')} @ ${signal.get('entry_price', 0):.2f}

<b>Position:</b>
• Size: ${result.get('size_usd', 0):.2f}
• Shares: {result.get('shares', 0):.1f}
• Edge: +{signal.get('edge', 0):.1f}%

<b>Status:</b> {result.get('status')}
"""
        
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            }, timeout=10)
        except Exception as e:
            print(f"   [WARN] Alert failed: {e}")
    
    def get_execution_stats(self) -> Dict:
        """Get execution statistics."""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30)
            
            stats = {}
            
            # Total executions
            row = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'EXECUTED' THEN 1 ELSE 0 END) as executed,
                    SUM(CASE WHEN status = 'DRY_RUN' THEN 1 ELSE 0 END) as dry_runs,
                    SUM(CASE WHEN status = 'SKIPPED' THEN 1 ELSE 0 END) as skipped,
                    SUM(CASE WHEN status IN ('EXECUTED', 'DRY_RUN') THEN size_usd ELSE 0 END) as total_size
                FROM trade_executions
            """).fetchone()
            
            stats = {
                "total": row[0] or 0,
                "executed": row[1] or 0,
                "dry_runs": row[2] or 0,
                "skipped": row[3] or 0,
                "total_size_usd": row[4] or 0
            }
            
            conn.close()
            return stats
            
        except Exception as e:
            return {"error": str(e)}


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto Executor for Polymarket")
    parser.add_argument("--stats", action="store_true", help="Show execution stats")
    parser.add_argument("--test", action="store_true", help="Test with mock signal")
    parser.add_argument("--live", action="store_true", help="Enable live trading (no dry run)")
    args = parser.parse_args()
    
    executor = AutoExecutor(dry_run=not args.live)
    
    if args.stats:
        stats = executor.get_execution_stats()
        print("\n[STATS] EXECUTION STATS")
        print("=" * 40)
        for k, v in stats.items():
            print(f"  {k}: {v}")
    
    elif args.test:
        # Test with mock signal
        mock_signal = {
            "signal_id": "test-001",
            "market": "Test Market: Will something happen?",
            "side": "YES",
            "entry_price": 0.45,
            "edge": 12.0,  # 12% edge
            "kelly": 0.10,
            "whale_count": 5,
            "agreement": 85,
            "confidence": 80,
            "token_id": "test-token-123",
            "condition_id": "test-condition-123"
        }
        
        print("\n[TEST] EXECUTION")
        print("=" * 40)
        print(f"Signal: {mock_signal['market']}")
        print(f"Side: {mock_signal['side']} @ ${mock_signal['entry_price']}")
        print(f"Edge: {mock_signal['edge']}%")
        print()
        
        result = executor.execute_signal(mock_signal)
        
        print(f"\nResult: {result['status']}")
        if result.get('size_usd'):
            print(f"Size: ${result['size_usd']}")
        if result.get('reason'):
            print(f"Reason: {result['reason']}")
    
    else:
        print("Usage: python auto_executor.py [--stats|--test|--live]")
        print("\nOptions:")
        print("  --stats  Show execution statistics")
        print("  --test   Test with mock signal (dry run)")
        print("  --live   Enable live trading")
