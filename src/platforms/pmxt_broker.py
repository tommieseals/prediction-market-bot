"""
TerminatorBot - pmxt Platform Adapter

Wraps the pmxt unified library to provide PlatformBroker implementations
for Kalshi, Polymarket, Limitless, etc.

pmxt API returns typed dataclass objects:
  - pmxt.UnifiedMarket (with .yes, .no MarketOutcome fields)
  - pmxt.Balance (currency, total, available, locked)
  - pmxt.Order (id, market_id, outcome_id, side, amount, status, filled, etc.)
  - pmxt.Position (market_id, outcome_id, outcome_label, size, entry_price, etc.)
  - pmxt.OrderBook (with bids/asks)
"""

from __future__ import annotations

import asyncio
import logging
import time
from functools import wraps
from typing import Optional, Callable, TypeVar, Any

from platforms.base import (
    PlatformBroker, UnifiedMarket, UnifiedOrder,
    UnifiedPosition, PlatformBalance,
)
from config import Config

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ── Retry Decorator with Exponential Backoff ─────────────────────────────

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
):
    """
    Decorator for retrying API calls with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap
        exponential_base: Multiplier for each retry
        retryable_exceptions: Tuple of exceptions that trigger retry
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    # Don't retry on the last attempt
                    if attempt == max_retries:
                        break
                    
                    # Calculate delay with exponential backoff + jitter
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    # Add jitter (10-30% randomness)
                    import random
                    delay *= (1 + random.uniform(0.1, 0.3))
                    
                    logger.warning(
                        "Retry %d/%d for %s after %.2fs: %s",
                        attempt + 1, max_retries, func.__name__, delay, str(e)[:100]
                    )
                    await asyncio.sleep(delay)
            
            # All retries exhausted
            logger.error(
                "All %d retries exhausted for %s: %s",
                max_retries, func.__name__, last_exception
            )
            raise last_exception
        
        return wrapper
    return decorator


def _safe_float(val, default: float = 0.0) -> float:
    """Safely convert to float, handling None and strings."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val, default: int = 0) -> int:
    """Safely convert to int, handling None and strings."""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


class PmxtBroker(PlatformBroker):
    """
    Generic pmxt-backed broker. Instantiate with an exchange name
    (e.g., 'kalshi', 'polymarket', 'limitless') and keyword credentials.
    """

    def __init__(
        self,
        exchange_name: str,
        credentials: dict,
        dry_run: bool = True,
    ):
        self._exchange_name = exchange_name.lower()
        self._credentials = credentials
        self._dry_run = dry_run
        self._client = None
        self._connected = False
        self._last_error = None
        self._connection_attempts = 0
        self._max_connection_attempts = 3

    @property
    def platform_name(self) -> str:
        return self._exchange_name

    @property
    def is_dry_run(self) -> bool:
        return self._dry_run

    @property
    def last_error(self) -> Optional[str]:
        """Returns the last error message, useful for debugging."""
        return self._last_error

    async def connect(self) -> bool:
        """Initialize connection with retry logic."""
        self._connection_attempts += 1
        
        if self._connection_attempts > self._max_connection_attempts:
            logger.error(
                "pmxt/%s: Max connection attempts (%d) exceeded",
                self._exchange_name, self._max_connection_attempts
            )
            return False
        
        try:
            import pmxt

            # pmxt uses capitalized class names (Kalshi, Polymarket, Limitless)
            class_name = self._exchange_name.capitalize()
            exchange_class = getattr(pmxt, class_name, None)
            if exchange_class is None:
                self._last_error = f"pmxt has no exchange '{self._exchange_name}' (tried class '{class_name}')"
                logger.error(self._last_error)
                return False

            # Filter out None credentials to avoid passing empty values
            filtered_creds = {k: v for k, v in self._credentials.items() if v}
            
            # Pass credentials as keyword args (pmxt uses api_key=, private_key=, etc.)
            self._client = exchange_class(**filtered_creds)

            # Test connection by loading markets (pmxt methods are synchronous)
            # Run in executor to not block event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._client.load_markets)
            
            self._connected = True
            self._last_error = None
            logger.info(
                "pmxt/%s connected (dry_run=%s, attempt=%d)",
                self._exchange_name, self._dry_run, self._connection_attempts,
            )
            return True
            
        except Exception as e:
            self._last_error = str(e)
            logger.error(
                "pmxt/%s connection failed (attempt %d/%d): %s",
                self._exchange_name, self._connection_attempts, 
                self._max_connection_attempts, e
            )
            
            # Retry with backoff
            if self._connection_attempts < self._max_connection_attempts:
                delay = 2 ** self._connection_attempts
                logger.info("Retrying connection in %ds...", delay)
                await asyncio.sleep(delay)
                return await self.connect()
            
            return False

    async def reconnect(self) -> bool:
        """Force reconnection (resets attempt counter)."""
        self._connected = False
        self._connection_attempts = 0
        self._client = None
        return await self.connect()

    async def health_check(self) -> bool:
        """Verify the connection is alive with retry."""
        if not self._connected:
            return False
        try:
            # Try fetching a small number of markets as health check
            markets = await self.fetch_markets(limit=1)
            return len(markets) > 0
        except Exception as e:
            logger.warning("pmxt/%s health check failed: %s", self._exchange_name, e)
            return False

    @retry_with_backoff(max_retries=2, base_delay=1.0)
    async def fetch_markets(
        self,
        category: Optional[str] = None,
        status: str = "open",
        limit: int = 500,
        query: Optional[str] = None,
    ) -> list[UnifiedMarket]:
        if not self._connected:
            logger.warning("pmxt/%s: Not connected, returning empty markets", self._exchange_name)
            return []

        try:
            # pmxt.fetch_markets() returns List[pmxt.UnifiedMarket]
            kwargs = {}
            if query:
                kwargs["query"] = query

            # Run synchronous pmxt call in executor
            loop = asyncio.get_event_loop()
            raw_markets = await loop.run_in_executor(
                None, 
                lambda: self._client.fetch_markets(**kwargs)
            )
            
            markets = []

            for m in raw_markets:
                try:
                    # Category filter
                    mcat = (getattr(m, 'category', '') or "").lower()
                    if category and category.lower() not in mcat:
                        continue

                    # Query filter (if pmxt doesn't handle it)
                    title = getattr(m, 'title', '') or ''
                    if query and query.lower() not in title.lower():
                        continue

                    # Extract yes/no prices from MarketOutcome objects
                    yes_price = m.yes.price if hasattr(m, 'yes') and m.yes else 0.0
                    no_price = m.no.price if hasattr(m, 'no') and m.no else (1.0 - yes_price if yes_price > 0 else 0.0)

                    # Resolution date
                    close_date = None
                    if hasattr(m, 'resolution_date') and m.resolution_date:
                        close_date = m.resolution_date.isoformat()

                    markets.append(UnifiedMarket(
                        platform=self._exchange_name,
                        market_id=m.market_id,
                        title=title,
                        description=getattr(m, 'description', '') or "",
                        category=mcat,
                        yes_price=yes_price,
                        no_price=no_price,
                        volume=_safe_float(getattr(m, 'volume', 0)),
                        liquidity=_safe_float(getattr(m, 'liquidity', 0)),
                        open_interest=_safe_float(getattr(m, 'open_interest', 0)),
                        close_date=close_date,
                        status="open",
                        raw_data={
                            "url": getattr(m, 'url', None),
                            "volume_24h": getattr(m, 'volume_24h', None),
                            "yes_outcome_id": m.yes.outcome_id if hasattr(m, 'yes') and m.yes else None,
                            "no_outcome_id": m.no.outcome_id if hasattr(m, 'no') and m.no else None,
                        },
                    ))

                    if len(markets) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug("Skipping malformed market: %s", e)
                    continue

            return markets
            
        except Exception as e:
            self._last_error = str(e)
            logger.error("pmxt/%s fetch_markets failed: %s", self._exchange_name, e)
            raise  # Let retry decorator handle

    @retry_with_backoff(max_retries=2, base_delay=0.5)
    async def fetch_orderbook(self, market_id: str) -> dict:
        if not self._connected:
            return {"bids": [], "asks": []}
        try:
            loop = asyncio.get_event_loop()
            ob = await loop.run_in_executor(
                None,
                lambda: self._client.fetch_order_book(market_id)
            )
            return {
                "bids": [[level.price, level.size] for level in (ob.bids or [])],
                "asks": [[level.price, level.size] for level in (ob.asks or [])],
            }
        except Exception as e:
            self._last_error = str(e)
            logger.error("pmxt/%s fetch_orderbook failed: %s", self._exchange_name, e)
            raise

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def place_order(
        self,
        market_id: str,
        side: str,
        quantity: int,
        price: float,
        order_type: str = "limit",
    ) -> UnifiedOrder:
        # Input validation
        if not market_id:
            raise ValueError("market_id is required")
        if side not in ("yes", "no", "buy", "sell"):
            raise ValueError(f"Invalid side: {side}")
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive: {quantity}")
        if not 0 < price <= 1:
            raise ValueError(f"Price must be between 0 and 1: {price}")
        
        if self._dry_run:
            logger.info(
                "[DRY RUN] pmxt/%s order: %s %d @ %.4f on %s",
                self._exchange_name, side, quantity, price, market_id,
            )
            return UnifiedOrder(
                platform=self._exchange_name,
                order_id=f"DRY-{market_id[:8]}",
                market_id=market_id,
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type,
                status="filled",
                filled_quantity=quantity,
                filled_price=price,
            )

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._client.create_order(
                    market_id=market_id,
                    side="buy" if side in ("yes", "buy") else "sell",
                    type=order_type if order_type != "fok" else "limit",
                    amount=quantity,
                    price=price,
                )
            )

            return UnifiedOrder(
                platform=self._exchange_name,
                order_id=str(result.id),
                market_id=market_id,
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type,
                status=getattr(result, 'status', 'pending'),
                filled_quantity=_safe_int(getattr(result, 'filled', 0)),
                filled_price=_safe_float(getattr(result, 'price', price), price),
            )
        except Exception as e:
            self._last_error = str(e)
            logger.error("pmxt/%s place_order failed: %s", self._exchange_name, e)
            
            # Return failed order instead of raising (so retry can work)
            return UnifiedOrder(
                platform=self._exchange_name,
                order_id="FAILED",
                market_id=market_id,
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type,
                status="failed",
                raw_data={"error": str(e)},
            )

    @retry_with_backoff(max_retries=2, base_delay=0.5)
    async def cancel_order(self, order_id: str) -> bool:
        if self._dry_run:
            logger.info("[DRY RUN] pmxt/%s cancel order %s", self._exchange_name, order_id)
            return True
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.cancel_order(order_id)
            )
            return True
        except Exception as e:
            self._last_error = str(e)
            logger.error("pmxt/%s cancel_order failed: %s", self._exchange_name, e)
            raise

    async def cancel_all_orders(self) -> int:
        if self._dry_run:
            logger.info("[DRY RUN] pmxt/%s cancel all orders", self._exchange_name)
            return 0
        try:
            loop = asyncio.get_event_loop()
            orders = await loop.run_in_executor(
                None,
                self._client.fetch_open_orders
            )
            count = 0
            for order in (orders or []):
                try:
                    await self.cancel_order(order.id)
                    count += 1
                except Exception as e:
                    logger.warning("Failed to cancel order %s: %s", order.id, e)
            return count
        except Exception as e:
            self._last_error = str(e)
            logger.error("pmxt/%s cancel_all failed: %s", self._exchange_name, e)
            return 0

    @retry_with_backoff(max_retries=2, base_delay=1.0)
    async def fetch_positions(self) -> list[UnifiedPosition]:
        if not self._connected:
            return []
        try:
            loop = asyncio.get_event_loop()
            positions = await loop.run_in_executor(
                None,
                self._client.fetch_positions
            )
            
            result = []
            for p in (positions or []):
                try:
                    outcome_label = getattr(p, 'outcome_label', '') or ''
                    side = "yes" if outcome_label.lower() in ("yes", "buy") else "no"
                    
                    result.append(UnifiedPosition(
                        platform=self._exchange_name,
                        market_id=getattr(p, 'market_id', ''),
                        market_title=outcome_label or getattr(p, 'market_id', ''),
                        side=side,
                        quantity=_safe_int(getattr(p, 'size', 0)),
                        avg_price=_safe_float(getattr(p, 'entry_price', 0)),
                        current_price=_safe_float(getattr(p, 'current_price', 0)),
                        unrealized_pnl=_safe_float(getattr(p, 'unrealized_pnl', 0)),
                    ))
                except Exception as e:
                    logger.debug("Skipping malformed position: %s", e)
                    continue
                    
            return result
            
        except Exception as e:
            self._last_error = str(e)
            logger.error("pmxt/%s fetch_positions failed: %s", self._exchange_name, e)
            raise

    async def fetch_balance(self) -> PlatformBalance:
        """Fetch account balance with fallback for dry run mode."""
        if self._dry_run:
            return PlatformBalance(
                platform=self._exchange_name,
                available=Config.PAPER_STARTING_BALANCE,
                total=Config.PAPER_STARTING_BALANCE,
                currency="USD",
            )
        
        try:
            loop = asyncio.get_event_loop()
            balances = await loop.run_in_executor(
                None,
                self._client.fetch_balance
            )

            if not balances:
                logger.warning("pmxt/%s: fetch_balance returned empty", self._exchange_name)
                return PlatformBalance(
                    platform=self._exchange_name,
                    available=0.0,
                    total=0.0,
                )

            # Use the first balance (typically USD or USDC)
            bal = balances[0]
            return PlatformBalance(
                platform=self._exchange_name,
                available=_safe_float(getattr(bal, 'available', 0)),
                total=_safe_float(getattr(bal, 'total', 0)),
                currency=getattr(bal, 'currency', 'USD'),
            )
            
        except Exception as e:
            self._last_error = str(e)
            logger.warning(
                "pmxt/%s fetch_balance failed (falling back to paper): %s",
                self._exchange_name, e
            )
            # Graceful fallback - return paper balance on error
            return PlatformBalance(
                platform=self._exchange_name,
                available=Config.PAPER_STARTING_BALANCE,
                total=Config.PAPER_STARTING_BALANCE,
                currency="USD",
                raw_data={"error": str(e), "fallback": True},
            )


# ── Factory functions for each exchange ──────────────────────────────

def create_kalshi_broker(dry_run: bool = True) -> PmxtBroker:
    """Create a Kalshi broker instance."""
    creds = {
        "api_key": Config.KALSHI_API_KEY or None,
        "private_key": Config.KALSHI_PRIVATE_KEY_PATH or None,
    }
    return PmxtBroker("kalshi", creds, dry_run=dry_run)


def create_polymarket_broker(dry_run: bool = True) -> PmxtBroker:
    """Create a Polymarket broker instance."""
    creds = {
        "api_key": Config.POLYMARKET_API_KEY or None,
        "api_secret": Config.POLYMARKET_API_SECRET or None,
        "passphrase": Config.POLYMARKET_API_PASSPHRASE or None,
        "private_key": Config.POLYMARKET_PRIVATE_KEY or None,
    }
    return PmxtBroker("polymarket", creds, dry_run=dry_run)


def create_limitless_broker(dry_run: bool = True) -> PmxtBroker:
    """Create a Limitless broker instance."""
    creds = {
        "api_key": Config.LIMITLESS_API_KEY or None,
    }
    return PmxtBroker("limitless", creds, dry_run=dry_run)
