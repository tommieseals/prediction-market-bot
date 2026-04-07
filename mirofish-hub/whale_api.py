#!/usr/bin/env python3
"""
Whale Tracker API - FastAPI backend for the dashboard.
Serves data from whale_hunter.db with full historical depth.
"""
import sqlite3
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from portfolio_tracker import get_full_portfolio, get_wallet_balance

# ============================================================
# LAYER 5: CLOB Liquidity Validation (Added 2026-03-25)
# ============================================================
# Cache: {token_id: {"liquid": bool, "spread": float, "checked_at": datetime}}
_liquidity_cache: Dict[str, dict] = {}
_LIQUIDITY_CACHE_TTL = timedelta(minutes=5)  # Recheck every 5 min

def check_token_liquidity(token_id: str) -> dict:
    """
    Check if a token has active liquidity on CLOB.
    Returns: {"liquid": bool, "spread": float, "reason": str}
    """
    if not token_id:
        return {"liquid": False, "spread": 1.0, "reason": "No token ID"}
    
    # Check cache first
    cached = _liquidity_cache.get(token_id)
    if cached and datetime.now() - cached["checked_at"] < _LIQUIDITY_CACHE_TTL:
        return cached
    
    try:
        # Query CLOB orderbook
        resp = requests.get(
            f"https://clob.polymarket.com/book?token_id={token_id}",
            timeout=5
        )
        
        if resp.status_code == 404:
            result = {"liquid": False, "spread": 1.0, "reason": "Orderbook not found"}
        elif resp.status_code != 200:
            result = {"liquid": False, "spread": 1.0, "reason": f"API error {resp.status_code}"}
        else:
            data = resp.json()
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            
            if not bids or not asks:
                result = {"liquid": False, "spread": 1.0, "reason": "No liquidity"}
            else:
                best_bid = float(bids[0]["price"]) if bids else 0
                best_ask = float(asks[0]["price"]) if asks else 1
                spread = best_ask - best_bid
                
                # Consider liquid if spread < 20 cents
                is_liquid = spread < 0.20 and best_bid > 0.01 and best_ask < 0.99
                result = {
                    "liquid": is_liquid,
                    "spread": spread,
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "reason": "OK" if is_liquid else f"Wide spread ({spread:.2f})"
                }
    except requests.Timeout:
        result = {"liquid": False, "spread": 1.0, "reason": "Timeout"}
    except Exception as e:
        result = {"liquid": False, "spread": 1.0, "reason": str(e)[:50]}
    
    # Cache result
    result["checked_at"] = datetime.now()
    _liquidity_cache[token_id] = result
    return result

def check_market_liquidity(condition_id: str, db_conn=None) -> dict:
    """
    Check liquidity for a market by condition_id.
    Looks up token_ids from whale_positions and checks both sides.
    """
    if not condition_id:
        return {"liquid": False, "spread": 1.0, "reason": "No condition ID"}
    
    # Get token IDs from database
    close_conn = False
    if db_conn is None:
        db_conn = get_db()
        close_conn = True
    
    try:
        cur = db_conn.cursor()
        cur.execute("""
            SELECT DISTINCT token_id, side FROM whale_positions 
            WHERE condition_id = ? AND token_id IS NOT NULL
            LIMIT 4
        """, (condition_id,))
        tokens = cur.fetchall()
    finally:
        if close_conn:
            db_conn.close()
    
    if not tokens:
        return {"liquid": False, "spread": 1.0, "reason": "No token IDs in DB"}
    
    # Check each token, return best result
    best_result = {"liquid": False, "spread": 1.0, "reason": "All illiquid"}
    for token_id, side in tokens:
        result = check_token_liquidity(token_id)
        if result.get("liquid"):
            return {**result, "token_id": token_id, "side": side}
        if result.get("spread", 1.0) < best_result.get("spread", 1.0):
            best_result = {**result, "token_id": token_id, "side": side}
    
    return best_result
# ============================================================

app = FastAPI(title="Whale Tracker API", version="2.0")

# CORS for dashboard access - MUST be before routes!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dashboard folder path
DASHBOARD_PATH = Path(__file__).parent / "dashboard"

# Serve HTML pages - Main routes
@app.get("/")
def serve_root():
    """Serve main dashboard index."""
    return FileResponse(DASHBOARD_PATH / "index.html")

@app.get("/consensus")
def serve_consensus():
    """Serve whale consensus page."""
    return FileResponse(Path(__file__).parent / "whale-consensus.html")

@app.get("/leaderboard")
def serve_leaderboard():
    """Serve whale leaderboard page."""
    return FileResponse(Path(__file__).parent / "whale-tracker-v2.html")

@app.get("/whales")
def serve_whales():
    """Serve whale tracker main page."""
    return FileResponse(Path(__file__).parent / "whale-tracker-original.html")

# Project pages
@app.get("/terminator")
def serve_terminator():
    """Serve TerminatorBot dashboard."""
    return FileResponse(DASHBOARD_PATH / "terminator.html")

@app.get("/vault")
def serve_vault():
    """Serve Project Vault dashboard."""
    return FileResponse(DASHBOARD_PATH / "project-vault.html")

@app.get("/fort-knox")
def serve_fort_knox():
    """Serve Fort Knox dashboard."""
    return FileResponse(DASHBOARD_PATH / "fort-knox.html")

@app.get("/legion")
def serve_legion():
    """Serve Legion HQ dashboard."""
    return FileResponse(DASHBOARD_PATH / "legion.html")

@app.get("/legion-tracker")
def serve_legion_tracker():
    """Serve Legion Tracker dashboard."""
    return FileResponse(DASHBOARD_PATH / "legion-tracker.html")

@app.get("/pharma")
def serve_pharma():
    """Serve Arbitrage Pharma dashboard."""
    return FileResponse(DASHBOARD_PATH / "arbitrage-pharma.html")

@app.get("/infrastructure")
def serve_infrastructure():
    """Serve Infrastructure dashboard."""
    return FileResponse(DASHBOARD_PATH / "infrastructure.html")

@app.get("/agents")
def serve_agents():
    """Serve Agents dashboard."""
    return FileResponse(DASHBOARD_PATH / "agents.html")

@app.get("/projects")
def serve_projects():
    """Serve Projects dashboard."""
    return FileResponse(DASHBOARD_PATH / "projects.html")

@app.get("/achievements")
def serve_achievements():
    """Serve Achievements dashboard."""
    return FileResponse(DASHBOARD_PATH / "achievements.html")

@app.get("/apis")
def serve_apis():
    """Serve APIs dashboard."""
    return FileResponse(DASHBOARD_PATH / "apis.html")

@app.get("/skills")
def serve_skills():
    """Serve Skills dashboard."""
    return FileResponse(DASHBOARD_PATH / "skills.html")

@app.get("/tools")
def serve_tools():
    """Serve Tools dashboard."""
    return FileResponse(DASHBOARD_PATH / "tools.html")

@app.get("/n8n-hub")
def serve_n8n_hub():
    """Serve n8n Hub dashboard."""
    return FileResponse(DASHBOARD_PATH / "n8n-hub.html")

@app.get("/taskbot")
def serve_taskbot():
    """Serve TaskBot dashboard."""
    return FileResponse(DASHBOARD_PATH / "taskbot.html")

@app.get("/tascosaur")
def serve_tascosaur():
    """Serve Tascosaur dashboard."""
    return FileResponse(DASHBOARD_PATH / "tascosaur.html")

@app.get("/teams-translator")
def serve_teams_translator():
    """Serve Teams Translator dashboard."""
    return FileResponse(DASHBOARD_PATH / "teams-translator.html")

@app.get("/sidekick-paas")
def serve_sidekick_paas():
    """Serve Sidekick PaaS dashboard."""
    return FileResponse(DASHBOARD_PATH / "sidekick-paas.html")

@app.get("/memory")
def serve_memory():
    """Serve Memory dashboard."""
    return FileResponse(DASHBOARD_PATH / "memory.html")

@app.get("/sessions")
def serve_sessions():
    """Serve Sessions dashboard."""
    return FileResponse(DASHBOARD_PATH / "sessions.html")

@app.get("/a2a-server")
def serve_a2a_server():
    """Serve A2A Server dashboard."""
    return FileResponse(DASHBOARD_PATH / "a2a-server.html")

@app.get("/docs")
def serve_docs():
    """Serve Docs dashboard."""
    return FileResponse(DASHBOARD_PATH / "docs.html")

@app.get("/shared-brain")
def serve_shared_brain():
    """Serve Shared Brain dashboard."""
    return FileResponse(DASHBOARD_PATH / "shared-brain.html")

@app.get("/swarm-monitor")
def serve_swarm():
    """Serve Swarm Monitor dashboard."""
    return FileResponse(DASHBOARD_PATH / "swarm-monitor.html")

@app.get("/fraud-detection")
def serve_fraud():
    """Serve Fraud Detection dashboard."""
    return FileResponse(DASHBOARD_PATH / "fraud-detection.html")

@app.get("/fiverr")
def serve_fiverr():
    """Serve Fiverr dashboard."""
    return FileResponse(DASHBOARD_PATH / "fiverr.html")

@app.get("/my-trades")
def serve_my_trades():
    """Serve My Trades dashboard."""
    return FileResponse(DASHBOARD_PATH / "my-trades.html")

@app.get("/kdp")
def serve_kdp():
    """Serve KDP/Borbott Army dashboard."""
    return FileResponse(DASHBOARD_PATH / "borbott-army.html")

# Serve static files from dashboard folder (CSS, JS, images, etc.)
app.mount("/dashboard", StaticFiles(directory=DASHBOARD_PATH, html=True), name="dashboard")

# Serve static data files (for whale_positions.json etc)
app.mount("/data", StaticFiles(directory=Path(__file__).parent / "data"), name="data")

# CORS middleware moved to top (before routes)

DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"

# Kill switch state
KILL_SWITCH = False

def get_db():
    """Get database connection with row factory, timeout, and WAL mode."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    """Initialize database tables that may not exist yet."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mirofish_results (
            condition_id TEXT PRIMARY KEY,
            swarm_prob REAL,
            swarm_sentiment TEXT,
            agent_count INTEGER,
            convergence REAL,
            validates_whales INTEGER,
            edge REAL,
            status TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


_init_db()

@app.get("/api/health")
def get_health():
    """Health check endpoint for monitoring."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tracked_whales")
        whale_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM whale_positions")
        position_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM consensus_picks WHERE outcome = 'pending' OR outcome IS NULL")
        pending_picks = cur.fetchone()[0]
        conn.close()
        
        return {
            "status": "healthy",
            "database": "connected",
            "whales": whale_count,
            "positions": position_count,
            "pending_picks": pending_picks,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.get("/api/stats")
def get_stats():
    """Overall whale tracker stats."""
    conn = get_db()
    cur = conn.cursor()
    
    # Whale stats
    cur.execute("""
        SELECT 
            COUNT(*) as total_whales,
            COUNT(CASE WHEN elite_score >= 20 THEN 1 END) as elite_whales,
            SUM(pnl) as total_pnl,
            AVG(elite_score) as avg_elite,
            MAX(pnl) as top_pnl
        FROM tracked_whales
    """)
    whale_stats = dict(cur.fetchone())
    
    # Position stats
    cur.execute("""
        SELECT 
            COUNT(*) as total_positions,
            COUNT(CASE WHEN outcome = 'won' THEN 1 END) as wins,
            COUNT(CASE WHEN outcome = 'lost' THEN 1 END) as losses,
            COUNT(CASE WHEN outcome = 'pending' OR outcome IS NULL THEN 1 END) as pending,
            SUM(CASE WHEN outcome = 'won' THEN actual_pnl ELSE 0 END) as total_win_pnl,
            SUM(CASE WHEN outcome = 'lost' THEN actual_pnl ELSE 0 END) as total_loss_pnl,
            SUM(size_usd) as total_volume
        FROM whale_positions
    """)
    pos_stats = dict(cur.fetchone())
    
    # Calculate win rate
    total_resolved = (pos_stats['wins'] or 0) + (pos_stats['losses'] or 0)
    win_rate = ((pos_stats['wins'] or 0) / total_resolved * 100) if total_resolved > 0 else 0
    
    conn.close()
    
    return {
        "whale_count": whale_stats['total_whales'],
        "elite_whales": whale_stats['elite_whales'],
        "total_pnl": round(whale_stats['total_pnl'] or 0, 2),
        "avg_elite_score": round(whale_stats['avg_elite'] or 0, 1),
        "top_whale_pnl": round(whale_stats['top_pnl'] or 0, 2),
        "total_positions": pos_stats['total_positions'],
        "wins": pos_stats['wins'] or 0,
        "losses": pos_stats['losses'] or 0,
        "pending": pos_stats['pending'] or 0,
        "win_rate": round(win_rate, 1),
        "total_volume": round(pos_stats['total_volume'] or 0, 2),
        "net_pnl": round((pos_stats['total_win_pnl'] or 0) + (pos_stats['total_loss_pnl'] or 0), 2),
        "updated": datetime.now().isoformat()
    }

@app.get("/api/whales")
def get_whales(
    sort_by: str = Query("elite_score", description="Sort field"),
    order: str = Query("desc", description="Sort order (asc/desc)"),
    limit: int = Query(50, description="Max results"),
    min_elite: float = Query(0, description="Minimum elite score")
):
    """Get all whales with stats."""
    conn = get_db()
    cur = conn.cursor()
    
    order_dir = "DESC" if order.lower() == "desc" else "ASC"
    
    cur.execute(f"""
        SELECT 
            tw.address,
            tw.display_name,
            tw.elite_score,
            tw.pnl,
            tw.volume,
            tw.brier_score,
            tw.win_rate_raw,
            tw.bayesian_win_rate,
            tw.num_trades,
            tw.avg_position_size,
            tw.calmar_ratio,
            tw.insider_score,
            tw.categories,
            tw.first_seen,
            tw.last_updated,
            tw.tracked_bets,
            tw.winning_bets,
            tw.tracked_accuracy,
            (SELECT COUNT(*) FROM whale_positions wp WHERE wp.address = tw.address AND (wp.outcome = 'pending' OR wp.outcome IS NULL)) as active_positions,
            (SELECT COUNT(*) FROM whale_positions wp WHERE wp.address = tw.address AND wp.outcome = 'won') as total_wins,
            (SELECT COUNT(*) FROM whale_positions wp WHERE wp.address = tw.address AND wp.outcome = 'lost') as total_losses
        FROM tracked_whales tw
        WHERE tw.elite_score >= ?
        ORDER BY tw.{sort_by} {order_dir}
        LIMIT ?
    """, (min_elite, limit))
    
    whale_rows = [dict(row) for row in cur.fetchall()]  # Convert to list of dicts
    addresses = [w['address'] for w in whale_rows]
    
    # Batch fetch recent bets for all whales (last 10 resolved per whale)
    recent_bets_map = {}
    if addresses:
        placeholders = ','.join(['?' for _ in addresses])
        cur.execute(f"""
            SELECT address, outcome, actual_pnl, resolved_at,
                   ROW_NUMBER() OVER (PARTITION BY address ORDER BY resolved_at DESC) as rn
            FROM whale_positions
            WHERE address IN ({placeholders}) AND outcome IN ('won', 'lost')
        """, addresses)
        
        for r in cur.fetchall():
            addr = r['address']
            rn = r['rn']
            if rn <= 10:  # Only keep last 10
                if addr not in recent_bets_map:
                    recent_bets_map[addr] = []
                recent_bets_map[addr].append({
                    "outcome": r['outcome'],
                    "pnl": r['actual_pnl'] or 0
                })
        
        # Reverse to get oldest first for sparkline
        for addr in recent_bets_map:
            recent_bets_map[addr] = list(reversed(recent_bets_map[addr]))
    
    whales = []
    for w in whale_rows:
        total_resolved = (w['total_wins'] or 0) + (w['total_losses'] or 0)
        whales.append({
            "address": w['address'],
            "name": w['display_name'] or w['address'][:10] + "...",
            "elite_score": round(w['elite_score'] or 0, 1),
            "pnl": round(w['pnl'] or 0, 2),
            "volume": round(w['volume'] or 0, 2),
            "brier_score": round(w['brier_score'] or 0, 3),
            "win_rate": round(w['win_rate_raw'] or 0, 1),
            "bayesian_win_rate": round(w['bayesian_win_rate'] or 0, 1),
            "num_trades": w['num_trades'] or 0,
            "avg_position_size": round(w['avg_position_size'] or 0, 2),
            "calmar_ratio": round(w['calmar_ratio'] or 0, 2),
            "insider_score": round(w['insider_score'] or 0, 1),
            "categories": w['categories'],
            "active_positions": w['active_positions'] or 0,
            "total_wins": w['total_wins'] or 0,
            "total_losses": w['total_losses'] or 0,
            "total_resolved": total_resolved,
            "tracked_win_rate": round((w['total_wins'] or 0) / total_resolved * 100, 1) if total_resolved > 0 else 0,
            "first_seen": w['first_seen'],
            "last_updated": w['last_updated'],
            "recent_bets": recent_bets_map.get(w['address'], [])
        })
    
    conn.close()
    return {"whales": whales, "count": len(whales)}

@app.get("/api/whales/{address}")
def get_whale_detail(address: str):
    """Get detailed info for a single whale."""
    conn = get_db()
    cur = conn.cursor()
    
    # Get whale info
    cur.execute("SELECT * FROM tracked_whales WHERE address = ?", (address,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Whale not found")
    
    whale = dict(row)
    
    # Get position summary by outcome
    cur.execute("""
        SELECT 
            outcome,
            COUNT(*) as count,
            SUM(actual_pnl) as total_pnl,
            AVG(size_usd) as avg_size
        FROM whale_positions
        WHERE address = ?
        GROUP BY outcome
    """, (address,))
    
    outcomes = {}
    for r in cur.fetchall():
        outcomes[r['outcome'] or 'pending'] = {
            "count": r['count'],
            "total_pnl": round(r['total_pnl'] or 0, 2),
            "avg_size": round(r['avg_size'] or 0, 2)
        }
    
    # Get recent positions
    cur.execute("""
        SELECT *
        FROM whale_positions
        WHERE address = ?
        ORDER BY detected_at DESC
        LIMIT 20
    """, (address,))
    
    recent = [dict(r) for r in cur.fetchall()]
    
    # Get category breakdown using improved Python categorizer
    cur.execute("""
        SELECT market_title, outcome
        FROM whale_positions
        WHERE address = ? AND outcome IN ('won', 'lost')
    """, (address,))

    categories = {}
    for r in cur.fetchall():
        cat = categorize_market(r['market_title'] or "")
        if cat not in categories:
            categories[cat] = {"count": 0, "won": 0, "lost": 0}
        categories[cat]["count"] += 1
        if r['outcome'] == 'won':
            categories[cat]["won"] += 1
        else:
            categories[cat]["lost"] += 1

    conn.close()

    display_name = whale['display_name'] or whale['address'][:10] + "..."
    return {
        "address": whale['address'],
        "name": display_name,
        "display_name": display_name,
        "elite_score": round(whale['elite_score'] or 0, 1),
        "pnl": round(whale['pnl'] or 0, 2),
        "volume": round(whale['volume'] or 0, 2),
        "brier_score": round(whale['brier_score'] or 0, 3),
        "win_rate": round(whale['win_rate_raw'] or 0, 1),
        "num_trades": whale['num_trades'] or 0,
        "calmar_ratio": round(whale['calmar_ratio'] or 0, 2),
        "insider_score": round(whale['insider_score'] or 0, 1),
        "tracked_bets": whale.get('tracked_bets') or 0,
        "tracked_accuracy": round(whale.get('tracked_accuracy') or 0, 3),
        "outcomes": outcomes,
        "categories": categories,
        "category_breakdown": categories,
        "recent_positions": recent,
        "first_seen": whale['first_seen'],
        "last_updated": whale['last_updated']
    }

@app.get("/api/whales/{address}/history")
def get_whale_history(
    address: str,
    limit: int = Query(100, description="Max results"),
    outcome: Optional[str] = Query(None, description="Filter by outcome")
):
    """Get full bet history for a whale."""
    conn = get_db()
    cur = conn.cursor()
    
    query = """
        SELECT *
        FROM whale_positions
        WHERE address = ?
    """
    params = [address]
    
    if outcome:
        query += " AND outcome = ?"
        params.append(outcome)
    
    query += " ORDER BY detected_at DESC LIMIT ?"
    params.append(limit)
    
    cur.execute(query, params)
    positions = [dict(r) for r in cur.fetchall()]
    
    conn.close()
    return {"positions": positions, "count": len(positions)}

@app.get("/api/whales/{address}/chart")
def get_whale_chart_data(address: str):
    """Get chart data for a whale (cumulative PnL, win/loss over time)."""
    conn = get_db()
    cur = conn.cursor()
    
    # Get all resolved positions ordered by time
    cur.execute("""
        SELECT 
            date(resolved_at) as date,
            outcome,
            actual_pnl,
            resolved_at
        FROM whale_positions
        WHERE address = ? AND outcome IN ('won', 'lost') AND resolved_at IS NOT NULL
        ORDER BY resolved_at ASC
    """, (address,))
    
    positions = cur.fetchall()
    
    # Build cumulative PnL series
    cumulative = []
    running_pnl = 0
    daily_data = {}
    
    for pos in positions:
        date = pos['date']
        pnl = pos['actual_pnl'] or 0
        running_pnl += pnl
        
        if date not in daily_data:
            daily_data[date] = {"wins": 0, "losses": 0, "pnl": 0}
        
        if pos['outcome'] == 'won':
            daily_data[date]['wins'] += 1
        else:
            daily_data[date]['losses'] += 1
        daily_data[date]['pnl'] += pnl
        
        cumulative.append({
            "timestamp": pos['resolved_at'],
            "pnl": round(running_pnl, 2),
            "outcome": pos['outcome']
        })
    
    # Daily aggregates with cumulative PnL for charts
    running_total = 0
    daily = []
    for d, v in sorted(daily_data.items()):
        running_total += v['pnl']
        daily.append({
            "date": d,
            "wins": v['wins'],
            "losses": v['losses'],
            "pnl": round(v['pnl'], 2),
            "cumulative_pnl": round(running_total, 2),
            "cum_pnl": round(running_total, 2)  # Alias for frontend compatibility
        })
    
    conn.close()
    
    return {
        "daily": daily,  # Frontend expects this
        "cumulative_pnl": cumulative,  # Keep for detailed view
        "daily_stats": daily,  # Backwards compat
        "total_data_points": len(cumulative)
    }

def parse_end_date(end_date_str):
    """Parse end_date string to datetime."""
    if not end_date_str:
        return None
    try:
        from datetime import timezone
        s = str(end_date_str).strip()
        if 'T' in s:
            dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        elif ' ' in s:
            dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
        else:
            # Date-only format: assume end of day (23:59 UTC)
            dt = datetime.strptime(s, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def calc_time_remaining(end_date_str):
    """Calculate time remaining and status."""
    from datetime import timezone
    end_dt = parse_end_date(end_date_str)
    if not end_dt:
        return {"time_remaining": "Unknown", "status": "unknown", "minutes_left": None, "expired": False}
    
    now = datetime.now(timezone.utc)
    delta = end_dt - now
    total_minutes = delta.total_seconds() / 60
    
    if total_minutes < 0:
        return {"time_remaining": "EXPIRED", "status": "expired", "minutes_left": total_minutes, "expired": True}
    elif total_minutes < 30:
        return {"time_remaining": f"{int(total_minutes)}m", "status": "danger", "minutes_left": total_minutes, "expired": False}
    elif total_minutes < 120:
        hours = int(total_minutes // 60)
        mins = int(total_minutes % 60)
        return {"time_remaining": f"{hours}h {mins}m", "status": "warning", "minutes_left": total_minutes, "expired": False}
    else:
        hours = int(total_minutes // 60)
        mins = int(total_minutes % 60)
        return {"time_remaining": f"{hours}h {mins}m", "status": "safe", "minutes_left": total_minutes, "expired": False}

@app.get("/api/positions/live")
def get_live_positions(
    limit: int = Query(50, description="Max results"),
    exclude_expired: bool = Query(False, description="Exclude expired markets"),
    min_time_left: int = Query(0, description="Minimum minutes remaining")
):
    """Get all active/pending positions with expiration info."""
    conn = get_db()
    cur = conn.cursor()
    
    # FIX 2026-03-24: Exclude positions with current_price >= 0.99 or <= 0.01 (effectively resolved)
    cur.execute("""
        SELECT 
            wp.*,
            tw.display_name as whale_name,
            tw.elite_score,
            tw.pnl as whale_pnl
        FROM whale_positions wp
        LEFT JOIN tracked_whales tw ON wp.address = tw.address
        WHERE (wp.outcome = 'pending' OR wp.outcome IS NULL)
          AND (wp.current_price IS NULL OR (wp.current_price > 0.01 AND wp.current_price < 0.99))
        ORDER BY wp.detected_at DESC
        LIMIT ?
    """, (limit * 2,))  # Fetch extra to filter
    
    positions = []
    for row in cur.fetchall():
        p = dict(row)
        
        # Calculate time remaining
        time_info = calc_time_remaining(p.get('end_date'))
        
        # Apply filters
        if exclude_expired and time_info['expired']:
            continue
        if min_time_left > 0 and time_info['minutes_left'] is not None:
            if time_info['minutes_left'] < min_time_left:
                continue
        
        positions.append({
            "id": p['id'],
            "whale": p['whale_name'] or p['address'][:10] + "...",
            "whale_address": p['address'],
            "elite_score": round(p['elite_score'] or 0, 1),
            "whale_pnl": round(p['whale_pnl'] or 0, 2),
            "market": p['market_title'],
            "condition_id": p['condition_id'],
            "side": p['side'],
            "size_usd": round(p['size_usd'] or 0, 2),
            "entry_price": round(p['entry_price'] or 0, 4),
            "current_price": round(p['current_price'] or 0, 4),
            "unrealized_pnl": round(p['unrealized_pnl'] or 0, 2),
            "detected_at": p['detected_at'],
            "end_date": p.get('end_date'),
            "time_remaining": time_info['time_remaining'],
            "time_status": time_info['status'],
            "minutes_left": time_info['minutes_left'],
            "expired": time_info['expired']
        })
        
        if len(positions) >= limit:
            break
    
    conn.close()
    return {"positions": positions, "count": len(positions)}

@app.get("/api/positions/resolved")
def get_resolved_positions(
    limit: int = Query(50, description="Max results"),
    outcome: Optional[str] = Query(None, description="Filter: won/lost")
):
    """Get resolved positions with actual P&L."""
    conn = get_db()
    cur = conn.cursor()
    
    query = """
        SELECT 
            wp.*,
            tw.display_name as whale_name,
            tw.elite_score
        FROM whale_positions wp
        LEFT JOIN tracked_whales tw ON wp.address = tw.address
        WHERE wp.outcome IN ('won', 'lost')
    """
    params = []
    
    if outcome:
        query += " AND wp.outcome = ?"
        params.append(outcome)
    
    query += " ORDER BY wp.resolved_at DESC LIMIT ?"
    params.append(limit)
    
    cur.execute(query, params)
    
    positions = []
    for row in cur.fetchall():
        p = dict(row)
        positions.append({
            "id": p['id'],
            "whale": p['whale_name'] or p['address'][:10] + "...",
            "whale_address": p['address'],
            "elite_score": round(p['elite_score'] or 0, 1),
            "market": p['market_title'],
            "side": p['side'],
            "size_usd": round(p['size_usd'] or 0, 2),
            "entry_price": round(p['entry_price'] or 0, 4),
            "final_price": round(p['final_price'] or 0, 4),
            "outcome": p['outcome'],
            "actual_pnl": round(p['actual_pnl'] or 0, 2),
            "detected_at": p['detected_at'],
            "resolved_at": p['resolved_at']
        })
    
    conn.close()
    return {"positions": positions, "count": len(positions)}

@app.get("/api/leaderboard")
def get_leaderboard(limit: int = Query(20, description="Top N whales")):
    """Get whale leaderboard with sparkline data."""
    conn = get_db()
    cur = conn.cursor()
    
    # Get top whales by elite score
    cur.execute("""
        SELECT 
            tw.address,
            tw.display_name,
            tw.elite_score,
            tw.pnl,
            tw.win_rate_raw,
            tw.num_trades,
            tw.brier_score
        FROM tracked_whales tw
        WHERE tw.elite_score >= 20
        ORDER BY tw.elite_score DESC
        LIMIT ?
    """, (limit,))
    
    leaderboard = []
    for rank, row in enumerate(cur.fetchall(), 1):
        w = dict(row)
        
        # Get last 10 bets for sparkline
        cur.execute("""
            SELECT outcome, actual_pnl
            FROM whale_positions
            WHERE address = ? AND outcome IN ('won', 'lost')
            ORDER BY resolved_at DESC
            LIMIT 10
        """, (w['address'],))
        
        recent = [{"outcome": r['outcome'], "pnl": r['actual_pnl'] or 0} for r in cur.fetchall()]
        recent.reverse()  # Oldest first for sparkline
        
        # Count active positions
        cur.execute("""
            SELECT COUNT(*) FROM whale_positions
            WHERE address = ? AND (outcome = 'pending' OR outcome IS NULL)
        """, (w['address'],))
        active = cur.fetchone()[0]
        
        leaderboard.append({
            "rank": rank,
            "address": w['address'],
            "name": w['display_name'] or w['address'][:10] + "...",
            "elite_score": round(w['elite_score'] or 0, 1),
            "pnl": round(w['pnl'] or 0, 2),
            "win_rate": round(w['win_rate_raw'] or 0, 1),
            "num_trades": w['num_trades'] or 0,
            "brier_score": round(w['brier_score'] or 0, 3),
            "active_positions": active,
            "recent_bets": recent
        })
    
    conn.close()
    return {"leaderboard": leaderboard, "count": len(leaderboard)}

# -- Consensus Picks API ----------------------------------------------------------

import sys
sys.path.insert(0, str(Path(__file__).parent))
from whale_scorer import (
    calculate_consensus_confidence,
    categorize_market,
    determine_signal_direction,
    compute_dynamic_base_rates,
)

# Refresh category base rates from actual tracked data on startup
compute_dynamic_base_rates(str(DB_PATH))


def _get_sim_cache(condition_id: str) -> Optional[dict]:
    """Check for cached MiroFish simulation result from mirofish_results DB table.

    The consensus_swarm_connector stores sim results in the mirofish_results
    table.  Previously this function looked for JSON files in
    data/whale_sim_cache/ which were never created -- now it queries the DB
    directly so the API and connector stay in sync.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT swarm_prob, swarm_sentiment, validates_whales, edge, "
            "       status, updated_at "
            "FROM mirofish_results WHERE condition_id = ?",
            (condition_id,),
        ).fetchone()
        conn.close()
        if row:
            # Check freshness (only use results < 6 hours old)
            try:
                updated = datetime.fromisoformat(row["updated_at"])
                if datetime.now() - updated > timedelta(hours=6):
                    return None
            except Exception:
                pass
            return {
                # swarm_prob is stored as 0-100 (e.g. 50.0 = 50%).
                # Normalize to 0-1 for consistency with the rest of the API.
                "consensus_probability": (row["swarm_prob"] or 0) / 100.0,
                "sentiment": row["swarm_sentiment"] or "neutral",
                "validates_whales": bool(row["validates_whales"]),
                "edge": row["edge"] or 0,
                "status": row["status"] or "unknown",
            }
    except Exception:
        pass
    return None


_closed_market_cache: dict = {}  # condition_id → (bool, timestamp)
_CACHE_TTL = 300  # 5 minutes — shorter TTL prevents hiding live markets (H4 fix)


def _filter_closed_markets(raw_markets: list, max_check: int = 200) -> list:
    """
    Remove markets that are already closed on Polymarket.

    IMPORTANT: Markets with a valid end_date already get filtered by the SQL
    query (datetime(end_date) > datetime('now', '-6 hours')), so most daily sports markets don't
    need a Gamma API check. We only check markets WITHOUT end_dates, or where
    end_date is far in the future (might have resolved early).

    Uses a sample token_id from each market to query Gamma API (condition_id
    queries are unreliable). Results cached in-memory with 30-min TTL.
    """
    import requests, time

    if not raw_markets:
        return raw_markets

    # Get a token_id for each condition_id so we can query Gamma reliably
    db = get_db()
    token_map = {}
    for m in raw_markets[:max_check]:
        cid = m.get("condition_id", "")
        if not cid:
            continue
        row = db.execute(
            "SELECT token_id FROM whale_positions WHERE condition_id = ? "
            "AND token_id IS NOT NULL AND token_id != '' LIMIT 1",
            (cid,),
        ).fetchone()
        if row:
            token_map[cid] = row[0]
    db.close()

    alive = []
    checked = 0
    for m in raw_markets[:max_check]:
        cid = m.get("condition_id", "")

        # Use in-memory cache with TTL
        if cid in _closed_market_cache:
            cached_closed, cached_time = _closed_market_cache[cid]
            import time as _time
            if _time.time() - cached_time < _CACHE_TTL:
                if not cached_closed:
                    alive.append(m)
                continue
            else:
                del _closed_market_cache[cid]  # Expired — re-check

        # Skip Gamma check for markets with a near-term end_date
        # (the SQL query already filters these with datetime(end_date) > datetime('now', '-6 hours'))
        end_date = m.get("market_end_date", "")
        if end_date:
            try:
                from datetime import datetime as _dt, timedelta as _td
                end = _dt.fromisoformat(end_date.replace("Z", ""))
                if end <= _dt.now() + _td(days=7):
                    alive.append(m)  # Near-term market — trust end_date filter
                    continue
            except (ValueError, TypeError):
                pass

        tid = token_map.get(cid)
        if not tid:
            alive.append(m)  # No token_id → can't check, keep it
            continue

        try:
            resp = requests.get(
                "https://gamma-api.polymarket.com/markets",
                params={"clob_token_ids": tid},
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
                if data:
                    market_data = data[0] if isinstance(data, list) else data
                    is_closed = bool(market_data.get("closed"))
                    import time as _time
                    _closed_market_cache[cid] = (is_closed, _time.time())

                    if is_closed:
                        # Backfill end_date
                        end_date = market_data.get("endDate", "")
                        if end_date:
                            try:
                                db2 = get_db()
                                db2.execute(
                                    "UPDATE whale_positions SET end_date = ? "
                                    "WHERE condition_id = ? AND (end_date IS NULL OR end_date = '')",
                                    (end_date, cid),
                                )
                                db2.commit()
                                db2.close()
                            except Exception:
                                pass
                        continue  # Skip closed market
                else:
                    import time as _time
                    _closed_market_cache[cid] = (False, _time.time())
        except Exception:
            pass  # On error, keep the market

        alive.append(m)
        checked += 1
        if checked % 5 == 0:
            time.sleep(0.3)  # Rate limit every 5 requests

    # Include any markets beyond max_check (don't silently drop them)
    if len(raw_markets) > max_check:
        alive.extend(raw_markets[max_check:])

    return alive


def _extract_entities(title: str) -> List[str]:
    """Extract key entities (team names, player names) from market title."""
    import re
    # Remove common noise words
    noise = {"will", "the", "win", "on", "vs", "spread", "o/u", "game", "match"}
    words = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*", title)
    entities = [w.strip() for w in words if w.strip().lower() not in noise and len(w.strip()) > 2]
    return entities[:5]  # Cap at 5 entities


@app.get("/api/consensus")
def get_consensus(
    min_whales: int = Query(3, ge=1),
    min_confidence: float = Query(0, ge=0, le=100),
    category: str = Query("all"),
    limit: int = Query(50, ge=1, le=200),
    check_liquidity: bool = Query(False, description="Check CLOB liquidity (slower)"),
):
    """
    Get consensus picks — markets where multiple whales agree.

    Returns empty picks when kill switch is active.

    Ranked by Bayesian confidence score factoring whale count, elite scores,
    agreement %, price efficiency, freshness, and category.
    """
    if KILL_SWITCH:
        return {
            "picks": [],
            "message": "System paused - kill switch active",
            "kill_switch": True,
            "generated_at": datetime.now().isoformat(),
        }

    conn = get_db()
    cur = conn.cursor()

    # Get all multi-whale pending markets that are still open
    # Filter: exclude markets with end_date in the past (already resolved/expired)
    # FIX 2026-03-24: Exclude markets where ANY position has resolved price (>= 0.99 or <= 0.01)
    # Use subquery to find resolved condition_ids first
    cur.execute("""
        SELECT
            wp.market_title,
            wp.condition_id,
            COUNT(DISTINCT wp.address) as whale_count,
            SUM(CASE WHEN wp.side = 'YES' THEN 1 ELSE 0 END) as yes_count,
            SUM(CASE WHEN wp.side = 'NO' THEN 1 ELSE 0 END) as no_count,
            AVG(tw.elite_score) as avg_elite,
            SUM(wp.size_usd) as total_size,
            AVG(wp.entry_price) as avg_entry,
            MIN(wp.detected_at) as first_detected,
            COUNT(DISTINCT wp.address) as unique_whales,
            MAX(wp.end_date) as market_end_date,
            AVG(wp.current_price) as avg_current_price
        FROM whale_positions wp
        JOIN tracked_whales tw ON wp.address = tw.address
        WHERE wp.outcome = 'pending'
          AND wp.condition_id NOT IN (
              SELECT DISTINCT condition_id FROM whale_positions 
              WHERE current_price IS NOT NULL 
              AND (current_price >= 0.99 OR current_price <= 0.01)
          )
          AND (
            (wp.end_date IS NOT NULL AND wp.end_date != ''
             AND datetime(wp.end_date) > datetime('now', '-6 hours'))
            OR
            ((wp.end_date IS NULL OR wp.end_date = '')
             AND datetime(wp.detected_at) > datetime('now', '-48 hours'))
          )
        GROUP BY wp.condition_id
        HAVING whale_count >= ?
        ORDER BY whale_count DESC
    """, (min_whales,))

    raw_markets = [dict(row) for row in cur.fetchall()]

    # Batch alive-check: verify top markets are still open on Polymarket
    # This catches legacy positions that have no end_date but are already closed
    raw_markets = _filter_closed_markets(raw_markets, max_check=limit)

    # Score each market with Bayesian confidence
    picks = []
    for m in raw_markets:
        title = m["market_title"] or ""
        cat = categorize_market(title)

        # Category filter
        if category != "all" and cat != category.lower():
            continue

        whale_count = m["whale_count"]
        yes_c = m["yes_count"]
        no_c = m["no_count"]
        agreement_pct = max(yes_c, no_c) / whale_count if whale_count else 0
        consensus_side = "YES" if yes_c > no_c else "NO"

        # Hours since first whale
        first_dt = m["first_detected"] or datetime.now().isoformat()
        try:
            hours_since = (datetime.now() - datetime.fromisoformat(first_dt)).total_seconds() / 3600
        except Exception:
            hours_since = 24

        # Check MiroFish cache
        sim_cache = _get_sim_cache(m["condition_id"])
        miro_status = "not_run"
        miro_prob = 0.0
        if sim_cache:
            miro_prob = sim_cache.get("consensus_probability", 0) or 0
            if miro_prob > 0:
                # Does MiroFish agree with whale consensus?
                whale_prob = agreement_pct  # Rough: whale agreement as probability proxy
                if abs(miro_prob / 100 - whale_prob) < 0.15:
                    miro_status = "confirmed"
                else:
                    miro_status = "disagrees"

        # Bayesian confidence
        conf = calculate_consensus_confidence(
            whale_count=whale_count,
            avg_elite=m["avg_elite"] or 50,
            agreement_pct=agreement_pct,
            avg_entry_price=m["avg_entry"] or 0.5,
            hours_since_first=hours_since,
            unique_whales=m["unique_whales"],
            category=cat,
            mirofish_prob=miro_prob,
            mirofish_status=miro_status,
        )

        if conf["confidence_pct"] < min_confidence:
            continue

        # Get individual whale details for this market
        cur.execute("""
            SELECT tw.display_name, tw.elite_score, tw.address,
                   wp.side, wp.entry_price, wp.size_usd,
                   COALESCE(tw.tracked_bets, 0) as tracked_bets,
                   COALESCE(tw.tracked_accuracy, 0) as tracked_acc
            FROM whale_positions wp
            JOIN tracked_whales tw ON wp.address = tw.address
            WHERE wp.condition_id = ? AND wp.outcome = 'pending'
            ORDER BY tw.elite_score DESC
        """, (m["condition_id"],))

        whales = []
        for w in cur.fetchall():
            sig_dir = determine_signal_direction(w["tracked_bets"], w["tracked_acc"])
            whales.append({
                "name": w["display_name"] or w["address"][:10],
                "elite": round(w["elite_score"] or 0, 1),
                "side": w["side"],
                "entry": round(w["entry_price"] or 0, 4),
                "size": round(w["size_usd"] or 0, 2),
                "tracked_bets": w["tracked_bets"],
                "tracked_acc": f"{w['tracked_acc']:.0%}" if w["tracked_bets"] >= 5 else "new",
                "signal_direction": sig_dir,
            })

        # LAYER 5: Check liquidity (optional - adds latency)
        if check_liquidity:
            liq = check_market_liquidity(m["condition_id"], conn)
        else:
            liq = {"liquid": None, "spread": None, "reason": "Not checked"}
        
        picks.append({
            "market_title": title,
            "condition_id": m["condition_id"],
            "whale_count": whale_count,
            "yes_count": yes_c,
            "no_count": no_c,
            "consensus_side": consensus_side,
            "agreement_pct": round(agreement_pct * 100, 1),
            "avg_elite_score": round(m["avg_elite"] or 0, 1),
            "total_size_usd": round(m["total_size"] or 0, 0),
            "avg_entry_price": round(m["avg_entry"] or 0, 4),
            "confidence_pct": conf["confidence_pct"],
            "confidence_tier": conf["tier"],
            "kelly_fraction": conf["kelly_fraction"],
            "category": cat,
            "mirofish_status": miro_status,
            "mirofish_prob": round(miro_prob, 1),
            "hours_since_first_whale": round(hours_since, 1),
            "end_date": m.get("market_end_date") or "",
            "entities": _extract_entities(title),
            "whales": whales,
            # Layer 5: Liquidity status
            "liquid": liq.get("liquid") if liq.get("liquid") is not None else None,
            "liquidity_spread": round(liq["spread"], 3) if liq.get("spread") is not None else None,
            "liquidity_reason": liq.get("reason", "Not checked"),
        })

        # H3 FIX: Calculate minutes to expiration
        pick = picks[-1]  # Reference to just-appended pick
        if pick.get('end_date'):
            try:
                end = datetime.fromisoformat(pick['end_date'].replace('Z', '+00:00'))
                now = datetime.now(end.tzinfo) if end.tzinfo else datetime.now()
                minutes_left = max(0, (end - now).total_seconds() / 60)
                pick['minutes_to_expiration'] = round(minutes_left)
                pick['is_expiring_soon'] = minutes_left < 240  # < 4 hours
            except Exception:
                pick['minutes_to_expiration'] = None
                pick['is_expiring_soon'] = False
        else:
            pick['minutes_to_expiration'] = None
            pick['is_expiring_soon'] = False

    # Sort by confidence score
    picks.sort(key=lambda p: p["confidence_pct"], reverse=True)
    picks = picks[:limit]

    # Cross-market grouping: find related markets by shared entities
    _add_related_markets(picks)

    conn.close()

    # Summary counts
    green = sum(1 for p in picks if p["confidence_tier"] == "GREEN")
    yellow = sum(1 for p in picks if p["confidence_tier"] == "YELLOW")
    red = sum(1 for p in picks if p["confidence_tier"] == "RED")
    liquid_count = sum(1 for p in picks if p.get("liquid", False))
    tradeable = [p for p in picks if p.get("liquid", False) and p["confidence_tier"] == "GREEN"]

    return {
        "picks": picks,
        "summary": {
            "total": len(picks),
            "green": green,
            "yellow": yellow,
            "red": red,
            "liquid": liquid_count,
            "tradeable": len(tradeable),  # GREEN + liquid
            "generated_at": datetime.now().isoformat(),
        },
    }


def _add_related_markets(picks: List[dict]):
    """Annotate each pick with related markets sharing the same entities."""
    entity_to_picks = {}
    for i, p in enumerate(picks):
        for ent in p.get("entities", []):
            entity_to_picks.setdefault(ent.lower(), []).append(i)

    for i, p in enumerate(picks):
        related = set()
        for ent in p.get("entities", []):
            for j in entity_to_picks.get(ent.lower(), []):
                if j != i:
                    related.add(picks[j]["market_title"][:50])
        p["related_markets"] = list(related)[:5]


@app.get("/api/portfolio/heat")
def get_portfolio_heat():
    """
    Portfolio concentration analysis — warns when over-exposed to one category.
    """
    conn = get_db()
    cur = conn.cursor()

    # Get all pending positions grouped by category
    cur.execute("""
        SELECT wp.market_title, wp.side, wp.size_usd
        FROM whale_positions wp
        WHERE wp.outcome = 'pending' AND wp.size_usd > 0
    """)

    category_totals = {}
    total_size = 0
    for row in cur.fetchall():
        cat = categorize_market(row["market_title"] or "")
        size = row["size_usd"] or 0
        category_totals[cat] = category_totals.get(cat, 0) + size
        total_size += size

    conn.close()

    max_category_pct = 40  # Warning threshold
    categories = {}
    for cat, size in sorted(category_totals.items(), key=lambda x: -x[1]):
        pct = (size / total_size * 100) if total_size > 0 else 0
        categories[cat] = {
            "size_usd": round(size, 0),
            "exposure_pct": round(pct, 1),
            "status": "WARNING" if pct > max_category_pct else "OK",
        }

    return {
        "total_size_usd": round(total_size, 0),
        "by_category": categories,
        "max_category_limit_pct": max_category_pct,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/liquidity/{condition_id}")
def check_liquidity_endpoint(condition_id: str):
    """
    LAYER 5: Check liquidity for a single market.
    Fast endpoint for on-demand liquidity checks.
    """
    result = check_market_liquidity(condition_id)
    return {
        "condition_id": condition_id,
        "liquid": result.get("liquid", False),
        "spread": result.get("spread"),
        "best_bid": result.get("best_bid"),
        "best_ask": result.get("best_ask"),
        "reason": result.get("reason", "Unknown"),
        "checked_at": datetime.now().isoformat(),
    }


@app.get("/api/liquidity/batch")
def check_liquidity_batch(condition_ids: str = Query(..., description="Comma-separated condition IDs")):
    """
    LAYER 5: Batch liquidity check for multiple markets.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    ids = [c.strip() for c in condition_ids.split(",") if c.strip()][:20]  # Max 20
    results = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(check_market_liquidity, cid): cid for cid in ids}
        for future in as_completed(futures, timeout=30):
            cid = futures[future]
            try:
                result = future.result()
                results[cid] = {
                    "liquid": result.get("liquid", False),
                    "spread": result.get("spread"),
                    "reason": result.get("reason"),
                }
            except Exception as e:
                results[cid] = {"liquid": False, "spread": None, "reason": str(e)}
    
    liquid_count = sum(1 for r in results.values() if r.get("liquid"))
    return {
        "results": results,
        "summary": {"total": len(results), "liquid": liquid_count},
        "checked_at": datetime.now().isoformat(),
    }


@app.get("/analytics")
def serve_analytics():
    """Serve whale analytics dashboard."""
    return FileResponse(Path(__file__).parent / "whale-analytics.html")


@app.get("/api/consensus/history")
def get_consensus_history():
    """Historical consensus pick performance — tracks our prediction record."""
    conn = get_db()
    cur = conn.cursor()

    # All picks
    cur.execute("""
        SELECT id, market_title, side, confidence, whale_count,
               avg_entry_price, end_date, outcome, resolved_at,
               won, profit_loss, notes, created_at
        FROM consensus_picks
        ORDER BY id DESC
    """)
    picks = [dict(row) for row in cur.fetchall()]

    # Summary stats
    total = len(picks)
    won = sum(1 for p in picks if p.get("outcome") == "won")
    lost = sum(1 for p in picks if p.get("outcome") == "lost")
    pending = sum(1 for p in picks if p.get("outcome") == "pending")
    total_pnl = sum(p.get("profit_loss") or 0 for p in picks)
    win_rate = won / (won + lost) if (won + lost) > 0 else 0

    conn.close()
    return {
        "picks": picks,
        "summary": {
            "total": total,
            "won": won,
            "lost": lost,
            "pending": pending,
            "win_rate": round(win_rate, 3),
            "total_pnl": round(total_pnl, 2),
        },
        "generated_at": datetime.now().isoformat(),
    }


@app.get("/api/category/performance")
def get_category_performance():
    """Win rate and P&L by market category."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT market_title, outcome, actual_pnl
        FROM whale_positions
        WHERE outcome IN ('won', 'lost')
    """)

    cats = {}
    for row in cur.fetchall():
        cat = categorize_market(row["market_title"] or "")
        if cat not in cats:
            cats[cat] = {"won": 0, "lost": 0, "pnl": 0.0}
        if row["outcome"] == "won":
            cats[cat]["won"] += 1
        else:
            cats[cat]["lost"] += 1
        cats[cat]["pnl"] += row["actual_pnl"] or 0

    result = {}
    for cat, data in sorted(cats.items(), key=lambda x: -(x[1]["won"] + x[1]["lost"])):
        total = data["won"] + data["lost"]
        result[cat] = {
            "total": total,
            "won": data["won"],
            "lost": data["lost"],
            "win_rate": round(data["won"] / total, 3) if total > 0 else 0,
            "pnl": round(data["pnl"], 2),
        }

    conn.close()
    return {"categories": result, "generated_at": datetime.now().isoformat()}


@app.get("/api/calibration")
def get_calibration():
    """Get MiroFish/consensus prediction calibration report."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from outcome_tracker import OutcomeTracker
        ot = OutcomeTracker()
        report = ot.get_accuracy_report()
        return {"status": "ok", "report": report, "generated_at": datetime.now().isoformat()}
    except Exception as e:
        return {"status": "error", "error": str(e), "report": {
            "total_predictions": 0, "resolved": 0, "unresolved": 0,
            "brier_score": None, "directional_accuracy": None,
            "note": "No predictions logged yet — run consensus scan to populate"
        }}


@app.get("/api/hot-whales")
def get_hot_whales(days: int = Query(7, description="Lookback period in days")):
    """Get whales with best recent performance (winning streaks, hot streaks)."""
    conn = get_db()
    cur = conn.cursor()
    
    # Get recent performance for each whale (parameterized to prevent SQL injection)
    days_param = f"-{int(days)} days"
    cur.execute("""
        WITH recent_performance AS (
            SELECT
                address,
                COUNT(*) as recent_bets,
                SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) as recent_wins,
                SUM(CASE WHEN outcome = 'lost' THEN 1 ELSE 0 END) as recent_losses,
                SUM(actual_pnl) as recent_pnl,
                MAX(resolved_at) as last_bet
            FROM whale_positions
            WHERE outcome IN ('won', 'lost')
              AND resolved_at >= datetime('now', ?)
            GROUP BY address
            HAVING recent_bets >= 3
        )
        SELECT
            rp.*,
            tw.display_name,
            tw.elite_score,
            tw.pnl as total_pnl,
            ROUND(CAST(rp.recent_wins AS FLOAT) / rp.recent_bets * 100, 1) as recent_win_rate
        FROM recent_performance rp
        JOIN tracked_whales tw ON rp.address = tw.address
        WHERE tw.elite_score >= 50
        ORDER BY recent_win_rate DESC, recent_pnl DESC
        LIMIT 20
    """, (days_param,))

    hot_whales = []
    rows = cur.fetchall()  # Consume all rows before reusing cursor
    for row in rows:
        # Calculate streak (use conn.execute to avoid cursor reuse conflict)
        streak_rows = conn.execute("""
            SELECT outcome FROM whale_positions
            WHERE address = ? AND outcome IN ('won', 'lost')
            ORDER BY resolved_at DESC
            LIMIT 10
        """, (row['address'],)).fetchall()
        recent = [r['outcome'] for r in streak_rows]
        
        # Count winning streak
        streak = 0
        for o in recent:
            if o == 'won':
                streak += 1
            else:
                break
        
        hot_whales.append({
            "address": row['address'],
            "name": row['display_name'] or row['address'][:10] + "...",
            "elite_score": round(row['elite_score'] or 0, 1),
            "recent_bets": row['recent_bets'],
            "recent_wins": row['recent_wins'],
            "recent_losses": row['recent_losses'],
            "recent_win_rate": row['recent_win_rate'],
            "recent_pnl": round(row['recent_pnl'] or 0, 2),
            "total_pnl": round(row['total_pnl'] or 0, 2),
            "win_streak": streak,
            "last_bet": row['last_bet'],
            "status": "[HOT]" if streak >= 5 else "[FAST]" if streak >= 3 else "[UP]" if row['recent_win_rate'] >= 70 else ""
        })
    
    conn.close()
    return {
        "hot_whales": hot_whales,
        "period_days": days,
        "generated_at": datetime.now().isoformat()
    }


@app.get("/api/money-flow")
def get_money_flow():
    """Real-time smart money flow - where is whale money going TODAY."""
    conn = get_db()
    cur = conn.cursor()
    
    # Recent positions (last 24-48 hours)
    cur.execute("""
        SELECT 
            wp.market_title,
            wp.side,
            wp.condition_id,
            COUNT(DISTINCT wp.address) as whale_count,
            SUM(wp.size_usd) as total_size,
            AVG(tw.elite_score) as avg_elite_score,
            GROUP_CONCAT(DISTINCT tw.display_name) as whale_names
        FROM whale_positions wp
        JOIN tracked_whales tw ON wp.address = tw.address
        WHERE wp.detected_at >= datetime('now', '-48 hours')
          AND wp.outcome = 'pending'
          AND tw.elite_score >= 50
        GROUP BY wp.condition_id, wp.side
        HAVING whale_count >= 2
        ORDER BY total_size DESC
        LIMIT 20
    """)
    
    flows = []
    for row in cur.fetchall():
        cat = categorize_market(row['market_title'] or "")
        flows.append({
            "market": row['market_title'],
            "side": row['side'],
            "whale_count": row['whale_count'],
            "total_size": round(row['total_size'] or 0, 2),
            "avg_elite": round(row['avg_elite_score'] or 0, 1),
            "category": cat,
            "whales": (row['whale_names'] or "").split(",")[:5]  # Top 5 names
        })
    
    conn.close()
    return {
        "flows": flows,
        "generated_at": datetime.now().isoformat()
    }


@app.get("/api/fade-signals")
def get_fade_signals():
    """FADE SIGNALS - Bet AGAINST these losers. Sub-40% win rate whales."""
    conn = get_db()
    cur = conn.cursor()
    
    # Find worst whales with enough trade history
    cur.execute("""
        SELECT 
            address,
            display_name,
            elite_score,
            pnl,
            win_rate_raw,
            num_trades,
            brier_score
        FROM tracked_whales
        WHERE num_trades >= 50
          AND win_rate_raw < 0.4
        ORDER BY win_rate_raw ASC
        LIMIT 20
    """)
    
    fade_whales = []
    for row in cur.fetchall():
        fade_whales.append({
            "address": row['address'],
            "name": row['display_name'] or row['address'][:12] + "...",
            "win_rate": round((row['win_rate_raw'] or 0) * 100, 1),
            "num_trades": row['num_trades'],
            "pnl": round(row['pnl'] or 0, 2),
            "brier_score": round(row['brier_score'] or 0, 3),
            "fade_confidence": round(100 - (row['win_rate_raw'] or 0) * 100, 1)  # Inverse of their win rate
        })
    
    # Now find their ACTIVE positions to fade
    fade_positions = []
    for whale in fade_whales[:5]:  # Top 5 worst
        cur.execute("""
            SELECT 
                market_title,
                side,
                size_usd,
                entry_price,
                condition_id,
                detected_at
            FROM whale_positions
            WHERE address = ?
              AND outcome = 'pending'
            ORDER BY detected_at DESC
            LIMIT 5
        """, (whale['address'],))
        
        for pos in cur.fetchall():
            # Fade = opposite side
            fade_side = "NO" if pos['side'] == "YES" else "YES"
            fade_positions.append({
                "market": pos['market_title'],
                "whale_side": pos['side'],
                "fade_side": fade_side,
                "whale_name": whale['name'],
                "whale_win_rate": whale['win_rate'],
                "size_usd": round(pos['size_usd'] or 0, 2),
                "entry_price": round(pos['entry_price'] or 0, 3),
                "fade_confidence": whale['fade_confidence'],
                "condition_id": pos['condition_id']
            })
    
    conn.close()
    return {
        "fade_whales": fade_whales,
        "fade_positions": sorted(fade_positions, key=lambda x: -x['fade_confidence'])[:15],
        "strategy": "Bet OPPOSITE of these whales. Their sub-40% win rate = your 60%+ edge.",
        "generated_at": datetime.now().isoformat()
    }


@app.get("/api/economic-calendar")
def get_economic_calendar():
    """Upcoming economic events with Polymarket whale activity."""
    conn = get_db()
    cur = conn.cursor()
    
    # Check if table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='economic_events'")
    if not cur.fetchone():
        conn.close()
        return {"events": [], "message": "Run: python economic_calendar.py --load"}
    
    today = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    cur.execute("""
        SELECT * FROM economic_events
        WHERE date BETWEEN ? AND ?
        ORDER BY date ASC
    """, (today, future))
    
    events = []
    for row in cur.fetchall():
        event = dict(row)
        days_away = (datetime.strptime(event['date'], "%Y-%m-%d") - datetime.now()).days
        event['days_away'] = days_away
        events.append(event)
    
    conn.close()
    return {
        "events": events,
        "generated_at": datetime.now().isoformat()
    }


@app.get("/api/commodities")
def get_commodities():
    """Commodity positions (oil, gold, etc) from whales."""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            wp.market_title,
            wp.side,
            COUNT(DISTINCT wp.address) as whale_count,
            SUM(wp.size_usd) as total_size,
            AVG(wp.entry_price) as avg_entry,
            AVG(tw.elite_score) as avg_elite
        FROM whale_positions wp
        JOIN tracked_whales tw ON wp.address = tw.address
        WHERE (wp.market_title LIKE '%Oil%' OR wp.market_title LIKE '%Crude%' 
               OR wp.market_title LIKE '%Gold%' OR wp.market_title LIKE '%Gas%')
          AND wp.outcome = 'pending'
          AND tw.elite_score >= 50
        GROUP BY wp.condition_id, wp.side
        ORDER BY total_size DESC
        LIMIT 20
    """)
    
    positions = []
    for row in cur.fetchall():
        positions.append({
            "market": row['market_title'],
            "side": row['side'],
            "whale_count": row['whale_count'],
            "total_size": round(row['total_size'] or 0, 2),
            "avg_entry": round(row['avg_entry'] or 0, 3),
            "avg_elite": round(row['avg_elite'] or 0, 1)
        })
    
    conn.close()
    return {
        "positions": positions,
        "generated_at": datetime.now().isoformat()
    }


@app.get("/api/kill")
def activate_kill_switch():
    """Activate the kill switch - pauses consensus picks."""
    global KILL_SWITCH
    KILL_SWITCH = True
    print(f"[{datetime.now().isoformat()}] [WARN] Kill switch ACTIVATED")
    return {"kill_switch": True, "message": "Kill switch activated - consensus picks paused"}


@app.get("/api/resume")
def deactivate_kill_switch():
    """Deactivate the kill switch - resumes consensus picks."""
    global KILL_SWITCH
    KILL_SWITCH = False
    print(f"[{datetime.now().isoformat()}] [OK] Kill switch DEACTIVATED")
    return {"kill_switch": False, "message": "Kill switch deactivated - consensus picks resumed"}


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "kill_switch": KILL_SWITCH,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health-dashboard")
def serve_health_dashboard():
    """Serve the health dashboard page."""
    return FileResponse(Path(__file__).parent / "health-dashboard.html")


@app.get("/api/health/detailed")
def detailed_health():
    """Detailed health check with database stats, freshness, and position breakdown."""
    result = {
        "api": "healthy",
        "database": {"accessible": False, "size_mb": 0},
        "freshness": {"latest_position": None, "minutes_ago": None},
        "stale": {"pending_past_enddate": 0},
        "positions": {"total": 0, "pending": 0, "won": 0, "lost": 0, "expired": 0},
        "whales": {"total": 0, "elite": 0},
        "consensus": {"total_picks": 0, "pending": 0, "resolved": 0},
        "kill_switch": KILL_SWITCH,
    }

    try:
        # Database accessibility and size
        if DB_PATH.exists():
            result["database"]["size_mb"] = round(DB_PATH.stat().st_size / (1024 * 1024), 1)

        conn = get_db()
        cur = conn.cursor()
        result["database"]["accessible"] = True

        # Position breakdown
        cur.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN outcome = 'pending' OR outcome IS NULL THEN 1 END) as pending,
                COUNT(CASE WHEN outcome = 'won' THEN 1 END) as won,
                COUNT(CASE WHEN outcome = 'lost' THEN 1 END) as lost,
                COUNT(CASE WHEN outcome = 'expired' THEN 1 END) as expired
            FROM whale_positions
        """)
        row = cur.fetchone()
        result["positions"] = {
            "total": row["total"] or 0,
            "pending": row["pending"] or 0,
            "won": row["won"] or 0,
            "lost": row["lost"] or 0,
            "expired": row["expired"] or 0,
        }

        # Whale counts
        cur.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN elite_score >= 20 THEN 1 END) as elite
            FROM tracked_whales
        """)
        wrow = cur.fetchone()
        result["whales"] = {
            "total": wrow["total"] or 0,
            "elite": wrow["elite"] or 0,
        }

        # Data freshness
        cur.execute("SELECT MAX(detected_at) FROM whale_positions")
        frow = cur.fetchone()
        if frow and frow[0]:
            latest_str = frow[0]
            result["freshness"]["latest_position"] = latest_str
            try:
                latest_dt = datetime.fromisoformat(latest_str.replace("Z", "+00:00")).replace(tzinfo=None)
                minutes_ago = (datetime.now() - latest_dt).total_seconds() / 60.0
                result["freshness"]["minutes_ago"] = round(minutes_ago, 1)
            except Exception:
                pass

        # Stale pending count
        cur.execute("""
            SELECT COUNT(*) FROM whale_positions
            WHERE end_date < datetime('now')
            AND (outcome = 'pending' OR outcome IS NULL)
        """)
        result["stale"]["pending_past_enddate"] = cur.fetchone()[0] or 0

        # Consensus picks (if table exists)
        try:
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN status = 'pending' OR status IS NULL THEN 1 END) as pending,
                    COUNT(CASE WHEN status IN ('won', 'lost', 'resolved') THEN 1 END) as resolved
                FROM consensus_picks
            """)
            crow = cur.fetchone()
            result["consensus"] = {
                "total_picks": crow["total"] or 0,
                "pending": crow["pending"] or 0,
                "resolved": crow["resolved"] or 0,
            }
        except Exception:
            # consensus_picks table may not exist
            pass

        # MiroFish validation stats
        try:
            cur.execute("SELECT COUNT(*) FROM mirofish_results")
            validated = cur.fetchone()[0] or 0
            cur.execute("SELECT MAX(updated_at) FROM mirofish_results")
            last_val_row = cur.fetchone()
            last_val = last_val_row[0] if last_val_row else None
            total_picks = result["consensus"]["total_picks"]
            result["mirofish"] = {
                "total_validated": validated,
                "pending_validation": max(0, total_picks - validated),
                "last_validation": last_val,
            }
        except Exception:
            result["mirofish"] = {"total_validated": 0, "pending_validation": 0, "last_validation": None}

        # Check MiroFish + Ollama health
        import requests as _req
        try:
            _r = _req.get("http://localhost:5001/health", timeout=3)
            result["mirofish"]["backend_healthy"] = _r.status_code == 200
        except Exception:
            result["mirofish"]["backend_healthy"] = False
        try:
            _r = _req.get("http://localhost:11434/api/tags", timeout=3)
            result["mirofish"]["ollama_healthy"] = _r.status_code == 200
        except Exception:
            result["mirofish"]["ollama_healthy"] = False

        conn.close()

    except Exception as e:
        result["api"] = f"error: {e}"

    return result


# ============================================================
# MOCK ENDPOINTS FOR LEGACY DASHBOARDS (Terminator, Vault, Fort Knox)
# These provide placeholder data so dashboards load without errors
# ============================================================

@app.get("/api/portfolio")
def real_portfolio():
    """Real portfolio tracking - wallet balance + positions."""
    try:
        portfolio = get_full_portfolio()
        return portfolio
    except Exception as e:
        return {
            "error": str(e),
            "total_portfolio_value": 0,
            "cash_balance": 0,
            "positions_value": 0,
            "updated_at": datetime.now().isoformat()
        }

@app.get("/api/strategies")
def mock_strategies():
    """Mock strategies for Terminator dashboard."""
    return [
        {"name": "Whale Follow", "status": "active", "pnl": 25.00, "trades": 1},
        {"name": "Consensus", "status": "active", "pnl": 0, "trades": 0},
        {"name": "MiroFish Swarm", "status": "standby", "pnl": 0, "trades": 0}
    ]

@app.get("/api/positions")
def mock_positions():
    """Mock positions for Terminator dashboard."""
    return []

@app.get("/api/risk")
def mock_risk():
    """Mock risk metrics for Terminator dashboard."""
    return {
        "max_drawdown": 0,
        "sharpe_ratio": 0,
        "daily_var": 0,
        "position_concentration": 0
    }

@app.get("/api/vault/portfolio")
def mock_vault_portfolio():
    """Mock portfolio for Vault dashboard."""
    return {
        "total_assets": 90.11,
        "liquid_usdc": 90.11,
        "locked_positions": 0,
        "pending_redemptions": 0
    }

@app.get("/api/backups/status")
def mock_backups():
    """Mock backup status for Fort Knox dashboard."""
    return {
        "last_backup": datetime.now().isoformat(),
        "backup_size_mb": 12.5,
        "status": "healthy",
        "locations": ["local", "cloud"]
    }


# ══════════════════════════════════════════════════════════════
# MY TRADES — Personal trade tracking
# ══════════════════════════════════════════════════════════════

@app.get("/api/my-trades")
def get_my_trades():
    """Get all personal trades with summary stats."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM my_trades ORDER BY created_at DESC")
    trades = [dict(row) for row in cur.fetchall()]

    won = sum(1 for t in trades if t["outcome"] == "won")
    lost = sum(1 for t in trades if t["outcome"] == "lost")
    pending = sum(1 for t in trades if t["outcome"] == "pending")
    total_pnl = sum(t.get("pnl") or 0 for t in trades if t["outcome"] in ("won", "lost"))
    unredeemed = sum(1 for t in trades if t["outcome"] == "won" and not t.get("redeemed"))

    conn.close()
    return {
        "trades": trades,
        "summary": {
            "total": len(trades),
            "won": won,
            "lost": lost,
            "pending": pending,
            "win_rate": round(won / max(won + lost, 1) * 100, 1),
            "total_pnl": round(total_pnl, 2),
            "unredeemed": unredeemed,
        },
        "generated_at": datetime.now().isoformat(),
    }


@app.post("/api/my-trades")
def add_my_trade(trade: dict):
    """Add a personal trade to track."""
    conn = get_db()
    cur = conn.cursor()

    required = ["market_title", "side", "entry_price"]
    for field in required:
        if field not in trade:
            conn.close()
            return {"error": f"Missing required field: {field}"}, 400

    now = datetime.now().isoformat()
    shares = trade.get("shares", 0)
    entry = float(trade["entry_price"])
    cost = shares * entry if shares else trade.get("cost", 0)

    cur.execute("""
        INSERT INTO my_trades
        (market_title, condition_id, token_id, side, entry_price, shares, cost,
         outcome, pnl, redeemed, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', NULL, 0, ?, ?)
    """, (
        trade["market_title"],
        trade.get("condition_id", ""),
        trade.get("token_id", ""),
        trade["side"].upper(),
        entry,
        shares,
        cost,
        trade.get("notes", ""),
        now,
    ))
    conn.commit()
    trade_id = cur.lastrowid
    conn.close()
    return {"id": trade_id, "status": "tracked", "message": f"Trade logged: {trade['market_title']}"}


@app.put("/api/my-trades/{trade_id}")
def update_my_trade(trade_id: int, update: dict):
    """Update a personal trade (resolve, redeem, add notes)."""
    conn = get_db()
    cur = conn.cursor()

    sets = []
    params = []
    for field in ["outcome", "pnl", "redeemed", "notes", "resolved_at"]:
        if field in update:
            sets.append(f"{field} = ?")
            params.append(update[field])

    if not sets:
        conn.close()
        return {"error": "No fields to update"}

    params.append(trade_id)
    cur.execute(f"UPDATE my_trades SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return {"status": "updated", "trade_id": trade_id}


# Prometheus metrics proxy — forwards to windows_exporter on localhost:9100
# This exposes metrics on the already-firewall-open port 8081
from fastapi.responses import PlainTextResponse

@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics():
    """Proxy windows_exporter metrics so Prometheus can scrape via port 8081."""
    try:
        r = requests.get("http://localhost:9100/metrics", timeout=5)
        return PlainTextResponse(content=r.text, status_code=r.status_code,
                                  media_type=r.headers.get("Content-Type", "text/plain"))
    except Exception as e:
        return PlainTextResponse(content=f"# ERROR: windows_exporter unavailable: {e}\n",
                                  status_code=503)


# Mount static files for dashboard - MUST be last (catch-all)
# This allows direct access to .html files like /n8n-hub.html
app.mount("/", StaticFiles(directory=DASHBOARD_PATH, html=True), name="static")

if __name__ == "__main__":
    print("Starting Whale Tracker API on port 8081...")
    uvicorn.run(app, host="0.0.0.0", port=8081)
