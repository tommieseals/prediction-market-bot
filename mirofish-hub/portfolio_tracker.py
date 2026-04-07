# -*- coding: utf-8 -*-
"""
Real portfolio tracking - wallet balance + positions
"""
import sqlite3
import requests
from web3 import Web3
from datetime import datetime

# Polygon RPC
RPC_URL = "https://rpc-mainnet.matic.quiknode.pro"
WALLET = "0x299aCc0857B943d8490ECb1820fD458B3B58c728"

# USDC contracts on Polygon
USDC_NATIVE = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
USDC_BRIDGED = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

ERC20_ABI = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},{"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}]

def get_wallet_balance():
    """Get USDC balance from Polygon wallet."""
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        
        # MATIC balance
        matic = w3.eth.get_balance(WALLET) / 1e18
        
        # USDC native
        usdc_native_contract = w3.eth.contract(address=Web3.to_checksum_address(USDC_NATIVE), abi=ERC20_ABI)
        usdc_native = usdc_native_contract.functions.balanceOf(WALLET).call() / 1e6
        
        # USDC.e bridged
        usdc_bridged_contract = w3.eth.contract(address=Web3.to_checksum_address(USDC_BRIDGED), abi=ERC20_ABI)
        usdc_bridged = usdc_bridged_contract.functions.balanceOf(WALLET).call() / 1e6
        
        return {
            "matic": round(matic, 4),
            "usdc_native": round(usdc_native, 2),
            "usdc_bridged": round(usdc_bridged, 2),
            "total_usdc": round(usdc_native + usdc_bridged, 2)
        }
    except Exception as e:
        return {"error": str(e), "total_usdc": 0}

def get_positions_summary():
    """Get positions summary from my_trades table."""
    try:
        conn = sqlite3.connect('data/whale_hunter.db', timeout=10)
        cur = conn.cursor()
        
        # Get all trades
        cur.execute("""
            SELECT outcome, COUNT(*), SUM(cost), SUM(pnl) 
            FROM my_trades 
            WHERE outcome != 'cancelled'
            GROUP BY outcome
        """)
        
        results = {}
        for row in cur.fetchall():
            results[row[0]] = {
                "count": row[1],
                "cost": row[2] or 0,
                "pnl": row[3] or 0
            }
        
        # Get pending positions (open value)
        cur.execute("SELECT SUM(cost) FROM my_trades WHERE outcome = 'pending'")
        pending_value = cur.fetchone()[0] or 0
        
        # Get total P&L
        cur.execute("SELECT SUM(pnl) FROM my_trades WHERE pnl IS NOT NULL")
        total_pnl = cur.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "by_outcome": results,
            "pending_positions_value": round(pending_value, 2),
            "realized_pnl": round(total_pnl, 2)
        }
    except Exception as e:
        return {"error": str(e)}

def get_full_portfolio():
    """Get complete portfolio status."""
    wallet = get_wallet_balance()
    positions = get_positions_summary()
    
    cash = wallet.get("total_usdc", 0)
    pending = positions.get("pending_positions_value", 0)
    realized_pnl = positions.get("realized_pnl", 0)
    
    # Calculate win rate
    by_outcome = positions.get("by_outcome", {})
    wins = by_outcome.get("won", {}).get("count", 0)
    losses = by_outcome.get("lost", {}).get("count", 0)
    total_resolved = wins + losses
    win_rate = (wins / total_resolved * 100) if total_resolved > 0 else 0
    
    return {
        "wallet": wallet,
        "cash_balance": cash,
        "positions_value": pending,
        "total_portfolio_value": round(cash + pending, 2),
        "realized_pnl": realized_pnl,
        "record": {
            "wins": wins,
            "losses": losses,
            "pending": by_outcome.get("pending", {}).get("count", 0),
            "win_rate": round(win_rate, 1)
        },
        "updated_at": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import json
    print(json.dumps(get_full_portfolio(), indent=2))
