# -*- coding: utf-8 -*-
"""
TerminatorBot + MiroFish Integration Test
Creates a fresh simulation with Kalshi market data
"""
import os
import sys
import json
import time

# Set UTF-8 encoding
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(r"C:\Users\USER\clawd\mirofish-hub")
from mirofish_client import MiroFishClient

def main():
    print("=" * 60)
    print("TERMINATORBOT + MIROFISH TEST")
    print("=" * 60)
    
    client = MiroFishClient(poll_timeout=600)  # 10 min timeout
    
    if not client.health_check():
        print("[FAIL] MiroFish not running!")
        return
    print("[OK] MiroFish connected")
    
    # TerminatorBot style market question
    market_question = "Will Bitcoin price exceed $100,000 by end of March 2026?"
    
    seed_data = """
PREDICTION MARKET ANALYSIS: Bitcoin Price Prediction

Current Market Context (March 2026):
- Bitcoin is currently trading around $87,000
- Recent ETF inflows have been strong
- Institutional adoption continues growing
- Macro environment: Fed pausing rate cuts
- Crypto sentiment: Cautiously bullish

Key Factors to Consider:
1. ETF flows and institutional demand
2. Halving effect (occurred April 2024)
3. Regulatory environment
4. Macro liquidity conditions
5. Retail sentiment on social media

Historical Context:
- Bitcoin hit $69K ATH in November 2021
- Crashed to $16K in 2022 bear market
- Recovered throughout 2023-2024
- Post-halving rallies typically take 12-18 months

Social Media Sentiment:
- Twitter/X crypto community is divided
- Reddit r/bitcoin is moderately bullish
- YouTube influencers predicting various targets
- Retail Fear & Greed Index at 65 (Greed)

The Question: Will BTC hit $100K by end of March 2026?
Simulate public opinion and predict crowd sentiment.
    """
    
    try:
        # Step 1: Create project
        print("\n[Step 1] Creating project...")
        project = client.create_project(
            simulation_requirement=market_question,
            text=seed_data,
            project_name="TerminatorBot - BTC 100K Prediction"
        )
        project_id = project["data"]["project_id"]
        print(f"[OK] Project: {project_id}")
        
        # Step 2: Build graph (skip if Zep fails)
        print("\n[Step 2] Building knowledge graph...")
        try:
            build_resp = client.build_graph(project_id)
            task_id = build_resp["data"]["task_id"]
            print(f"  Task: {task_id}")
            client.wait_for_task(task_id, label="graph")
            print("[OK] Graph built")
        except Exception as e:
            print(f"[WARN] Graph skipped: {e}")
        
        # Step 3: Create simulation
        print("\n[Step 3] Creating simulation...")
        sim_resp = client.create_simulation(project_id, enable_twitter=True, enable_reddit=False)
        simulation_id = sim_resp["data"]["simulation_id"]
        print(f"[OK] Simulation: {simulation_id}")
        
        # Step 4: Prepare
        print("\n[Step 4] Preparing (generating agents)...")
        prep_resp = client.prepare_simulation(simulation_id, parallel_profile_count=3)
        prep_data = prep_resp.get("data", {})
        if not prep_data.get("already_prepared"):
            task_id = prep_data.get("task_id")
            if task_id:
                print(f"  Task: {task_id}")
                client.wait_for_preparation(simulation_id, task_id)
        print("[OK] Prepared")
        
        # Step 5: Start simulation (just 2 rounds)
        print("\n[Step 5] Starting simulation (2 rounds)...")
        client.start_simulation(simulation_id, platform="twitter", max_rounds=2)
        print("[OK] Started!")
        
        # Step 6: Wait and monitor
        print("\n[Step 6] Monitoring...")
        start = time.time()
        while True:
            status = client.get_run_status(simulation_id)
            data = status.get("data", {})
            runner_status = data.get("runner_status", "unknown")
            current = data.get("current_round", 0)
            total = data.get("total_rounds", 0)
            actions = data.get("total_actions_count", 0)
            elapsed = int(time.time() - start)
            
            print(f"  [{elapsed}s] status={runner_status}, round={current}/{total}, actions={actions}")
            
            if runner_status in ("completed", "stopped"):
                print("[OK] Simulation completed!")
                break
            if runner_status in ("failed", "error"):
                error = data.get("error", "unknown")
                print(f"[FAIL] {error[:200]}")
                break
            if elapsed > 300:  # 5 min timeout
                print("[TIMEOUT] Stopping...")
                client.stop_simulation(simulation_id)
                break
            
            time.sleep(5)
        
        # Step 7: Get actions
        print("\n[Step 7] Getting actions...")
        try:
            actions_resp = client.get_simulation_actions(simulation_id, limit=20)
            actions_data = actions_resp.get("data", [])
            print(f"Actions collected: {len(actions_data)}")
            for action in actions_data[:5]:
                print(f"  - {action.get('agent_name', '?')}: {action.get('action_type', '?')}")
        except Exception as e:
            print(f"[WARN] Actions: {e}")
        
        print("\n" + "=" * 60)
        print("COMPLETE")
        print(f"Project: {project_id}")
        print(f"Simulation: {simulation_id}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
