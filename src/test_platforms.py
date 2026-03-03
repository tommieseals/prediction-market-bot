#!/usr/bin/env python3
"""
TerminatorBot Platform Integration Tests

Tests all broker connections:
- Demo broker (paper trading)
- Kalshi (via pmxt)
- Platform registry routing
"""

import asyncio
import sys
import os
import logging

# Fix Windows encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Setup logging
logging.basicConfig(level=logging.WARNING)


async def test_demo_broker():
    """Test demo broker for paper trading."""
    print("\n[TEST 1] Demo Broker (Paper Trading)")
    print("-" * 50)
    
    from platforms.demo_broker import DemoBroker
    
    demo = DemoBroker(platform_name="demo_kalshi")
    
    # Connect
    connected = await demo.connect()
    assert connected, "Failed to connect demo broker"
    print(f"  Connected: {connected}")
    
    # Balance
    balance = await demo.fetch_balance()
    assert balance.available == 10000, f"Expected $10000, got ${balance.available}"
    print(f"  Balance: ${balance.available:,.2f} {balance.currency}")
    
    # Markets
    markets = await demo.fetch_markets(limit=5)
    assert len(markets) == 5, f"Expected 5 markets, got {len(markets)}"
    print(f"  Markets: {len(markets)} fetched")
    
    # Order
    order = await demo.place_order(
        market_id=markets[0].market_id,
        side="yes",
        quantity=10,
        price=0.50,
    )
    assert order.status == "filled", f"Order not filled: {order.status}"
    print(f"  Order: {order.order_id} ({order.status})")
    
    print("  [PASS] Demo broker working")
    return True


async def test_kalshi_broker():
    """Test Kalshi broker via pmxt."""
    print("\n[TEST 2] Kalshi Broker (via pmxt)")
    print("-" * 50)
    
    from config import Config
    from platforms.pmxt_broker import create_kalshi_broker
    
    if not Config.KALSHI_API_KEY:
        print("  [SKIP] No Kalshi API key configured")
        return True
    
    print(f"  API Key: ***{Config.KALSHI_API_KEY[-4:]}")
    
    # Test dry run mode
    broker = create_kalshi_broker(dry_run=True)
    connected = await broker.connect()
    assert connected, f"Failed to connect: {broker.last_error}"
    print(f"  Connected: {connected}")
    
    # Fetch markets
    markets = await broker.fetch_markets(limit=5)
    assert len(markets) > 0, "No markets fetched"
    print(f"  Markets: {len(markets)} fetched")
    
    for m in markets[:2]:
        print(f"    - {m.title[:40]}... ({m.yes_price:.1%})")
    
    # Balance (paper mode)
    balance = await broker.fetch_balance()
    print(f"  Balance: ${balance.available:,.2f} {balance.currency}")
    
    # Test order (dry run)
    order = await broker.place_order(
        market_id=markets[0].market_id,
        side="yes",
        quantity=10,
        price=markets[0].yes_price,
    )
    print(f"  Order (dry): {order.order_id} ({order.status})")
    
    print("  [PASS] Kalshi broker working")
    return True


async def test_platform_registry():
    """Test platform registry routing."""
    print("\n[TEST 3] Platform Registry")
    print("-" * 50)
    
    from platforms.platform_registry import PlatformRegistry
    
    registry = PlatformRegistry(dry_run=True)
    results = await registry.initialize()
    
    print(f"  Initialization results:")
    for platform, success in results.items():
        status = "OK" if success else "FAIL"
        print(f"    [{status}] {platform}")
    
    # Check active platforms
    active = registry.platform_names()
    print(f"  Active platforms: {active}")
    assert len(active) > 0, "No platforms active"
    
    # Fetch all markets
    markets = await registry.fetch_all_markets(limit_per_platform=3)
    print(f"  Total markets: {len(markets)}")
    
    # Fetch all balances
    balances = await registry.fetch_all_balances()
    total_equity = await registry.get_total_equity()
    print(f"  Total equity: ${total_equity:,.2f}")
    
    # Health check
    health = await registry.health_check_all()
    print(f"  Health check: {health}")
    
    print("  [PASS] Platform registry working")
    return True


async def main():
    print("=" * 60)
    print("TERMINATORBOT PLATFORM INTEGRATION TESTS")
    print("=" * 60)
    
    results = {}
    
    try:
        results['demo_broker'] = await test_demo_broker()
    except Exception as e:
        print(f"  [FAIL] {e}")
        results['demo_broker'] = False
    
    try:
        results['kalshi_broker'] = await test_kalshi_broker()
    except Exception as e:
        print(f"  [FAIL] {e}")
        results['kalshi_broker'] = False
    
    try:
        results['platform_registry'] = await test_platform_registry()
    except Exception as e:
        print(f"  [FAIL] {e}")
        results['platform_registry'] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + ("ALL TESTS PASSED!" if all_passed else "SOME TESTS FAILED"))
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
