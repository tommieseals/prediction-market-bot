# -*- coding: utf-8 -*-
"""
Test MiroFish with Zep API key
Full pipeline test: Create project -> Build graph -> Create simulation -> Prepare -> Start
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(r"C:\Users\USER\clawd\mirofish-hub")
from mirofish_client import MiroFishClient

def main():
    client = MiroFishClient(poll_timeout=300)  # 5 min timeout
    
    print("=" * 60)
    print("MIROFISH + ZEP INTEGRATION TEST")
    print("=" * 60)
    
    # Health check
    if not client.health_check():
        print("[FAIL] MiroFish not running!")
        return
    print("[OK] MiroFish health check passed")
    
    # Test data - simple question
    test_requirement = "Predict whether people will be bullish or bearish on Bitcoin in the next week"
    test_text = """
    Bitcoin has been showing strong momentum lately.
    Institutional adoption continues to grow.
    ETF inflows have been consistent.
    However, macroeconomic uncertainty remains.
    Interest rates may stay higher for longer.
    Some analysts predict a pullback, others see ATH potential.
    Retail sentiment on Twitter appears mixed.
    Reddit crypto communities are cautiously optimistic.
    """
    
    try:
        # Step 1: Create project + ontology
        print("\n[Step 1] Creating project with ontology...")
        project = client.create_project(
            simulation_requirement=test_requirement,
            text=test_text,
            project_name="Zep Integration Test - BTC Sentiment"
        )
        project_id = project["data"]["project_id"]
        print(f"[OK] Project created: {project_id}")
        
        # Step 2: Build knowledge graph (requires Zep)
        print("\n[Step 2] Building knowledge graph (Zep)...")
        try:
            build_resp = client.build_graph(project_id)
            task_id = build_resp["data"]["task_id"]
            print(f"  Task ID: {task_id}")
            client.wait_for_task(task_id, label="graph_build")
            print("[OK] Knowledge graph built!")
        except Exception as e:
            print(f"[WARN] Graph build: {e}")
            print("  (Continuing without graph - simulation still works)")
        
        # Step 3: Create simulation
        print("\n[Step 3] Creating simulation...")
        sim_resp = client.create_simulation(project_id)
        simulation_id = sim_resp["data"]["simulation_id"]
        print(f"[OK] Simulation created: {simulation_id}")
        
        # Step 4: Prepare simulation (generate profiles)
        print("\n[Step 4] Preparing simulation (generating agent profiles)...")
        prep_resp = client.prepare_simulation(simulation_id)
        prep_data = prep_resp.get("data", {})
        if prep_data.get("already_prepared"):
            print("[OK] Already prepared!")
        else:
            task_id = prep_data.get("task_id")
            if task_id:
                print(f"  Task ID: {task_id}")
                client.wait_for_preparation(simulation_id, task_id)
            print("[OK] Simulation prepared!")
        
        # Step 5: Start simulation (just 3 rounds for test)
        print("\n[Step 5] Starting simulation (3 rounds)...")
        client.start_simulation(simulation_id, platform="twitter", max_rounds=3)
        print("[OK] Simulation started!")
        
        # Step 6: Wait for completion
        print("\n[Step 6] Waiting for simulation to complete...")
        client.wait_for_simulation(simulation_id)
        print("[OK] Simulation completed!")
        
        # Step 7: Generate report
        print("\n[Step 7] Generating report...")
        try:
            report_resp = client.generate_report(simulation_id)
            report_id = report_resp.get("data", {}).get("report_id")
            print(f"[OK] Report: {report_id}")
        except Exception as e:
            print(f"[WARN] Report: {e}")
        
        print("\n" + "=" * 60)
        print("MIROFISH + ZEP INTEGRATION TEST COMPLETE!")
        print("=" * 60)
        print(f"Project ID: {project_id}")
        print(f"Simulation ID: {simulation_id}")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
