#!/usr/bin/env python3
"""Run a whale trade simulation through MiroFish"""

from mirofish_client import MiroFishClient
import json
import time

def main():
    client = MiroFishClient()

    # beachboy4's active position
    seed_text = """
WHALE ALERT: beachboy4 (Top #1 on Polymarket, +$808K PnL) just took a position:

Market: Will the Toronto Raptors beat the Denver Nuggets?
Position: YES at $0.30 (103,000 shares = ~$31K USD)

beachboy4 stats:
- Total PnL: +$808,111 USD
- One of the top performing traders on Polymarket
- Elite score: 27 (high skill trader based on Brier scoring)

Question for swarm: What is the TRUE probability the Raptors beat the Nuggets?
Consider: Home/away advantage, injuries, recent form, Vegas betting lines, whale conviction signal.
"""

    sim_requirement = (
        "Analyze beachboy4's whale position on Toronto Raptors vs Denver Nuggets. "
        "This is a $808K PnL trader taking a YES position at 0.30. "
        "Generate 15 specialized agents: NBA analysts, sports bettors, "
        "prediction market experts, and contrarian traders. "
        "Debate the TRUE probability on Twitter and Reddit."
    )

    print("=" * 60)
    print("WHALE HUNTER - Live Simulation")
    print("=" * 60)
    print("")
    print("Target: beachboy4 (#1 Polymarket, $808K PnL)")
    print("Market: Raptors vs Nuggets")
    print("Position: YES @ $0.30 (103K shares)")
    print("")

    result = client.run_dual_platform(
        simulation_requirement=sim_requirement,
        seed_text=seed_text,
        project_name="Whale Hunt: beachboy4 - Raptors vs Nuggets",
        max_rounds=20,
        skip_graph=True  # Skip graph building for faster run
    )

    print("")
    print("=" * 60)
    print("SIMULATION COMPLETE")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    main()
