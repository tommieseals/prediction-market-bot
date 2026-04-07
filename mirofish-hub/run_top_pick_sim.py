#!/usr/bin/env python3
"""Run MiroFish sim on the top dashboard pick."""
import requests
import sqlite3
from datetime import datetime
from mirofish_client import MiroFishClient

WHALE_API = "http://localhost:8081"
MIROFISH_API = "http://localhost:5001"
DB_PATH = "data/whale_hunter.db"

def main():
    # Get top pick from dashboard API
    print("=" * 60)
    print("MIROFISH VALIDATION - TOP DASHBOARD PICK")
    print("=" * 60)
    
    r = requests.get(f"{WHALE_API}/api/consensus?limit=1", timeout=30)
    picks = r.json().get("picks", [])
    
    if not picks:
        print("No picks found!")
        return
    
    pick = picks[0]
    market_title = pick.get("market_title", "Unknown")
    condition_id = pick.get("condition_id", "")
    whale_count = pick.get("whale_count", 0)
    miro_status = pick.get("mirofish_status", "not_run")
    
    print(f"\nMarket: {market_title}")
    print(f"Condition ID: {condition_id}")
    print(f"Whale Count: {whale_count}")
    print(f"Current MiroFish Status: {miro_status}")
    
    if miro_status == "validated":
        print("\nAlready validated! Skipping.")
        return
    
    # Run MiroFish simulation
    print("\n" + "-" * 60)
    print("Starting MiroFish simulation...")
    print("This will take ~20-25 minutes on RTX 3060...")
    print("-" * 60)
    
    client = MiroFishClient(base_url=MIROFISH_API, poll_timeout=1800)
    
    try:
        result = client.run_dual_platform(
            simulation_requirement=f"""
            Prediction market analysis:
            
            Market: {market_title}
            
            {whale_count} whale traders have taken positions on this market.
            
            Simulate crowd sentiment with diverse agents:
            1. Would the general public bet YES or NO on this?
            2. What probability would informed traders assign?
            3. What factors influence this outcome?
            """,
            seed_text=market_title,
            skip_graph=True
        )
        
        print("\n" + "=" * 60)
        print("SIMULATION COMPLETE")
        print("=" * 60)
        
        status = result.get("status", "unknown")
        swarm_prob = result.get("probability", 50.0)
        
        print(f"Status: {status}")
        print(f"Swarm Probability: {swarm_prob}%")
        
        # Save to database
        if status == "success":
            conn = sqlite3.connect(DB_PATH, timeout=60)
            conn.execute("PRAGMA busy_timeout = 60000")
            cur = conn.cursor()
            
            cur.execute("""
                INSERT OR REPLACE INTO mirofish_results 
                (condition_id, swarm_prob, swarm_sentiment, validates_whales, edge, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                condition_id,
                swarm_prob,
                result.get("sentiment", "neutral"),
                1 if result.get("validates", True) else 0,
                result.get("edge", 0),
                "success",
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            conn.commit()
            conn.close()
            print(f"\nSaved to database!")
        
    except Exception as e:
        print(f"\nError: {e}")
        raise

if __name__ == "__main__":
    main()
