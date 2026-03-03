"""
TerminatorBot - Master Controller

The Terminator. Global prediction market exploitation engine.

Usage:
    python src/main.py --status          # Show platform status and balances
    python src/main.py --match-report    # Show cross-platform matched markets
    python src/main.py --scan dumb_bet   # Run a single scan cycle
    python src/main.py --scan arb        # Run arbitrage scan
    python src/main.py --scan alpha      # Run ML alpha scan
    python src/main.py --scan all        # Run all scanners
    python src/main.py --continuous      # 24/7 continuous scanning loop
    python src/main.py --stream          # Real-time WebSocket/polling mode
    python src/main.py --train           # Train ML alpha model
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time

# Ensure src/ is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from platforms.platform_registry import PlatformRegistry
from matching.fuzzy_matcher import MarketMatcher
from matching.llm_verifier import LLMMatchVerifier
from matching.market_graph import MarketGraph
from scanners.base_scanner import Opportunity
from scanners.dumb_bet_scanner import DumbBetScanner
from scanners.contrarian_scanner import ContrarianScanner
from scanners.arbitrage_scanner import ArbitrageScanner
from scanners.alpha_scanner import AlphaScanner
from core.circuit_breaker import PortfolioCircuitBreaker
from core.position_sizer import PredictionMarketSizer
from core.rebalancer import CrossPlatformRebalancer
from execution.dry_run_engine import DryRunEngine
from execution.order_manager import OrderManager
from execution.arb_executor import ArbExecutor
from streams.event_bus import EventBus
from streams.price_aggregator import PriceAggregator
from streams.stream_manager import StreamManager
from data.market_cache import MarketCache
from ml.feature_engine import FeatureEngine
from ml.alpha_model import AlphaModel
from ml.sentiment_nlp import SentimentScorer
from utils.logger import TerminatorLogger
from utils.alerts import AlertManager

from colorama import Fore, Style, init as colorama_init
from tabulate import tabulate

colorama_init(autoreset=True)

logger = logging.getLogger("terminator")


BANNER = f"""{Fore.RED}{Style.BRIGHT}
  ████████╗███████╗██████╗ ███╗   ███╗██╗███╗   ██╗ █████╗ ████████╗ ██████╗ ██████╗
  ╚══██╔══╝██╔════╝██╔══██╗████╗ ████║██║████╗  ██║██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗
     ██║   █████╗  ██████╔╝██╔████╔██║██║██╔██╗ ██║███████║   ██║   ██║   ██║██████╔╝
     ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║██║██║╚██╗██║██╔══██║   ██║   ██║   ██║██╔══██╗
     ██║   ███████╗██║  ██║██║ ╚═╝ ██║██║██║ ╚████║██║  ██║   ██║   ╚██████╔╝██║  ██║
     ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
  {Fore.CYAN}Global Prediction Market Exploitation System{Style.RESET_ALL}
"""


class TerminatorController:
    """
    Master controller integrating all TerminatorBot subsystems.

    Modeled after Project_Vault's VaultController.
    """

    def __init__(self):
        self._is_paper = Config.TRADING_MODE.upper() != "LIVE"

        # Platform layer
        self._registry = PlatformRegistry(dry_run=self._is_paper)

        # Matching engine
        self._llm_verifier = LLMMatchVerifier() if Config.OPENAI_API_KEY else None
        self._matcher = MarketMatcher(llm_verifier=self._llm_verifier)
        self._market_graph = MarketGraph(matcher=self._matcher)

        # Risk infrastructure
        starting_balance = Config.PAPER_STARTING_BALANCE if self._is_paper else 0
        self._circuit_breaker = PortfolioCircuitBreaker(starting_balance=starting_balance)
        self._rebalancer = CrossPlatformRebalancer()

        # Dry run engine
        self._dry_run = DryRunEngine() if self._is_paper else None

        # ML components
        self._sentiment = SentimentScorer()
        self._features = FeatureEngine(sentiment_scorer=self._sentiment)
        self._alpha_model = AlphaModel(feature_engine=self._features)
        self._alpha_model.load()  # Load if trained model exists

        # Scanners
        self._scanners = {
            "dumb_bet": DumbBetScanner(),
            "contrarian": ContrarianScanner(),
            "arb": ArbitrageScanner(market_graph=self._market_graph),
            "alpha": AlphaScanner(
                alpha_model=self._alpha_model if self._alpha_model.is_loaded else None,
                sentiment_scorer=self._sentiment if self._sentiment.enabled else None,
            ),
        }

        # Execution
        self._trade_logger = TerminatorLogger()
        self._order_manager = OrderManager(
            registry=self._registry,
            circuit_breaker=self._circuit_breaker,
            trade_logger=self._trade_logger,
            dry_run_engine=self._dry_run,
        )
        self._arb_executor = ArbExecutor(
            registry=self._registry,
            trade_logger=self._trade_logger,
            dry_run_engine=self._dry_run,
        )

        # Streaming
        self._event_bus = EventBus()
        self._price_aggregator = PriceAggregator(event_bus=self._event_bus)
        self._stream_manager = StreamManager(
            registry=self._registry,
            aggregator=self._price_aggregator,
            event_bus=self._event_bus,
        )

        # Data
        self._cache = MarketCache()

        # State
        self._cycle_count = 0

    async def initialize(self) -> bool:
        """Initialize all platforms and subsystems."""
        sys.stderr.write(BANNER)

        mode_str = f"{Fore.YELLOW}PAPER{Style.RESET_ALL}" if self._is_paper else f"{Fore.RED}LIVE{Style.RESET_ALL}"
        AlertManager.info(f"Trading mode: {mode_str}")

        # Initialize platforms
        results = await self._registry.initialize()
        active = sum(1 for v in results.values() if v)

        if active == 0:
            AlertManager.critical("No platforms connected! Check .env credentials.")
            return False

        for name, ok in results.items():
            status = f"{Fore.GREEN}OK{Style.RESET_ALL}" if ok else f"{Fore.RED}FAIL{Style.RESET_ALL}"
            AlertManager.info(f"  {name:<15s} [{status}]")

        # Update circuit breaker with real balance if live
        if not self._is_paper:
            equity = await self._registry.get_total_equity()
            self._circuit_breaker.starting_balance = equity
            self._circuit_breaker._daily_high_water = equity

        AlertManager.success(f"{active}/{len(results)} platforms online")
        return True

    # ── Commands ──────────────────────────────────────────────────────

    async def cmd_status(self) -> None:
        """Show platform status and balances."""
        balances = await self._registry.fetch_all_balances()
        if not balances:
            AlertManager.warning("No platform balances available.")
            return

        rows = []
        total = 0.0
        for name, bal in balances.items():
            rows.append([name, f"${bal.available:,.2f}", f"${bal.total:,.2f}", bal.currency])
            total += bal.total

        print(f"\n{Fore.CYAN}Platform Balances:{Style.RESET_ALL}")
        print(tabulate(rows, headers=["Platform", "Available", "Total", "Currency"], tablefmt="simple"))
        print(f"\n  Total Equity: {Fore.GREEN}${total:,.2f}{Style.RESET_ALL}")

        # Circuit breaker status
        health = self._circuit_breaker.check_health(total)
        mode_color = {
            "OPERATIONAL": Fore.GREEN,
            "WARNING": Fore.YELLOW,
            "LOCKOUT": Fore.RED,
            "SENTRY": Fore.RED,
        }.get(health.system_mode.value, Fore.WHITE)
        print(f"  System Mode:  {mode_color}{health.system_mode.value}{Style.RESET_ALL}")
        print(f"  Drawdown:     {health.current_drawdown_pct:.2%}")

        if self._is_paper and self._dry_run:
            summary = self._dry_run.summary()
            print(f"\n{Fore.YELLOW}Paper Trading:{Style.RESET_ALL}")
            print(f"  Equity:     ${summary['total_equity']:,.2f}")
            print(f"  P&L:        ${summary['total_pnl']:,.2f}")
            print(f"  Trades:     {summary['trade_count']}")
            print(f"  Positions:  {summary['open_positions']}")

    async def cmd_match_report(self) -> None:
        """Show cross-platform market matches."""
        AlertManager.info("Fetching markets from all platforms...")
        markets = await self._registry.fetch_all_markets()
        AlertManager.info(f"Fetched {len(markets)} markets total")

        self._market_graph.refresh(markets)
        pairs = self._market_graph.get_all_pairs()
        arb_pairs = self._market_graph.get_arb_opportunities()

        print(f"\n{Fore.CYAN}Market Match Report:{Style.RESET_ALL}")
        print(f"  Total matched pairs: {len(pairs)}")
        print(f"  Pairs with arb:      {len(arb_pairs)}")

        if arb_pairs:
            print(f"\n{Fore.GREEN}Arb Opportunities:{Style.RESET_ALL}")
            rows = []
            for p in arb_pairs[:20]:
                rows.append([
                    f"{p.market_a.platform}+{p.market_b.platform}",
                    p.market_a.title[:45],
                    f"{p.similarity_score:.0f}",
                    f"${p.combined_yes_cost:.4f}",
                    f"{p.arb_edge:.2%}",
                    "LLM" if p.llm_verified else "Fuzzy",
                ])
            print(tabulate(
                rows,
                headers=["Platforms", "Market", "Sim", "Cost", "Edge", "Verify"],
                tablefmt="simple",
            ))

    async def cmd_scan(self, scanner_type: str, execute: bool = False) -> None:
        """Run scanners and optionally execute opportunities."""
        AlertManager.info("Fetching markets...")
        markets = await self._registry.fetch_all_markets()
        self._cache.put_batch(markets)
        AlertManager.info(f"Fetched {len(markets)} markets from {len(self._registry.platform_names())} platforms")

        scanners_to_run = []
        if scanner_type == "all":
            scanners_to_run = list(self._scanners.values())
        elif scanner_type in self._scanners:
            scanners_to_run = [self._scanners[scanner_type]]
        else:
            AlertManager.critical(f"Unknown scanner: {scanner_type}")
            return

        all_opps: list[Opportunity] = []
        for scanner in scanners_to_run:
            if not self._circuit_breaker.is_scanner_enabled(scanner.scanner_name):
                AlertManager.warning(f"Scanner '{scanner.scanner_name}' disabled by circuit breaker")
                continue

            opps = await scanner.scan(markets)
            all_opps.extend(opps)

            for opp in opps:
                AlertManager.opportunity_found(
                    scanner_type=opp.scanner_type,
                    platform=opp.platform,
                    title=opp.market_title,
                    edge=opp.edge_estimate,
                    side=opp.side,
                )
                self._trade_logger.log_opportunity(
                    scanner_type=opp.scanner_type,
                    platform=opp.platform,
                    market_id=opp.market_id,
                    market_title=opp.market_title,
                    side=opp.side,
                    edge=opp.edge_estimate,
                    confidence=opp.confidence,
                    reasoning=opp.reasoning,
                )

        # Sort all opportunities by EV
        all_opps.sort(key=lambda o: o.expected_value, reverse=True)

        print(f"\n{Fore.CYAN}Scan Results:{Style.RESET_ALL}")
        if not all_opps:
            print("  No opportunities found.")
            return

        rows = []
        for opp in all_opps[:30]:
            rows.append([
                opp.scanner_type,
                opp.platform,
                opp.side.upper(),
                f"${opp.price:.4f}",
                f"{opp.edge_estimate:.2%}",
                f"{opp.confidence:.2f}",
                f"{opp.expected_value:.4f}",
                opp.market_title[:40],
            ])
        print(tabulate(
            rows,
            headers=["Scanner", "Platform", "Side", "Price", "Edge", "Conf", "EV", "Market"],
            tablefmt="simple",
        ))

        if execute:
            await self._execute_opportunities(all_opps)

    async def _execute_opportunities(self, opps: list[Opportunity]) -> None:
        """Execute top opportunities through the order manager."""
        equity = await self._get_equity()
        trades_executed = 0

        for opp in opps[:10]:  # Cap at 10 per cycle
            if opp.scanner_type == "arb":
                result = await self._arb_executor.execute_arb(opp, equity)
                if result.success:
                    trades_executed += 1
            else:
                order = await self._order_manager.execute_opportunity(opp, equity)
                if order is not None:
                    trades_executed += 1

        AlertManager.info(f"Executed {trades_executed}/{len(opps[:10])} opportunities")

    async def cmd_continuous(self) -> None:
        """Run continuous scanning loop."""
        AlertManager.info(f"Starting continuous mode (interval={Config.SCAN_INTERVAL_SECONDS}s)")

        try:
            while True:
                self._cycle_count += 1
                cycle_start = time.time()

                AlertManager.scan_cycle_start(
                    self._cycle_count,
                    len(self._registry.platform_names()),
                )

                # Health check
                equity = await self._get_equity()
                health = self._circuit_breaker.check_health(equity)

                if not health.is_healthy:
                    AlertManager.critical(f"Circuit breaker: {health.reason}")
                    if health.system_mode.value == "LOCKOUT":
                        AlertManager.circuit_breaker_alert(health.current_drawdown_pct)
                        AlertManager.info("Waiting for lockout to expire...")
                        await asyncio.sleep(300)
                        continue
                    # SENTRY mode: wait an hour
                    await asyncio.sleep(3600)
                    continue

                if health.current_drawdown_pct > 0.025:
                    AlertManager.drawdown_warning(health.current_drawdown_pct)

                # Fetch all markets
                markets = await self._registry.fetch_all_markets()
                self._cache.put_batch(markets)

                # Run all scanners concurrently
                scan_tasks = []
                for scanner in self._scanners.values():
                    if self._circuit_breaker.is_scanner_enabled(scanner.scanner_name):
                        scan_tasks.append(scanner.scan(markets))

                results = await asyncio.gather(*scan_tasks, return_exceptions=True)

                all_opps = []
                for result in results:
                    if isinstance(result, Exception):
                        logger.error("Scanner error: %s", result)
                    else:
                        all_opps.extend(result)

                all_opps.sort(key=lambda o: o.expected_value, reverse=True)

                # Log and alert
                for opp in all_opps:
                    AlertManager.opportunity_found(
                        scanner_type=opp.scanner_type,
                        platform=opp.platform,
                        title=opp.market_title,
                        edge=opp.edge_estimate,
                        side=opp.side,
                    )

                # Execute top opportunities
                trades_executed = 0
                if all_opps:
                    await self._execute_opportunities(all_opps)
                    trades_executed = min(len(all_opps), 10)

                # Rebalance check
                balances = await self._registry.fetch_all_balances()
                report = self._rebalancer.analyze(balances)
                if report and hasattr(report, "needs_rebalance") and report.needs_rebalance:
                    AlertManager.warning(f"Rebalance needed: {report}")

                # Cycle summary
                duration_ms = int((time.time() - cycle_start) * 1000)
                AlertManager.scan_cycle_end(
                    self._cycle_count, len(all_opps), trades_executed, duration_ms,
                )

                await asyncio.sleep(Config.SCAN_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            AlertManager.info("Continuous mode stopped by user.")

    async def cmd_train(self) -> None:
        """Train the alpha model on synthetic data (demo) or resolved markets (live)."""
        from data.historical_loader import HistoricalLoader
        import numpy as np

        AlertManager.info("Training alpha model...")

        loader = HistoricalLoader()

        # Try to load real resolved data first
        records, labels = loader.load_training_data()

        if len(records) < 50:
            AlertManager.info(
                f"Only {len(records)} resolved markets in DB — generating synthetic training data..."
            )
            records, labels = self._generate_synthetic_training_data(n_samples=2000)

        if not records:
            AlertManager.critical("No training data available.")
            return

        # Convert records to UnifiedMarket objects for feature extraction
        from platforms.base import UnifiedMarket

        markets = []
        for r in records:
            markets.append(UnifiedMarket(
                platform=r.get("platform", "synthetic"),
                market_id=r.get("market_id", ""),
                title=r.get("title", ""),
                category=r.get("category", ""),
                yes_price=r.get("yes_price", 0.5),
                no_price=r.get("no_price", 0.5),
                volume=r.get("volume", 1000),
                liquidity=r.get("liquidity", 500),
                open_interest=r.get("open_interest", 200),
                close_date=r.get("close_date", None),
            ))

        # Extract features
        X, valid_indices = self._features.extract_batch(markets)
        y = np.array([labels[i] for i in valid_indices])

        AlertManager.info(f"Training on {X.shape[0]} samples with {X.shape[1]} features")

        metrics = self._alpha_model.train(X, y, save=True)

        if "error" in metrics:
            AlertManager.critical(f"Training failed: {metrics['error']}")
            return

        AlertManager.success(
            f"Model trained! Accuracy: {metrics['accuracy_mean']:.3f} "
            f"(+/- {metrics['accuracy_std']:.3f}) on {metrics['n_samples']} samples"
        )

        # Show feature importance
        print(f"\n{Fore.CYAN}Feature Importance:{Style.RESET_ALL}")
        importance = sorted(
            metrics["feature_importance"].items(),
            key=lambda x: x[1],
            reverse=True,
        )
        for name, score in importance:
            bar = "#" * int(score * 50)
            print(f"  {name:<25s} {score:.4f} {bar}")

        # Reload the model in the alpha scanner
        self._alpha_model.load()
        self._scanners["alpha"] = AlphaScanner(
            alpha_model=self._alpha_model if self._alpha_model.is_loaded else None,
            sentiment_scorer=self._sentiment if self._sentiment.enabled else None,
        )
        AlertManager.success("Alpha scanner reloaded with trained model.")

    def _generate_synthetic_training_data(
        self, n_samples: int = 2000
    ) -> tuple[list[dict], list[int]]:
        """Generate synthetic training data with realistic market patterns."""
        import random
        from datetime import datetime, timedelta, timezone

        categories = ["politics", "crypto", "economics", "sports", "science", "tech"]
        templates = {
            "politics": [
                "Will {candidate} win the election?",
                "Will the {party} pass the {bill} bill?",
                "Will {leader} approval exceed {pct}%?",
            ],
            "crypto": [
                "Will Bitcoin exceed ${price}K by {month}?",
                "Will Ethereum exceed ${price} by {month}?",
                "Will a crypto ETF be approved in {year}?",
            ],
            "economics": [
                "Will GDP growth exceed {pct}% in Q{q}?",
                "Will the Fed cut rates in {month}?",
                "Will inflation fall below {pct}%?",
            ],
            "sports": [
                "Will {team} win the championship?",
                "Will {team} reach the semifinals?",
            ],
            "science": [
                "Will SpaceX launch to Mars in {year}?",
                "Will a major earthquake hit {region}?",
                "Will global temperature set record in {year}?",
            ],
            "tech": [
                "Will {company} release {product} in {year}?",
                "Will {company} be banned in the US?",
            ],
        }

        candidates = ["Smith", "Johnson", "Williams", "Davis", "Brown"]
        parties = ["Democrats", "Republicans"]
        bills = ["infrastructure", "healthcare", "defense", "education"]
        leaders = ["Biden", "Trump", "DeSantis"]
        teams = ["Lakers", "Warriors", "Chiefs", "Eagles", "Argentina", "Brazil"]
        companies = ["Apple", "Google", "Meta", "TikTok", "OpenAI"]
        products = ["AR glasses", "smart ring", "AI chip", "new OS"]
        regions = ["California", "Japan", "Turkey", "Alaska"]
        months = ["March", "April", "May", "June", "July"]

        records = []
        labels = []
        now = datetime.now(timezone.utc)

        for i in range(n_samples):
            cat = random.choice(categories)
            template = random.choice(templates[cat])

            title = template
            title = title.replace("{candidate}", random.choice(candidates))
            title = title.replace("{party}", random.choice(parties))
            title = title.replace("{bill}", random.choice(bills))
            title = title.replace("{leader}", random.choice(leaders))
            title = title.replace("{team}", random.choice(teams))
            title = title.replace("{company}", random.choice(companies))
            title = title.replace("{product}", random.choice(products))
            title = title.replace("{region}", random.choice(regions))
            title = title.replace("{month}", random.choice(months))
            title = title.replace("{year}", str(random.choice([2025, 2026])))
            title = title.replace("{price}", str(random.choice([50, 80, 100, 150])))
            title = title.replace("{pct}", str(random.randint(2, 60)))
            title = title.replace("{q}", str(random.randint(1, 4)))

            # Market price (what the market thinks)
            yes_price = random.uniform(0.05, 0.95)

            # Outcome correlates with price but with noise
            noise = random.gauss(0, 0.15)
            true_prob = max(0.01, min(0.99, yes_price + noise))
            outcome = 1 if random.random() < true_prob else 0

            volume = random.randint(100, 100000)
            close_days = random.randint(-90, -1)

            records.append({
                "platform": random.choice(["kalshi", "polymarket", "betfair"]),
                "market_id": f"synth-{i:05d}",
                "title": title,
                "category": cat,
                "yes_price": round(yes_price, 4),
                "no_price": round(1 - yes_price, 4),
                "volume": volume,
                "liquidity": random.randint(50, 20000),
                "open_interest": random.randint(50, 10000),
                "close_date": (now + timedelta(days=close_days)).isoformat(),
            })
            labels.append(outcome)

        AlertManager.info(
            f"Generated {n_samples} synthetic markets "
            f"({sum(labels)} YES / {n_samples - sum(labels)} NO)"
        )
        return records, labels

    async def cmd_stream(self) -> None:
        """Start real-time streaming mode."""
        AlertManager.info("Starting real-time streaming mode...")
        await self._stream_manager.start()

        try:
            while True:
                active = self._stream_manager.active_streams
                AlertManager.info(f"Active streams: {', '.join(active) or 'none'}")
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            await self._stream_manager.stop()
            AlertManager.info("Streaming stopped.")

    async def _get_equity(self) -> float:
        """Get total equity (paper or live)."""
        # Always use platform balances as the source of truth
        return await self._registry.get_total_equity()

    async def shutdown(self) -> None:
        """Clean shutdown."""
        await self._stream_manager.stop()
        self._cache.close()
        self._trade_logger.log_system_event(
            "shutdown", "TerminatorBot shutting down", severity="INFO",
        )
        AlertManager.info("Terminator offline.")


def setup_logging() -> None:
    """Configure logging."""
    level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Quiet noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TerminatorBot - Global Prediction Market Exploitation System",
    )
    parser.add_argument("--status", action="store_true", help="Show platform status and balances")
    parser.add_argument("--match-report", action="store_true", help="Show cross-platform market matches")
    parser.add_argument("--scan", type=str, help="Run scanner (dumb_bet|arb|alpha|contrarian|all)")
    parser.add_argument("--execute", action="store_true", help="Execute discovered opportunities")
    parser.add_argument("--continuous", action="store_true", help="Run 24/7 continuous scanning")
    parser.add_argument("--stream", action="store_true", help="Run real-time streaming mode")
    parser.add_argument("--train", action="store_true", help="Train ML alpha prediction model")
    return parser.parse_args()


async def main() -> None:
    setup_logging()
    args = parse_args()

    controller = TerminatorController()
    if not await controller.initialize():
        sys.exit(1)

    try:
        if args.status:
            await controller.cmd_status()
        elif args.match_report:
            await controller.cmd_match_report()
        elif args.scan:
            await controller.cmd_scan(args.scan, execute=args.execute)
        elif args.continuous:
            await controller.cmd_continuous()
        elif args.train:
            await controller.cmd_train()
        elif args.stream:
            await controller.cmd_stream()
        else:
            await controller.cmd_status()
    finally:
        await controller.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
