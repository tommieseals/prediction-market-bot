import time
import requests
from whale_scorer import score_trader, WhaleProfile
from polymarket_api import PolymarketAPI

print("Testing whale scorer performance...")
print("="*50)

# Initialize API
api = PolymarketAPI(rate_limit=0.5)

# Get one whale from leaderboard
print("\n1. Fetching leaderboard...")
start = time.time()
leaders = api.get_leaderboard(limit=3)
print(f"   Got {len(leaders)} leaders in {time.time()-start:.1f}s")

if not leaders:
    print("   ERROR: No leaderboard data!")
    api.close()
    exit(1)

# Score just one whale
entry = leaders[0]
addr = entry.get("proxyWallet") or entry.get("address", "")
name = entry.get("userName") or entry.get("username") or addr[:10]

print(f"\n2. Scoring whale: {name}")
print(f"   Address: {addr[:30]}...")

# Time each step
print("\n3. Fetching positions...")
start = time.time()
positions = api.get_positions(addr)
print(f"   Got {len(positions)} open positions in {time.time()-start:.1f}s")

print("\n4. Fetching closed positions...")
start = time.time()
closed = api.get_closed_positions(addr)
print(f"   Got {len(closed)} closed positions in {time.time()-start:.1f}s")

print("\n5. Fetching activity...")
start = time.time()
activity = api.get_activity(addr)
print(f"   Got {len(activity)} activities in {time.time()-start:.1f}s")

print("\n6. Running full score_whale()...")
start = time.time()
try:
    whale = score_trader(
        address=addr,
        name=name,
        pnl=float(entry.get("pnl", 0) or 0),
        volume=float(entry.get("volume", 0) or entry.get("vol", 0) or 0),
        positions=positions,
        closed_positions=closed,
        activity=activity,
    )
    elapsed = time.time() - start
    print(f"   Scored in {elapsed:.1f}s")
    print(f"\n   Results:")
    print(f"     Elite Score: {whale.elite_score:.1f}")
    print(f"     Brier Score: {whale.brier_score:.3f}")
    print(f"     Win Rate: {whale.win_rate:.1%}")
    print(f"     Open Positions: {len(whale.positions)}")
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

api.close()
print("\n" + "="*50)
print("Test complete!")
