"""
Quick test to verify MiroFish report generation speed with Groq
"""
import time
import requests
import json

MIROFISH_URL = "http://localhost:5001"

def test_llm_speed():
    """Test raw LLM speed via MiroFish"""
    print("Testing LLM speed through MiroFish backend...")
    
    # Get a recent simulation to test with
    response = requests.get(f"{MIROFISH_URL}/api/simulation/list", timeout=30)
    sims = response.json().get('data', [])
    
    if not sims:
        print("No simulations found!")
        return
    
    # Find one with a completed simulation
    for sim in sims[:10]:
        sim_id = sim.get('simulation_id')
        if not sim_id:
            continue
            
        # Check simulation status
        status_resp = requests.get(f"{MIROFISH_URL}/api/simulation/{sim_id}/status", timeout=30)
        if status_resp.status_code == 200:
            status = status_resp.json()
            if status.get('status') == 'completed':
                print(f"Found completed simulation: {sim_id}")
                
                # Test report generation
                print("\nStarting report generation test...")
                start = time.time()
                
                report_resp = requests.post(
                    f"{MIROFISH_URL}/api/report/generate",
                    json={"simulation_id": sim_id},
                    timeout=300  # 5 min timeout
                )
                
                elapsed = time.time() - start
                
                if report_resp.status_code == 200:
                    result = report_resp.json()
                    report_id = result.get('report_id')
                    print(f"✅ Report started: {report_id}")
                    print(f"⏱️ Initial response time: {elapsed:.1f}s")
                    
                    # Poll for completion
                    for i in range(60):  # Max 5 minutes
                        time.sleep(5)
                        poll_resp = requests.get(
                            f"{MIROFISH_URL}/api/report/{report_id}/status",
                            timeout=30
                        )
                        if poll_resp.status_code == 200:
                            poll_data = poll_resp.json()
                            status = poll_data.get('status')
                            progress = poll_data.get('progress', 0)
                            print(f"  [{i*5}s] Status: {status}, Progress: {progress}%")
                            
                            if status == 'completed':
                                total_time = time.time() - start
                                print(f"\n✅ REPORT COMPLETE in {total_time:.1f}s")
                                return total_time
                            elif status == 'failed':
                                print(f"\n❌ REPORT FAILED: {poll_data.get('error')}")
                                return None
                else:
                    print(f"❌ Failed to start report: {report_resp.status_code}")
                    print(report_resp.text[:500])
                return None
    
    print("No completed simulations found to test with")
    return None

if __name__ == "__main__":
    result = test_llm_speed()
    if result:
        if result < 120:
            print(f"\n🚀 FAST! Report generated in {result:.0f}s (under 2 min)")
        elif result < 300:
            print(f"\n⚠️ MODERATE - Report took {result:.0f}s (2-5 min)")
        else:
            print(f"\n🐌 SLOW - Report took {result:.0f}s (over 5 min)")
    else:
        print("\n❌ Test failed")
