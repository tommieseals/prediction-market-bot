"""
Project Vault → MiroFish Connector

Reads portfolio data, positions, and strategy signals from Project Vault,
runs MiroFish swarm simulations to gauge market sentiment on held positions
and identify crowd psychology patterns for trading edge.

Usage:
    python vault_connector.py                        # Health check
    python vault_connector.py --test                 # Test with sample data
    python vault_connector.py --scan                 # Simulate top positions
    python vault_connector.py --symbol NVDA          # Simulate specific symbol
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Paths
VAULT_DIR = Path(r"C:\Users\USER\clawd\project-vault")
DASHBOARD_FILE = VAULT_DIR / "data" / "dashboard_backup.json"
SIGNALS_DIR = VAULT_DIR / "data" / "signals"
PREDICTIONS_LOG = Path(__file__).parent / "vault_predictions.jsonl"

sys.path.insert(0, str(Path(__file__).parent))
from mirofish_client import MiroFishClient
from simulation_configs import VAULT_CONFIG


def load_portfolio() -> dict:
    """Load portfolio snapshot from Project Vault."""
    if DASHBOARD_FILE.exists():
        with open(DASHBOARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_positions() -> list[dict]:
    """Get current positions from portfolio snapshot."""
    portfolio = load_portfolio()
    return portfolio.get("positions", [])


def get_balance() -> dict:
    """Get account balance summary (normalize camelCase to snake_case)."""
    portfolio = load_portfolio()
    raw = portfolio.get("balance", {})
    return {
        "total_equity": raw.get("equity", 0),
        "cash": raw.get("cash", 0),
        "buying_power": raw.get("buyingPower", 0),
        "day_pnl": raw.get("dayPnL", 0),
        "day_pnl_pct": 0,  # Not in backup
    }


def get_top_positions(limit: int = 5, sort_by: str = "value") -> list[dict]:
    """Get top positions by market value or unrealized P&L."""
    positions = get_positions()
    for p in positions:
        qty = p.get("quantity", 0)
        price = p.get("currentPrice") or p.get("current_price") or p.get("last_price", 0)
        cost = p.get("costBasis") or p.get("cost_basis", 0)
        p["current_price"] = price
        p["cost_basis"] = cost
        p["market_value"] = p.get("marketValue") or qty * price
        p["unrealized_pnl"] = p.get("unrealizedPnL") or (p["market_value"] - cost)

    if sort_by == "pnl":
        positions.sort(key=lambda x: abs(x.get("unrealized_pnl", 0)), reverse=True)
    else:
        positions.sort(key=lambda x: x.get("market_value", 0), reverse=True)

    return positions[:limit]


def format_positions_text(positions: list[dict]) -> str:
    """Format positions for seed text."""
    lines = []
    for p in positions:
        symbol = p.get("symbol", "???")
        qty = p.get("quantity", 0)
        cost = p.get("cost_basis", 0)
        value = p.get("market_value", 0)
        pnl = p.get("unrealized_pnl", 0)
        pnl_pct = (pnl / cost * 100) if cost else 0
        lines.append(
            f"  {symbol:6s}  {int(qty):6d} shares  "
            f"Cost: ${cost:>10,.2f}  Value: ${value:>10,.2f}  "
            f"P&L: ${pnl:>+10,.2f} ({pnl_pct:+.1f}%)"
        )
    return "\n".join(lines) if lines else "  No positions"


def build_seed_text(focus_position: dict, all_positions: list[dict]) -> str:
    """Build seed text for MiroFish from Vault data."""
    balance = get_balance()
    positions_text = format_positions_text(all_positions)

    symbol = focus_position.get("symbol", "SPY")
    qty = focus_position.get("quantity", 0)
    price = focus_position.get("current_price") or focus_position.get("last_price", 0)
    cost = focus_position.get("cost_basis", 0)
    pnl = focus_position.get("unrealized_pnl", 0)

    return VAULT_CONFIG.seed_text_template.format(
        total_equity=balance.get("total_equity", 0),
        cash=balance.get("cash", 0),
        day_pnl=balance.get("day_pnl", 0),
        day_pnl_pct=balance.get("day_pnl_pct", 0),
        buying_power=balance.get("buying_power", 0),
        positions_text=positions_text,
        kill_switch_status="INACTIVE (Normal Operations)",
        regime_text="Analysis pending — check ADX/BB indicators for current regime",
        focus_symbol=symbol,
        focus_price=price,
        focus_shares=qty,
        focus_cost=cost,
        focus_pnl=pnl,
    )


def simulate_position(
    client: MiroFishClient,
    position: dict,
    all_positions: list[dict],
    max_rounds: int = 24,
    skip_graph: bool = False,
) -> dict:
    """Run a MiroFish dual-platform simulation for a position."""
    symbol = position.get("symbol", "???")
    seed_text = build_seed_text(position, all_positions)

    sim_req = (
        f"Simulate social media discourse about ${symbol} stock. "
        f"Generate retail traders, institutional analysts, technical chartists, "
        f"value investors, momentum traders, and financial journalists. "
        f"Have them discuss: current price action, fundamental valuation, "
        f"sector trends, macro risks, and near-term catalysts. "
        f"Model how sentiment cascades and identify crowd positioning extremes."
    )

    pnl = position.get("unrealized_pnl", 0)
    print(f"\nSimulating: ${symbol}")
    print(f"  Value: ${position.get('market_value', 0):,.2f}")
    print(f"  P&L: ${pnl:+,.2f}")

    result = client.run_dual_platform(
        simulation_requirement=sim_req,
        seed_text=seed_text,
        project_name=f"Vault: ${symbol} Sentiment",
        max_rounds=max_rounds,
        skip_graph=skip_graph,
    )

    prediction = {
        "connector": "vault",
        "symbol": symbol,
        "quantity": position.get("quantity"),
        "cost_basis": position.get("cost_basis"),
        "market_value": position.get("market_value"),
        "unrealized_pnl": pnl,
        "simulation_id": result.get("simulation_id"),
        "project_id": result.get("project_id"),
        "report_id": result.get("report_id"),
        "steps": result.get("steps"),
        "timestamp": datetime.now().isoformat(),
    }
    return prediction


def log_prediction(prediction: dict) -> None:
    with open(PREDICTIONS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(prediction, ensure_ascii=False) + "\n")
    print(f"  Logged to {PREDICTIONS_LOG}")


def cmd_health(client: MiroFishClient) -> None:
    """Check connectivity."""
    print("Checking MiroFish...")
    if client.health_check():
        print("  MiroFish: ONLINE")
    else:
        print("  MiroFish: OFFLINE")

    print(f"\nChecking Project Vault data...")
    portfolio = load_portfolio()
    if portfolio:
        balance = get_balance()
        print(f"  Portfolio Equity: ${balance.get('total_equity', 0):,.2f}")
        print(f"  Cash: ${balance.get('cash', 0):,.2f}")
        print(f"  Day P&L: ${balance.get('day_pnl', 0):+,.2f}")
    else:
        print("  Portfolio data: NOT FOUND")

    positions = get_positions()
    print(f"  Positions: {len(positions)}")
    for p in get_top_positions(limit=5):
        print(f"    {p.get('symbol'):6s} — ${p.get('market_value', 0):>10,.2f} "
              f"(P&L: ${p.get('unrealized_pnl', 0):+,.2f})")


def cmd_test(client: MiroFishClient) -> None:
    """Run test simulation with sample data."""
    sample = {
        "symbol": "NVDA",
        "quantity": 100,
        "cost_basis": 18000,
        "current_price": 185,
        "market_value": 18500,
        "unrealized_pnl": 500,
    }
    prediction = simulate_position(
        client, sample, [sample], max_rounds=5, skip_graph=True
    )
    log_prediction(prediction)
    print("\nTest complete!")
    print(json.dumps(prediction, indent=2))


def cmd_scan(client: MiroFishClient, top_n: int = 3) -> None:
    """Simulate top positions by market value."""
    print(f"Finding top {top_n} positions...")
    all_positions = get_top_positions(limit=20)

    if not all_positions:
        print("No positions found.")
        return

    for i, pos in enumerate(all_positions[:top_n], 1):
        print(f"\n{'=' * 60}")
        print(f"Position {i}/{min(top_n, len(all_positions))}: ${pos.get('symbol')}")
        try:
            prediction = simulate_position(client, pos, all_positions, skip_graph=False)
            log_prediction(prediction)
        except Exception as e:
            print(f"  FAILED: {e}")

    print(f"\nDone! Predictions logged to {PREDICTIONS_LOG}")


def cmd_symbol(client: MiroFishClient, symbol: str) -> None:
    """Simulate a specific symbol."""
    all_positions = get_top_positions(limit=20)
    match = None
    for p in all_positions:
        if p.get("symbol", "").upper() == symbol.upper():
            match = p
            break

    if not match:
        print(f"Symbol {symbol} not in portfolio. Using as focus anyway...")
        match = {
            "symbol": symbol.upper(),
            "quantity": 0,
            "cost_basis": 0,
            "current_price": 0,
            "market_value": 0,
            "unrealized_pnl": 0,
        }

    prediction = simulate_position(client, match, all_positions, skip_graph=False)
    log_prediction(prediction)
    print(json.dumps(prediction, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Project Vault → MiroFish Connector")
    parser.add_argument("--test", action="store_true", help="Run test simulation")
    parser.add_argument("--scan", action="store_true", help="Simulate top positions")
    parser.add_argument("--symbol", type=str, help="Simulate specific symbol")
    parser.add_argument("--url", default="http://localhost:5001", help="MiroFish URL")
    parser.add_argument("--api-key", default=None, help="MiroFish API key")
    parser.add_argument("--top", type=int, default=3, help="Number of positions to simulate")
    args = parser.parse_args()

    client = MiroFishClient(base_url=args.url, api_key=args.api_key,
                            poll_timeout=1800)

    if args.test:
        cmd_test(client)
    elif args.scan:
        cmd_scan(client, top_n=args.top)
    elif args.symbol:
        cmd_symbol(client, args.symbol)
    else:
        cmd_health(client)
