"""Test MiroFish report generation speed after optimizations"""
import requests
import time
import sys

MIROFISH_URL = "http://localhost:5001"

def test_report_speed():
    print("Finding completed simulation...")
    
    r = requests.get(f"{MIROFISH_URL}/api/simulation/list", timeout=30)
    sims = r.json().get('data', [])
    
    for sim in sims[:20]:
        sid = sim.get('simulation_id', '')
        if not sid:
            continue
            
        sr = requests.get(f"{MIROFISH_URL}/api/simulation/{sid}/status", timeout=10)
        if sr.status_code == 200 and sr.json().get('status') == 'completed':
            print(f"Testing with: {sid}")
            
            # Start report generation
            start = time.time()
            rr = requests.post(
                f"{MIROFISH_URL}/api/report/generate",
                json={"simulation_id": sid},
                timeout=30
            )
            
            if rr.status_code != 200:
                print(f"Error starting report: {rr.status_code}")
                print(rr.text[:300])
                return None
            
            report_id = rr.json().get('report_id')
            print(f"Report started: {report_id}")
            
            # Poll for completion (max 3 min)
            for i in range(36):
                time.sleep(5)
                pr = requests.get(f"{MIROFISH_URL}/api/report/{report_id}/status", timeout=10)
                if pr.status_code == 200:
                    data = pr.json()
                    status = data.get('status')
                    progress = data.get('progress', 0)
                    elapsed = (i+1)*5
                    print(f"[{elapsed}s] {status} - {progress}%")
                    
                    if status == 'completed':
                        total = time.time() - start
                        print(f"\n[SUCCESS] Report completed in {total:.0f}s")
                        return total
                    elif status == 'failed':
                        error = data.get('error', 'unknown')
                        print(f"\n[FAILED] {error}")
                        return None
            
            print("\n[TIMEOUT] Report took too long")
            return None
    
    print("No completed simulations found")
    return None

if __name__ == "__main__":
    result = test_report_speed()
    if result:
        if result < 60:
            print(f"\n>>> FAST! Under 1 minute")
        elif result < 120:
            print(f"\n>>> GOOD! Under 2 minutes")
        else:
            print(f"\n>>> SLOW - needs more optimization")
    sys.exit(0 if result else 1)
