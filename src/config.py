"""
TerminatorBot - System Configuration
All thresholds, API settings, and strategy parameters.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── System Settings ──────────────────────────────────────────────
    TRADING_MODE = os.getenv("TRADING_MODE", "PAPER")  # PAPER or LIVE
    SCAN_INTERVAL_SECONDS = 60       # 1 minute between scan cycles
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # ── Platform Credentials (pmxt) ──────────────────────────────────
    KALSHI_API_KEY = os.getenv("KALSHI_API_KEY", "")
    KALSHI_PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")

    POLYMARKET_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
    POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY", "")
    POLYMARKET_API_SECRET = os.getenv("POLYMARKET_API_SECRET", "")
    POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE", "")

    LIMITLESS_API_KEY = os.getenv("LIMITLESS_API_KEY", "")

    # ── Betfair Credentials ──────────────────────────────────────────
    BETFAIR_USERNAME = os.getenv("BETFAIR_USERNAME", "")
    BETFAIR_PASSWORD = os.getenv("BETFAIR_PASSWORD", "")
    BETFAIR_APP_KEY = os.getenv("BETFAIR_APP_KEY", "")
    BETFAIR_CERT_PATH = os.getenv("BETFAIR_CERT_PATH", "")

    # ── Smarkets Credentials ─────────────────────────────────────────
    SMARKETS_API_KEY = os.getenv("SMARKETS_API_KEY", "")

    # ── Optional APIs ────────────────────────────────────────────────
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

    # ── Scanner Settings ─────────────────────────────────────────────
    ARB_MIN_EDGE_PCT = 0.02          # 2% minimum arb edge after fees
    ARB_FEE_BUFFER = 0.007           # 0.7% estimated fees + slippage
    ARB_MIN_LIQUIDITY = 100          # Minimum contracts on each side

    DUMB_BET_MAX_PROB = 0.10         # 10% max implied prob for dumb bets
    DUMB_BET_MIN_VOLUME = 500        # Minimum contracts traded
    DUMB_BET_EXCLUDE_KEYWORDS = [    # Skip gamified / subjective markets
        "mention", "word", "parlay", "weather forecast",
    ]

    ALPHA_EDGE_THRESHOLD = 0.05      # 5% minimum edge for alpha trades
    ALPHA_CONFIDENCE_THRESHOLD = 0.70

    CONTRARIAN_CONSENSUS_THRESHOLD = 0.85  # 85%+ one-sided = contrarian signal
    CONTRARIAN_OVERCONFIDENCE_BIAS = 0.15  # 15% bias adjustment

    # ── Risk Management ──────────────────────────────────────────────
    MAX_DRAWDOWN_PCT = 0.05          # 5% daily drawdown = kill switch
    MAX_POSITION_SIZE = 0.02         # 2% of equity per standard trade
    HIGH_CONVICTION_SIZE = 0.05      # 5% for high-conviction trades
    MAX_CONSECUTIVE_LOSSES = 3       # Disable scanner after 3 losses
    LOCKOUT_HOURS = 24               # Hours to lock out after circuit break
    HOURLY_LOSS_CAP_PCT = 0.03       # 3% hourly loss cap

    # ── Kelly Criterion ──────────────────────────────────────────────
    KELLY_FRACTION = 0.50            # Half Kelly (default safety)
    KELLY_MAX_FRACTION = 0.75        # Max Kelly fraction for aggressive
    KELLY_ARB_FRACTION = 0.75        # Arb-specific (higher since lower risk)
    KELLY_DUMB_BET_FRACTION = 0.60   # Dumb bets (high confidence)
    CORRELATION_PENALTY = 0.15       # Reduce size per correlated open bet

    # ── Capital Allocation ───────────────────────────────────────────
    MAX_PLATFORM_ALLOCATION = 0.40   # No more than 40% on one platform
    REBALANCE_THRESHOLD = 0.10       # Rebalance when 10% skewed
    PAPER_STARTING_BALANCE = 10_000  # Starting balance per platform (paper)

    # ── Market Matching ──────────────────────────────────────────────
    FUZZY_MATCH_THRESHOLD = 85       # rapidfuzz score 0-100
    FUZZY_LLM_ZONE_LOW = 70          # Below this = auto-reject
    FUZZY_LLM_ZONE_HIGH = 85         # Above this = auto-accept
    MATCH_MAX_DATE_DIFF_DAYS = 7     # Max close-date difference

    # ── Platform Fees (approximate) ──────────────────────────────────
    PLATFORM_FEES = {
        "kalshi": 0.003,             # ~0.3% average
        "polymarket": 0.001,         # ~0.1% (maker often free)
        "limitless": 0.002,
        "betfair": 0.05,             # 5% commission on profits
        "smarkets": 0.02,            # 2% commission
        "manifold": 0.0,             # Play money
    }
