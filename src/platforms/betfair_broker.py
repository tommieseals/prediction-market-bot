"""
TerminatorBot - Betfair Platform Adapter

Wraps betfairlightweight to provide PlatformBroker interface.
Betfair uses back/lay instead of yes/no:
  - Back = YES (you believe event will happen)
  - Lay  = NO  (you believe event will NOT happen)

Betfair uses decimal odds (e.g., 2.5) instead of probabilities.
  Conversion: probability = 1 / decimal_odds
"""

from __future__ import annotations

import logging
from typing import Optional

from platforms.base import (
    PlatformBroker, UnifiedMarket, UnifiedOrder,
    UnifiedPosition, PlatformBalance,
)
from config import Config

logger = logging.getLogger(__name__)


class BetfairBroker(PlatformBroker):
    """Betfair Exchange adapter using betfairlightweight."""

    def __init__(self, dry_run: bool = True):
        self._dry_run = dry_run
        self._client = None
        self._connected = False

    @property
    def platform_name(self) -> str:
        return "betfair"

    @property
    def is_dry_run(self) -> bool:
        return self._dry_run

    async def connect(self) -> bool:
        if not Config.BETFAIR_USERNAME or not Config.BETFAIR_APP_KEY:
            logger.warning("Betfair credentials not configured, skipping.")
            return False

        try:
            import betfairlightweight

            self._client = betfairlightweight.APIClient(
                username=Config.BETFAIR_USERNAME,
                password=Config.BETFAIR_PASSWORD,
                app_key=Config.BETFAIR_APP_KEY,
                certs=Config.BETFAIR_CERT_PATH or None,
            )

            if not self._dry_run:
                self._client.login()

            self._connected = True
            logger.info("Betfair connected (dry_run=%s)", self._dry_run)
            return True
        except Exception as e:
            logger.error("Betfair connection failed: %s", e)
            return False

    async def fetch_markets(
        self,
        category: Optional[str] = None,
        status: str = "open",
        limit: int = 500,
        query: Optional[str] = None,
    ) -> list[UnifiedMarket]:
        if not self._connected and not self._dry_run:
            return []

        try:
            market_filter = {}
            if query:
                market_filter["textQuery"] = query

            catalogues = self._client.betting.list_market_catalogue(
                filter=market_filter,
                max_results=min(limit, 1000),
                market_projection=["RUNNER_DESCRIPTION", "MARKET_START_TIME"],
            )

            markets = []
            for cat in (catalogues or []):
                # Get best prices
                yes_price = 0.0
                no_price = 0.0

                if hasattr(cat, "runners") and cat.runners:
                    for runner in cat.runners:
                        # First runner is typically the "yes" outcome
                        if hasattr(runner, "last_price_traded") and runner.last_price_traded:
                            decimal_odds = runner.last_price_traded
                            yes_price = 1.0 / decimal_odds if decimal_odds > 0 else 0.0
                            no_price = 1.0 - yes_price
                            break

                mcat = ""
                if hasattr(cat, "event_type") and cat.event_type:
                    mcat = cat.event_type.name.lower() if hasattr(cat.event_type, "name") else ""

                if category and category.lower() not in mcat:
                    continue

                markets.append(UnifiedMarket(
                    platform="betfair",
                    market_id=cat.market_id,
                    title=cat.market_name,
                    description=getattr(cat, "description", ""),
                    category=mcat,
                    yes_price=yes_price,
                    no_price=no_price,
                    volume=getattr(cat, "total_matched", 0.0) or 0.0,
                    close_date=str(cat.market_start_time) if hasattr(cat, "market_start_time") else None,
                    status="open",
                    raw_data={"market_id": cat.market_id, "name": cat.market_name},
                ))

                if len(markets) >= limit:
                    break

            return markets
        except Exception as e:
            logger.error("Betfair fetch_markets failed: %s", e)
            return []

    async def fetch_orderbook(self, market_id: str) -> dict:
        if not self._connected:
            return {"bids": [], "asks": []}
        try:
            books = self._client.betting.list_market_book(
                market_ids=[market_id],
                price_projection={"priceData": ["EX_BEST_OFFERS"]},
            )
            if not books:
                return {"bids": [], "asks": []}

            book = books[0]
            bids = []
            asks = []

            for runner in (book.runners or []):
                ex = runner.ex
                if ex:
                    for back in (ex.available_to_back or []):
                        prob = 1.0 / back.price if back.price > 0 else 0
                        bids.append([prob, back.size])
                    for lay in (ex.available_to_lay or []):
                        prob = 1.0 / lay.price if lay.price > 0 else 0
                        asks.append([prob, lay.size])

            return {"bids": bids, "asks": asks}
        except Exception as e:
            logger.error("Betfair fetch_orderbook failed: %s", e)
            return {"bids": [], "asks": []}

    async def place_order(
        self,
        market_id: str,
        side: str,
        quantity: int,
        price: float,
        order_type: str = "limit",
    ) -> UnifiedOrder:
        if self._dry_run:
            logger.info(
                "[DRY RUN] Betfair order: %s %d @ %.4f on %s",
                side, quantity, price, market_id,
            )
            return UnifiedOrder(
                platform="betfair",
                order_id=f"DRY-BF-{market_id[:8]}",
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
            # Convert probability back to decimal odds for Betfair
            decimal_odds = 1.0 / price if price > 0 else 1000.0
            bf_side = "BACK" if side == "yes" else "LAY"

            instructions = [{
                "orderType": "LIMIT",
                "selectionId": market_id,  # simplified
                "side": bf_side,
                "limitOrder": {
                    "size": quantity,
                    "price": round(decimal_odds, 2),
                    "persistenceType": "LAPSE",
                },
            }]

            result = self._client.betting.place_orders(
                market_id=market_id,
                instructions=instructions,
            )

            oid = ""
            status = "pending"
            if result and hasattr(result, "place_instruction_reports"):
                report = result.place_instruction_reports[0]
                oid = getattr(report, "bet_id", "")
                status = getattr(report, "status", "pending").lower()

            return UnifiedOrder(
                platform="betfair",
                order_id=str(oid),
                market_id=market_id,
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type,
                status=status,
                raw_data={"result": str(result)},
            )
        except Exception as e:
            logger.error("Betfair place_order failed: %s", e)
            return UnifiedOrder(
                platform="betfair",
                order_id="FAILED",
                market_id=market_id,
                side=side,
                quantity=quantity,
                price=price,
                status="failed",
            )

    async def cancel_order(self, order_id: str) -> bool:
        if self._dry_run:
            return True
        try:
            self._client.betting.cancel_orders(
                instructions=[{"betId": order_id}],
            )
            return True
        except Exception as e:
            logger.error("Betfair cancel_order failed: %s", e)
            return False

    async def cancel_all_orders(self) -> int:
        if self._dry_run:
            return 0
        try:
            result = self._client.betting.cancel_orders()
            return getattr(result, "cancel_instruction_reports_count", 0)
        except Exception:
            return 0

    async def fetch_positions(self) -> list[UnifiedPosition]:
        if not self._connected:
            return []
        try:
            orders = self._client.betting.list_current_orders()
            return [
                UnifiedPosition(
                    platform="betfair",
                    market_id=getattr(o, "market_id", ""),
                    market_title=getattr(o, "market_id", ""),
                    side="yes" if getattr(o, "side", "") == "BACK" else "no",
                    quantity=int(getattr(o, "size_matched", 0)),
                    avg_price=1.0 / getattr(o, "average_price_matched", 1) if getattr(o, "average_price_matched", 0) > 0 else 0,
                    raw_data={"order": str(o)},
                )
                for o in (orders.orders if orders else [])
            ]
        except Exception as e:
            logger.error("Betfair fetch_positions failed: %s", e)
            return []

    async def fetch_balance(self) -> PlatformBalance:
        if self._dry_run:
            return PlatformBalance(
                platform="betfair",
                available=Config.PAPER_STARTING_BALANCE,
                total=Config.PAPER_STARTING_BALANCE,
                currency="GBP",
            )
        try:
            funds = self._client.account.get_account_funds()
            return PlatformBalance(
                platform="betfair",
                available=funds.available_to_bet_balance or 0.0,
                total=(funds.available_to_bet_balance or 0.0) + (funds.exposure or 0.0),
                currency="GBP",
                raw_data={"funds": str(funds)},
            )
        except Exception as e:
            logger.error("Betfair fetch_balance failed: %s", e)
            return PlatformBalance(platform="betfair", available=0.0, total=0.0)
