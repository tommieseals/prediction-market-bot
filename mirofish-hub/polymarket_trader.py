#!/usr/bin/env python3
"""
POLYMARKET TRADER — Place bets via CLOB API

Setup:
1. Create .env file with POLY_PRIVATE_KEY and POLY_PROXY (optional)
2. Fund wallet with USDC on Polygon
3. Run: python polymarket_trader.py --balance

Usage:
    python polymarket_trader.py --balance              # Check wallet balance
    python polymarket_trader.py --markets "trump"      # Search markets
    python polymarket_trader.py --buy TOKEN_ID 0.50 10 # Buy 10 shares at $0.50
    python polymarket_trader.py --sell TOKEN_ID 0.50 10 # Sell 10 shares
"""

import os
import json
import argparse
import requests
from pathlib import Path
from typing import Dict, Optional
from decimal import Decimal

# Load environment
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# Proxy configuration (for geo-bypass)
PROXY_URL = os.getenv("POLY_PROXY", "")  # e.g., "http://user:pass@p.webshare.io:80"
PROXIES = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

# API endpoints
CLOB_API = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

# Chain config
POLYGON_CHAIN_ID = 137
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # USDC on Polygon

# Fee structure (March 2026+)
# Polymarket charges ~1% fee per side at 50/50 odds, scaling with price.
# Taker fees are higher; maker limit orders get rebates.
TAKER_FEE_PCT = 0.01         # ~1% taker fee (conservative estimate)
MAKER_REBATE_PCT = 0.0025    # 0.25% maker rebate on limit orders
MIN_PROFITABLE_EDGE = 0.05   # 5% minimum edge AFTER fees to be worth trading


def is_trade_profitable(edge_pct: float, order_type: str = "limit") -> dict:
    """
    Check if a trade is profitable after Polymarket fees.

    Args:
        edge_pct: Expected edge as decimal (0.08 = 8%)
        order_type: "limit" (maker, gets rebate) or "market" (taker, pays fee)

    Returns:
        Dict with 'profitable', 'net_edge', 'fee', 'recommendation'
    """
    if order_type == "market":
        fee = TAKER_FEE_PCT
    else:
        fee = -MAKER_REBATE_PCT  # Negative = we earn

    net_edge = edge_pct - fee
    profitable = net_edge >= MIN_PROFITABLE_EDGE

    return {
        "profitable": profitable,
        "gross_edge": round(edge_pct, 4),
        "fee": round(fee, 4),
        "net_edge": round(net_edge, 4),
        "recommendation": (
            "TRADE (limit order)" if profitable and order_type == "limit"
            else "TRADE (market order)" if profitable
            else "SKIP -- edge too thin after fees"
        ),
    }


class PolymarketTrader:
    """Trade on Polymarket via CLOB API."""
    
    def __init__(self, private_key: str, proxy: str = None):
        self.private_key = private_key
        self.proxy = proxy
        self.proxies = {"http": proxy, "https": proxy} if proxy else None
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize py-clob-client."""
        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds
            
            # Create client with credentials
            self.client = ClobClient(
                host=CLOB_API,
                key=self.private_key,
                chain_id=POLYGON_CHAIN_ID,
            )
            
            # Derive API credentials
            self.client.set_api_creds(self.client.create_or_derive_api_creds())
            print("[OK] CLOB client initialized")
            
        except ImportError:
            print("[FAIL] py-clob-client not installed. Run: pip install py-clob-client")
            self.client = None
        except Exception as e:
            print(f"[FAIL] Failed to init client: {e}")
            self.client = None
    
    def get_balance(self) -> Dict:
        """Get wallet balances."""
        if not self.client:
            return {"error": "Client not initialized"}
        
        try:
            # Get allowances and balances
            balances = self.client.get_balance_allowance()
            return {
                "usdc_balance": balances.get("balance", 0),
                "allowance": balances.get("allowance", 0),
            }
        except Exception as e:
            return {"error": str(e)}
    
    def search_markets(self, query: str, limit: int = 10) -> list:
        """Search for markets."""
        try:
            resp = requests.get(
                f"{GAMMA_API}/markets",
                params={"query": query, "active": "true", "limit": limit},
                proxies=self.proxies,
                timeout=15
            )
            if resp.ok:
                return resp.json()
            return []
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def get_market_price(self, token_id: str) -> Optional[float]:
        """Get current market price for a token."""
        try:
            resp = requests.get(
                f"{CLOB_API}/price",
                params={"token_id": token_id},
                proxies=self.proxies,
                timeout=15
            )
            if resp.ok:
                data = resp.json()
                return float(data.get("price", 0))
            return None
        except Exception as e:
            print(f"Price error: {e}")
            return None
    
    def get_orderbook(self, token_id: str) -> Dict:
        """Get orderbook for a token."""
        try:
            resp = requests.get(
                f"{CLOB_API}/book",
                params={"token_id": token_id},
                proxies=self.proxies,
                timeout=15
            )
            if resp.ok:
                return resp.json()
            return {}
        except Exception as e:
            print(f"Orderbook error: {e}")
            return {}
    
    def check_orderbook_depth(self, token_id: str, side: str, size: float, min_liquidity: float = 100.0) -> Dict:
        """
        Check if orderbook has sufficient liquidity before trading.
        
        Args:
            token_id: The outcome token ID
            side: "BUY" or "SELL" - checks opposite side for liquidity
            size: Intended trade size
            min_liquidity: Minimum required liquidity in USD (default $100)
            
        Returns:
            Dict with 'ok', 'liquidity', 'spread', 'warning' keys
        """
        try:
            book = self.get_orderbook(token_id)
            if not book:
                return {"ok": False, "error": "Could not fetch orderbook"}
            
            # For BUY orders, check asks (sellers); for SELL, check bids (buyers)
            check_side = "asks" if side.upper() == "BUY" else "bids"
            orders = book.get(check_side, [])
            
            if not orders:
                return {"ok": False, "error": f"No {check_side} in orderbook - market may be illiquid"}
            
            # Calculate available liquidity at reasonable prices (within 5% of best)
            best_price = float(orders[0].get("price", 0)) if orders else 0
            total_liquidity = 0.0
            depth_at_price = []
            
            for order in orders[:10]:  # Check top 10 levels
                price = float(order.get("price", 0))
                qty = float(order.get("size", 0))
                
                # Only count liquidity within 5% of best price
                if side.upper() == "BUY":
                    if price <= best_price * 1.05:
                        total_liquidity += price * qty
                        depth_at_price.append({"price": price, "size": qty, "value": price * qty})
                else:
                    if price >= best_price * 0.95:
                        total_liquidity += price * qty
                        depth_at_price.append({"price": price, "size": qty, "value": price * qty})
            
            # Calculate spread
            bids = book.get("bids", [])
            asks = book.get("asks", [])
            spread = None
            if bids and asks:
                best_bid = float(bids[0].get("price", 0))
                best_ask = float(asks[0].get("price", 0))
                spread = best_ask - best_bid
            
            # Check if our order would move the market significantly
            order_value = size * best_price
            slippage_risk = order_value > total_liquidity * 0.5  # >50% of available liquidity
            
            result = {
                "ok": total_liquidity >= min_liquidity and not slippage_risk,
                "liquidity": round(total_liquidity, 2),
                "spread": round(spread, 4) if spread else None,
                "best_price": best_price,
                "depth_levels": len(depth_at_price),
                "order_value": round(order_value, 2),
            }
            
            if total_liquidity < min_liquidity:
                result["warning"] = f"Low liquidity: ${total_liquidity:.2f} < ${min_liquidity:.2f} minimum"
            elif slippage_risk:
                result["warning"] = f"Slippage risk: order ${order_value:.2f} is >50% of ${total_liquidity:.2f} liquidity"
            
            return result
            
        except Exception as e:
            return {"ok": False, "error": f"Depth check failed: {e}"}
    
    def place_order(self, token_id: str, side: str, price: float, size: float, 
                    skip_depth_check: bool = False, edge: Optional[float] = None) -> Dict:
        """
        Place a limit order with orderbook depth validation and fee-aware execution.
        
        Args:
            token_id: The outcome token ID
            edge: Optional expected edge (0.08 = 8%). If provided, rejects trades with edge < 5% after fees
            side: "BUY" or "SELL"
            price: Price per share (0.01 to 0.99)
            size: Number of shares
            skip_depth_check: Skip liquidity check (use with caution)
        """
        if not self.client:
            return {"error": "Client not initialized"}
        
        # FEE CHECK: Ensure trade is profitable after Polymarket fees
        if edge is not None:
            fee_check = is_trade_profitable(edge, order_type="limit")
            if not fee_check["profitable"]:
                print(f"[SKIP] Trade rejected: edge {edge:.1%} too thin after fees")
                print(f"       Net edge: {fee_check['net_edge']:.1%}, need {MIN_PROFITABLE_EDGE:.1%}")
                return {
                    "error": "Edge too thin after fees",
                    "gross_edge": fee_check["gross_edge"],
                    "net_edge": fee_check["net_edge"],
                    "min_required": MIN_PROFITABLE_EDGE,
                    "recommendation": fee_check["recommendation"],
                }

        # H16 FIX: Check orderbook depth before placing order
        if not skip_depth_check:
            depth = self.check_orderbook_depth(token_id, side, size)
            if not depth.get("ok"):
                warning = depth.get("warning") or depth.get("error", "Unknown liquidity issue")
                print(f"[WARN] Orderbook depth check failed: {warning}")
                return {
                    "error": f"Orderbook depth check failed: {warning}",
                    "depth_info": depth,
                    "hint": "Use skip_depth_check=True to force (not recommended)"
                }
            print(f"[OK] Orderbook depth OK: ${depth['liquidity']:.2f} liquidity, spread={depth.get('spread')}")
        
        try:
            from py_clob_client.order_builder.constants import BUY, SELL
            from py_clob_client.clob_types import OrderArgs
            
            order_side = BUY if side.upper() == "BUY" else SELL
            
            # Create OrderArgs object (new API)
            order_args = OrderArgs(
                token_id=str(token_id),
                price=float(price),
                size=float(size),
                side=order_side,
            )
            
            # Create and post order
            order = self.client.create_and_post_order(order_args)
            
            return {
                "success": True,
                "order_id": order.get("orderID"),
                "status": order.get("status"),
                "details": order
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an open order."""
        if not self.client:
            return {"error": "Client not initialized"}
        
        try:
            result = self.client.cancel(order_id)
            return {"success": True, "result": result}
        except Exception as e:
            return {"error": str(e)}
    
    def get_open_orders(self) -> list:
        """Get all open orders."""
        if not self.client:
            return []
        
        try:
            return self.client.get_orders()
        except Exception as e:
            print(f"Orders error: {e}")
            return []


def create_test_wallet():
    """Generate a new test wallet."""
    try:
        from eth_account import Account
        account = Account.create()
        return {
            "address": account.address,
            "private_key": account.key.hex(),
            "warning": "SAVE THIS KEY! Fund with USDC on Polygon to trade."
        }
    except ImportError:
        return {"error": "eth-account not installed"}


def main():
    parser = argparse.ArgumentParser(description="Polymarket Trading CLI")
    parser.add_argument("--balance", action="store_true", help="Check wallet balance")
    parser.add_argument("--markets", type=str, help="Search markets by query")
    parser.add_argument("--price", type=str, help="Get price for token ID")
    parser.add_argument("--book", type=str, help="Get orderbook for token ID")
    parser.add_argument("--buy", nargs=3, metavar=("TOKEN", "PRICE", "SIZE"), help="Buy shares")
    parser.add_argument("--sell", nargs=3, metavar=("TOKEN", "PRICE", "SIZE"), help="Sell shares")
    parser.add_argument("--orders", action="store_true", help="List open orders")
    parser.add_argument("--cancel", type=str, help="Cancel order by ID")
    parser.add_argument("--new-wallet", action="store_true", help="Generate new test wallet")
    args = parser.parse_args()
    
    if args.new_wallet:
        wallet = create_test_wallet()
        print("\n🔑 NEW WALLET GENERATED")
        print("=" * 50)
        print(f"Address: {wallet.get('address')}")
        print(f"Private Key: {wallet.get('private_key')}")
        print(f"\n[WARN]  {wallet.get('warning')}")
        print("\nAdd to .env file:")
        print(f'POLY_PRIVATE_KEY={wallet.get("private_key")}')
        return
    
    # Load private key
    private_key = os.getenv("POLY_PRIVATE_KEY")
    if not private_key:
        print("[FAIL] Set POLY_PRIVATE_KEY in .env file")
        print("   Run: python polymarket_trader.py --new-wallet")
        return
    
    proxy = os.getenv("POLY_PROXY", "")
    trader = PolymarketTrader(private_key, proxy)
    
    if args.balance:
        bal = trader.get_balance()
        print("\n[MONEY] WALLET BALANCE")
        print("=" * 40)
        if "error" in bal:
            print(f"Error: {bal['error']}")
        else:
            print(f"USDC Balance: ${bal.get('usdc_balance', 0):.2f}")
            print(f"Allowance: ${bal.get('allowance', 0):.2f}")
    
    elif args.markets:
        markets = trader.search_markets(args.markets)
        print(f"\n[SCAN] MARKETS: '{args.markets}'")
        print("=" * 60)
        for m in markets[:10]:
            title = m.get("question", m.get("title", "Unknown"))[:60]
            cid = m.get("conditionId", "")
            closed = m.get("closed", False)
            if closed:
                continue  # Skip closed markets
            print(f"  {title}...")
            print(f"    Condition: {cid[:40]}...")
            # Get token IDs from the correct field
            tokens = m.get("clobTokenIds") or m.get("clob_token_ids") or []
            if isinstance(tokens, str):
                import json as js
                try:
                    tokens = js.loads(tokens)
                except (ValueError, TypeError):  # H12 FIX: Specific JSON decode errors
                    tokens = []
            if tokens and len(tokens) >= 2:
                print(f"    YES: {tokens[0]}")
                print(f"    NO:  {tokens[1]}")
            print()
    
    elif args.price:
        price = trader.get_market_price(args.price)
        print(f"\n💵 Price for {args.price[:20]}...: ${price}")
    
    elif args.book:
        book = trader.get_orderbook(args.book)
        print(f"\n📖 ORDERBOOK")
        print(json.dumps(book, indent=2)[:500])
    
    elif args.buy:
        token, price, size = args.buy
        print(f"\n[GREEN] BUYING {size} shares @ ${price}")
        result = trader.place_order(token, "BUY", float(price), float(size))
        print(json.dumps(result, indent=2))
    
    elif args.sell:
        token, price, size = args.sell
        print(f"\n[RED] SELLING {size} shares @ ${price}")
        result = trader.place_order(token, "SELL", float(price), float(size))
        print(json.dumps(result, indent=2))
    
    elif args.orders:
        orders = trader.get_open_orders()
        print(f"\n[LIST] OPEN ORDERS ({len(orders)})")
        for o in orders:
            print(json.dumps(o, indent=2))
    
    elif args.cancel:
        result = trader.cancel_order(args.cancel)
        print(f"\n[FAIL] CANCEL ORDER")
        print(json.dumps(result, indent=2))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
