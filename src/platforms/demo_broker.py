"""
TerminatorBot - Demo Broker

Generates realistic mock market data for paper trading when no
real platform credentials are configured. Simulates markets
across Kalshi and Polymarket with varied categories and prices.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timedelta, timezone

from platforms.base import (
    PlatformBroker,
    UnifiedMarket,
    UnifiedOrder,
    UnifiedPosition,
    PlatformBalance,
)
from config import Config

logger = logging.getLogger(__name__)

# Realistic market templates
_DEMO_MARKETS = [
    # Politics
    ("Will {candidate} win the 2026 midterm election?", "politics", (0.30, 0.70)),
    ("Will the US pass infrastructure bill by Q3 2026?", "politics", (0.55, 0.65)),
    ("Will Trump approval rating exceed 50% in {month}?", "politics", (0.25, 0.40)),
    ("Will Democrats win the Senate in 2026?", "politics", (0.40, 0.55)),
    ("Will the US impose new tariffs on China in 2026?", "politics", (0.50, 0.70)),
    # Crypto
    ("Will Bitcoin exceed $100,000 by end of 2026?", "crypto", (0.55, 0.75)),
    ("Will Ethereum exceed $5,000 by end of 2026?", "crypto", (0.35, 0.55)),
    ("Will Bitcoin drop below $50,000 in 2026?", "crypto", (0.10, 0.25)),
    ("Will a new crypto ETF be approved in 2026?", "crypto", (0.60, 0.80)),
    # Economics
    ("Will US GDP growth exceed 3% in Q2 2026?", "economics", (0.30, 0.50)),
    ("Will the Fed cut rates in {month} 2026?", "economics", (0.40, 0.65)),
    ("Will US inflation fall below 2.5% by mid-2026?", "economics", (0.35, 0.55)),
    ("Will unemployment rise above 5% in 2026?", "economics", (0.15, 0.30)),
    # Sports
    ("Will the US win the 2026 World Cup?", "sports", (0.05, 0.15)),
    ("Will Argentina reach World Cup 2026 semifinals?", "sports", (0.50, 0.70)),
    ("Will the Lakers win the 2026 NBA Championship?", "sports", (0.08, 0.18)),
    # Science
    ("Will SpaceX launch Starship to Mars in 2026?", "science", (0.10, 0.25)),
    ("Will a major earthquake (>7.0) hit California in 2026?", "science", (0.08, 0.20)),
    ("Will aliens be confirmed by a government in 2026?", "science", (0.01, 0.03)),
    ("Will global temperature set a new record in 2026?", "science", (0.60, 0.80)),
    # Tech
    ("Will Apple release AR glasses in 2026?", "tech", (0.30, 0.50)),
    ("Will OpenAI release GPT-5 by mid-2026?", "tech", (0.55, 0.75)),
    ("Will TikTok be banned in the US in 2026?", "tech", (0.15, 0.35)),
]

_CANDIDATES = ["Smith", "Johnson", "Williams", "Brown", "Davis"]
_MONTHS = ["March", "April", "May", "June", "July", "August"]


class DemoBroker(PlatformBroker):
    """
    Mock broker that generates realistic market data for paper trading.
    """

    def __init__(self, platform_name: str = "demo_kalshi"):
        self._name = platform_name
        self._balance = Config.PAPER_STARTING_BALANCE
        self._markets: list[UnifiedMarket] = []
        self._orders: list[UnifiedOrder] = []
        self._positions: list[UnifiedPosition] = []
        self._connected = False

    @property
    def platform_name(self) -> str:
        return self._name

    @property
    def is_dry_run(self) -> bool:
        return True

    async def connect(self) -> bool:
        self._markets = self._generate_markets()
        self._connected = True
        logger.info("DemoBroker '%s' connected with %d mock markets", self._name, len(self._markets))
        return True

    async def fetch_markets(self, category=None, status="open", limit=500, query=None):
        markets = self._markets
        if category:
            markets = [m for m in markets if m.category == category]
        if query:
            q = query.lower()
            markets = [m for m in markets if q in m.title.lower()]
        # Simulate slight price drift each fetch
        drifted = []
        for m in markets[:limit]:
            drift = random.uniform(-0.02, 0.02)
            new_yes = max(0.01, min(0.99, m.yes_price + drift))
            drifted.append(UnifiedMarket(
                platform=m.platform,
                market_id=m.market_id,
                title=m.title,
                description=m.description,
                category=m.category,
                yes_price=round(new_yes, 4),
                no_price=round(1 - new_yes, 4),
                volume=m.volume + random.randint(0, 100),
                liquidity=m.liquidity,
                open_interest=m.open_interest,
                close_date=m.close_date,
                status="open",
                last_updated=datetime.now(timezone.utc).isoformat(),
            ))
        return drifted

    async def fetch_orderbook(self, market_id: str):
        return {"bids": [[0.50, 100]], "asks": [[0.51, 100]]}

    async def place_order(self, market_id, side, quantity, price, order_type="limit"):
        order_id = f"demo_{uuid.uuid4().hex[:8]}"
        order = UnifiedOrder(
            platform=self._name,
            order_id=order_id,
            market_id=market_id,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            status="filled",
            filled_quantity=quantity,
            filled_price=price,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._orders.append(order)
        return order

    async def cancel_order(self, order_id: str):
        return True

    async def cancel_all_orders(self):
        return 0

    async def fetch_positions(self):
        return self._positions

    async def fetch_balance(self):
        return PlatformBalance(
            platform=self._name,
            available=self._balance,
            total=self._balance,
        )

    def _generate_markets(self) -> list[UnifiedMarket]:
        """Generate a set of realistic mock markets."""
        markets = []
        now = datetime.now(timezone.utc)

        for i, (template, category, price_range) in enumerate(_DEMO_MARKETS):
            title = template
            if "{candidate}" in title:
                title = title.replace("{candidate}", random.choice(_CANDIDATES))
            if "{month}" in title:
                title = title.replace("{month}", random.choice(_MONTHS))

            yes_price = round(random.uniform(price_range[0], price_range[1]), 4)
            close_days = random.randint(14, 300)

            markets.append(UnifiedMarket(
                platform=self._name,
                market_id=f"{self._name}-{i:03d}",
                title=title,
                category=category,
                yes_price=yes_price,
                no_price=round(1 - yes_price, 4),
                volume=random.randint(500, 50000),
                liquidity=random.randint(200, 10000),
                open_interest=random.randint(100, 5000),
                close_date=(now + timedelta(days=close_days)).isoformat(),
                status="open",
                last_updated=now.isoformat(),
            ))

        return markets
