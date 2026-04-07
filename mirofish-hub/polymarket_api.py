#!/usr/bin/env python3
"""
POLYMARKET API CLIENT — Synchronous wrapper for Gamma + Data + CLOB APIs
Correct endpoints per Polymarket documentation.
Cloudflare-aware rate limiting.
"""

import os
import time
import requests
import logging
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("polymarket_api")

# ── API base URLs ──────────────────────────────────────────────
GAMMA_API = "https://gamma-api.polymarket.com"
DATA_API  = "https://data-api.polymarket.com"
CLOB_API  = "https://clob.polymarket.com"

# Polymarket API key (JWT) for authenticated access
POLYMARKET_API_KEY = os.getenv(
    "POLYMARKET_API_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc5NDAzOTM1LCJpYXQiOjE3NzQyMTk5MzUsImp0aSI6IjM3Yjg3ZmY5YTQ3NTQ2YjBhNjQ4ZDUxMTQ1MDMyYzRkIiwidXNlcl9pZCI6NzE5LCJzY29wZSI6ImxhdW5jaHBhZDphZ2VudC1yZWFkLHJldHJpZXZlcjplY2hvLWdlbmVyYXRpb24scmV0cmlldmVyOmZlYXR1cmUtZXh0cmFjdGlvbix1c2VyOnJlYWQscmV0cmlldmVyOmFnZW50LW9wdGlvbi1yZXRyaWV2YWwsbGF1bmNocGFkOmFnZW50LWNyZWF0aW9uLGxhdW5jaHBhZDphZ2VudC11cGRhdGUsdXNlcjp3cml0ZSxyZXRyaWV2ZXI6c2VtYW50aWMtcmV0cmlldmFsLGxhdW5jaHBhZDplY2hvLXN0eWxlLWNyZWF0aW9uIiwidG9rZW5fbmFtZSI6ImJhc2VfbG9naW4ifQ.nHJYn-uNtL18khr620m97KDBHGiJ2O1k_19aMOC4g40"
)

# Default throttle (Cloudflare queues rather than rejects — silent latency killer)
DEFAULT_RATE_LIMIT = 0.35  # seconds between requests (tested: 0.3s works without 429s)


class PolymarketAPI:
    """
    Synchronous Polymarket API client with rate limiting.

    Three APIs:
      Gamma  — market discovery, metadata, events
      Data   — wallet positions, leaderboard, analytics
      CLOB   — orderbook depth, prices
    """

    def __init__(self, rate_limit: float = DEFAULT_RATE_LIMIT,
                 api_key: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MiroFish-WhaleHunter/2.0",
            "Accept": "application/json",
        })
        # Add API key for authenticated endpoints
        key = api_key or POLYMARKET_API_KEY
        if key:
            self.session.headers["Authorization"] = f"Bearer {key}"
        self.rate_limit = rate_limit
        self._last_request_time = 0.0
        self._request_count = 0
        self._slow_responses = 0  # Cloudflare throttling indicator

    def close(self):
        self.session.close()

    # ── Core request method ────────────────────────────────────

    def _throttled_get(self, url: str, params: Dict = None,
                       timeout: float = 15.0) -> Optional[Dict]:
        """
        Rate-limited GET with Cloudflare throttling detection.

        Cloudflare throttling = delays (not 429 rejections), which silently
        destroys "copy before market adjusts" timing if uninstrumented.
        """
        # Enforce rate limit
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

        self._last_request_time = time.time()
        self._request_count += 1

        try:
            start = time.time()
            resp = self.session.get(url, params=params, timeout=timeout)
            elapsed_ms = (time.time() - start) * 1000

            # Detect Cloudflare throttling via response time
            if elapsed_ms > 3000:
                self._slow_responses += 1
                logger.warning(
                    f"Slow response ({elapsed_ms:.0f}ms) — possible throttling: "
                    f"{url.split('?')[0]}"
                )

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited (429). Waiting {retry_after}s")
                time.sleep(retry_after)
                return self._throttled_get(url, params, timeout)

            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(f"API {resp.status_code}: {url}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout: {url}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error: {url}")
            return None
        except Exception as e:
            logger.error(f"Request failed: {url} — {e}")
            return None

    # ── Gamma API (market discovery / metadata) ────────────────

    def search_markets(self, query: str = "", active: bool = True,
                       limit: int = 100) -> List[Dict]:
        """
        GET /markets — search/list markets.
        Returns market objects with condition_id, question, outcomes, etc.
        """
        params = {"limit": limit, "active": active}
        if query:
            params["query"] = query
        result = self._throttled_get(f"{GAMMA_API}/markets", params)
        if isinstance(result, list):
            return result
        return result if result else []

    def get_market(self, condition_id: str) -> Optional[Dict]:
        """
        GET /markets/{condition_id} — single market metadata.
        Returns: question, outcomes, end_date, volume, enableOrderBook, etc.
        """
        return self._throttled_get(f"{GAMMA_API}/markets/{condition_id}")

    def get_events(self, limit: int = 50) -> List[Dict]:
        """
        GET /events — list events (groups of related markets).
        """
        params = {"limit": limit}
        result = self._throttled_get(f"{GAMMA_API}/events", params)
        if isinstance(result, list):
            return result
        return result if result else []

    # ── Data API (wallet analytics / leaderboard) ──────────────

    def get_leaderboard(self, category: str = "ALL",
                        period: str = "ALL",
                        limit: int = 100,
                        sort_by: str = "PNL") -> List[Dict]:
        """
        GET /leaderboard — top traders by PnL or volume.

        Correct endpoint per Polymarket Data API docs.
        Returns: list of {rank, address/walletAddress, username, volume, pnl}
        Note: Does NOT return win_rate — that's the whole reason we compute
        proper scoring ourselves.
        """
        params = {
            "limit": limit,
            "offset": 0,
            "sortBy": sort_by,
        }
        result = self._throttled_get(f"{DATA_API}/v1/leaderboard", params)
        if isinstance(result, list):
            return result
        # Some endpoints wrap in {"data": [...]} or {"traders": [...]}
        if isinstance(result, dict):
            return (result.get("data") or result.get("traders")
                    or result.get("leaderboard") or [])
        return []

    def get_positions(self, user: str) -> List[Dict]:
        """
        GET /positions?user={address} — current open positions.
        Returns: list of position objects with market_id, size, avgEntryPrice, etc.
        """
        result = self._throttled_get(
            f"{DATA_API}/positions", {"user": user}
        )
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("positions", result.get("data", []))
        return []

    def get_closed_positions(self, user: str,
                              start: int = None,
                              end: int = None,
                              limit: int = 50,
                              max_total: int = 500) -> List[Dict]:
        """
        GET /closed-positions?user={address} — resolved positions with pagination.

        The API returns results sorted by realizedPnl DESC and defaults to 10
        results without a limit param.  We paginate to fetch ALL closed
        positions (up to *max_total*) so that scoring uses the complete
        trading history, not just the top-10 most profitable trades.
        """
        all_positions: List[Dict] = []
        offset = 0
        while offset < max_total:
            params: Dict = {"user": user, "limit": limit, "offset": offset}
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            result = self._throttled_get(
                f"{DATA_API}/closed-positions", params
            )
            batch: List[Dict] = []
            if isinstance(result, list):
                batch = result
            elif isinstance(result, dict):
                batch = result.get("positions", result.get("data", []))
            if not batch:
                break
            all_positions.extend(batch)
            if len(batch) < limit:
                break  # Last page
            offset += limit
        return all_positions

    def get_activity(self, user: str,
                     start: int = None,
                     activity_type: str = None) -> List[Dict]:
        """
        GET /activity?user={address} — recent trade activity.
        Types: TRADE, SPLIT, MERGE, REDEEM, CONVERSION (neg-risk mechanics).
        Includes proxyWallet, transactionHash, market identifiers.
        """
        params = {"user": user}
        if start:
            params["start"] = start
        if activity_type:
            params["type"] = activity_type
        result = self._throttled_get(
            f"{DATA_API}/activity", params
        )
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("activity", result.get("data", []))
        return []

    def get_value(self, user: str) -> Optional[Dict]:
        """
        GET /value?user={address} — portfolio value / equity curve.
        Used for drawdown calculation.
        """
        return self._throttled_get(
            f"{DATA_API}/value", {"user": user}
        )

    def get_market_holders(self, condition_id: str) -> List[Dict]:
        """
        GET /holders?market={condition_id} — position holders for a market.
        """
        result = self._throttled_get(
            f"{DATA_API}/holders", {"market": condition_id}
        )
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("holders", result.get("data", []))
        return []

    # ── CLOB API (orderbook / prices) ──────────────────────────

    def get_orderbook(self, token_id: str) -> Optional[Dict]:
        """
        GET /book?token_id={token_id} — orderbook depth (bids/asks).
        Used for slippage calculation before trade emulation.
        """
        return self._throttled_get(
            f"{CLOB_API}/book", {"token_id": token_id}
        )

    def get_price(self, token_id: str) -> Optional[Dict]:
        """
        GET /price?token_id={token_id} — current best price.
        """
        return self._throttled_get(
            f"{CLOB_API}/price", {"token_id": token_id}
        )

    def get_midpoint(self, token_id: str) -> Optional[Dict]:
        """
        GET /midpoint?token_id={token_id} — orderbook midpoint.
        """
        return self._throttled_get(
            f"{CLOB_API}/midpoint", {"token_id": token_id}
        )

    # ── Convenience ────────────────────────────────────────────

    def health_check(self) -> bool:
        """Quick connectivity check against Gamma API."""
        try:
            result = self._throttled_get(
                f"{GAMMA_API}/markets", {"limit": 1, "active": True},
                timeout=10
            )
            return result is not None
        except Exception:
            return False

    def get_stats(self) -> Dict:
        """Return rate-limit and throttling stats."""
        return {
            "total_requests": self._request_count,
            "slow_responses": self._slow_responses,
            "throttle_ratio": (
                self._slow_responses / max(self._request_count, 1)
            ),
        }

    # ── Orderbook analysis helpers ─────────────────────────────

    def calculate_slippage(self, token_id: str,
                            side: str, size_usd: float) -> Dict:
        """
        Calculate expected slippage for a given trade size.

        Walks the orderbook to estimate fill price vs midpoint.
        Returns: {feasible, slippage_pct, avg_fill_price, depth_1pct}
        """
        book = self.get_orderbook(token_id)
        if not book:
            return {
                "feasible": False,
                "slippage_pct": 0.05,
                "avg_fill_price": 0,
                "depth_1pct": 0,
                "reason": "Orderbook unavailable",
            }

        # Select correct side
        if side.upper() in ("BUY", "YES"):
            levels = book.get("asks", [])
        else:
            levels = book.get("bids", [])

        if not levels:
            return {
                "feasible": False,
                "slippage_pct": 0.05,
                "avg_fill_price": 0,
                "depth_1pct": 0,
                "reason": "No liquidity on this side",
            }

        # Walk the book
        filled = 0.0
        cost = 0.0
        best_price = float(levels[0].get("price", 0.5))

        for level in levels:
            price = float(level.get("price", 0))
            level_size = float(level.get("size", 0))
            level_value = price * level_size

            remaining = size_usd - filled
            if remaining <= 0:
                break

            take = min(level_value, remaining)
            filled += take
            cost += take  # Already in USD terms

        if filled < size_usd * 0.5:
            return {
                "feasible": False,
                "slippage_pct": 0.10,
                "avg_fill_price": best_price,
                "depth_1pct": filled,
                "reason": f"Insufficient depth: ${filled:.0f} vs ${size_usd:.0f} needed",
            }

        avg_fill = cost / max(filled, 0.01)
        slippage = abs(avg_fill - best_price) / max(best_price, 0.01)

        # Depth at 1% from best
        depth_1pct = sum(
            float(l.get("size", 0)) * float(l.get("price", 0))
            for l in levels
            if abs(float(l.get("price", 0)) - best_price) <= 0.01
        )

        return {
            "feasible": True,
            "slippage_pct": round(slippage, 4),
            "avg_fill_price": round(avg_fill, 4),
            "depth_1pct": round(depth_1pct, 2),
            "best_price": best_price,
            "reason": "OK",
        }


# ── CLI test ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("POLYMARKET API CLIENT — Health Check")
    print("=" * 60)

    api = PolymarketAPI(rate_limit=1.0)

    # 1. Gamma API — market discovery
    print("\n📡 Gamma API (market discovery)...")
    if api.health_check():
        print("  [OK] Gamma API: ONLINE")
        markets = api.search_markets(limit=3, active=True)
        if markets:
            print(f"  Found {len(markets)} sample markets:")
            for m in markets[:3]:
                question = m.get("question", m.get("title", "?"))[:70]
                try:
                    vol = float(m.get("volume", 0) or 0)
                    print(f"    • {question}  (vol: ${vol:,.0f})")
                except (ValueError, TypeError):
                    print(f"    • {question}")
    else:
        print("  [FAIL] Gamma API: OFFLINE")

    # 2. Data API — leaderboard
    print("\n[STATS] Data API (wallet analytics)...")
    leaders = api.get_leaderboard(limit=5)
    if leaders:
        print(f"  [OK] Data API: ONLINE — {len(leaders)} leaderboard entries")
        for i, entry in enumerate(leaders[:5]):
            addr = (entry.get("proxyWallet") or entry.get("walletAddress")
                    or entry.get("address") or "?")
            name = (entry.get("userName") or entry.get("username")
                    or entry.get("displayName") or addr[:10])
            pnl = entry.get("pnl", entry.get("totalPnl", 0))
            vol = entry.get("vol", entry.get("volume", entry.get("totalVolume", 0)))
            try:
                pnl_f = float(pnl)
                vol_f = float(vol)
                print(f"    #{i+1} {name:20s} PnL: ${pnl_f:>12,.2f}  Vol: ${vol_f:>14,.2f}")
            except (ValueError, TypeError):
                print(f"    #{i+1} {name:20s} PnL: {pnl}  Vol: {vol}")
    else:
        print("  [WARN]  Data API: No leaderboard data (may need different endpoint)")

    # 3. CLOB API — orderbook (needs a token_id, skip if none)
    print("\n📖 CLOB API (orderbook)...")
    print("  ⏩ Skipped (requires specific token_id)")

    # Stats
    stats = api.get_stats()
    print(f"\n[UP] Session stats: {stats['total_requests']} requests, "
          f"{stats['slow_responses']} slow responses")

    api.close()
    print("\n[OK] Polymarket API client ready")
