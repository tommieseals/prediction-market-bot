# Claude Code Prompt: MiroFish Swarm Integration

## MISSION
Integrate MiroFish AI swarm intelligence platform with our existing money-making projects. Create connectors, data pipelines, and automation to feed project data into MiroFish simulations and extract actionable predictions.

---

## INFRASTRUCTURE OVERVIEW

### Machines
| Machine | IP | Role | OS | Key Services |
|---------|-----|------|-----|--------------|
| **RTX Workstation** | 100.115.12.91 | PRIMARY - GPU Compute | Windows 11 | Clawdbot, Ollama (RTX 3060 12GB), MiroFish |
| **Mac Mini** | 100.88.105.106 | Automation Hub | macOS | Legion, Dashboard, LLM Gateway |
| **Mac Pro** | 100.92.123.115 | Heavy Compute | macOS | Large models (when awake) |

### MiroFish Location
```
C:\Users\USER\Desktop\mirofish-secure\
├── backend\           # Flask API (Python 3.12)
├── frontend\          # Vue.js UI
├── .env              # Configuration (LLM, Zep, auth)
└── SECURITY_AUDIT.md # Security review completed
```

**MiroFish Services:**
- Frontend: http://localhost:3000 (also http://100.115.12.91:3000)
- Backend API: http://localhost:5001
- LLM: Ollama qwen2.5:14b (local GPU-accelerated)
- Zep Graph Memory: DISABLED (optional - enable for full GraphRAG)

---

## TARGET PROJECTS FOR INTEGRATION

### PRIORITY 1: TerminatorBot (Prediction Markets) 💰
**Location:** `C:\Users\USER\clawd\TerminatorBot\`
**Purpose:** AI-powered prediction market trading on Kalshi ($10K paper balance)

**Data Available:**
- `src/scanners/` - Alpha, contrarian, dumb_bet, arbitrage scanners
- `src/data/` - Market data, sentiment scrapers
- `src/ml/` - XGBoost models, feature engineering
- Market feed: 33,665 Kalshi markets

**MiroFish Integration:**
1. **Input:** Feed breaking news + market data into MiroFish
2. **Simulation:** Simulate Twitter/Reddit crowd reaction
3. **Output:** Sentiment prediction → inform trading decisions
4. **Use Case:** "Will Trump win 2028?" → Simulate 1000 voters → Predict market movement

**Implementation:**
```python
# Create: C:\Users\USER\clawd\TerminatorBot\src\mirofish_connector.py
# - Fetch active Kalshi markets
# - For high-edge opportunities, run MiroFish simulation
# - Use simulation results to adjust position sizing
# - Log predictions vs actual outcomes for model training
```

---

### PRIORITY 2: Arbitrage Pharma (Biotech Deals) 💊
**Location:** `C:\Users\USER\clawd\arbitrage-pharma\`
**Purpose:** Identify pharma acquisition targets ($4.72B pipeline)

**Data Available:**
- `latest_scan.json` - 7.3MB of biotech company data
- `CRM.md` - Contact database
- `OUTREACH_DRAFTS.md` - Email templates
- Daily PNL reports, evening reports

**MiroFish Integration:**
1. **Input:** Company profiles, drug pipeline data, exec backgrounds
2. **Simulation:** Simulate FDA advisory committee deliberation
3. **Simulation:** Simulate pharma BD exec response to cold outreach
4. **Output:** Probability scores for each target

**Implementation:**
```python
# Create: C:\Users\USER\clawd\arbitrage-pharma\mirofish_analyzer.py
# - Parse target company data
# - Create agent personas (FDA reviewers, pharma execs, investors)
# - Run acquisition probability simulation
# - Rank targets by predicted success rate
```

---

### PRIORITY 3: Project Legion (Job Applications) 🚀
**Location (Mac Mini):** `/Users/tommie/project-legion-rusty-fix/Project-Legion/`
**Purpose:** Automated job applications (1,809 approved jobs)

**Data Available:**
- Job postings with company info
- Resume/profile data
- Application history
- Success/rejection tracking

**MiroFish Integration:**
1. **Input:** Job posting + company culture data
2. **Simulation:** Simulate hiring panel review of application
3. **Output:** Predicted success rate + optimization suggestions
4. **Use Case:** Test 5 cover letter variations → Pick highest-scoring

**Implementation:**
```python
# Create connector on Mac Mini
# SSH: ssh tommie@100.88.105.106
# Path: ~/project-legion-rusty-fix/Project-Legion/mirofish_optimizer.py
# - Analyze job posting requirements
# - Simulate hiring manager personas
# - Score application fit
# - Suggest resume optimizations
```

---

### PRIORITY 4: Project Vault (Stock Trading) 📈
**Location:** `C:\Users\USER\clawd\project-vault\`
**Purpose:** Automated stock trading ($105K live equity)

**Data Available:**
- `vault.py` - Main trading logic
- Position data (10 positions)
- Fear & Greed Index integration
- Tradier API connection

**MiroFish Integration:**
1. **Input:** Stock news, earnings data, social sentiment
2. **Simulation:** Simulate retail investor panic/euphoria
3. **Output:** Predicted sentiment shift → Position adjustments

**Implementation:**
```python
# Create: C:\Users\USER\clawd\project-vault\mirofish_sentiment.py
# - Monitor earnings announcements
# - Simulate WSB/Reddit reaction
# - Predict retail flow direction
# - Adjust position sizing based on crowd simulation
```

---

### PRIORITY 5: Money Machine (Freelance) 💵
**Location:** `C:\Users\USER\clawd\memory\money-machine-tracker.md`
**Purpose:** 31 income streams (Upwork, Fiverr, micro-tasks)

**MiroFish Integration:**
1. **Input:** Gig posting + proposal draft
2. **Simulation:** Simulate client evaluation process
3. **Output:** Predicted win rate + proposal optimization

---

## MIROFISH API REFERENCE (CORRECTED)

### Core Endpoints (Backend: localhost:5001)

**NOTE:** All long-running operations (graph build, simulation prepare, report generate) are ASYNC — they return a task_id that must be polled until completion.

```bash
# Step 1: Create project + upload files + generate ontology (combined endpoint)
POST /api/graph/ontology/generate
Content-Type: multipart/form-data
Fields: simulation_requirement (required), project_name, additional_context
Files: files (PDF/MD/TXT, multiple allowed)
→ Returns: project_id, ontology, files

# Step 2: Build knowledge graph (ASYNC — requires ZEP_API_KEY)
POST /api/graph/build
Content-Type: application/json
{"project_id": "proj_xxx", "chunk_size": 500, "chunk_overlap": 50}
→ Returns: task_id (poll with GET /api/graph/task/{task_id})

# Step 3: Create simulation
POST /api/simulation/create
{"project_id": "proj_xxx", "enable_twitter": true, "enable_reddit": true}
→ Returns: simulation_id

# Step 4: Prepare simulation (ASYNC — generates profiles + config via LLM)
POST /api/simulation/prepare
{"simulation_id": "sim_xxx", "use_llm_for_profiles": true}
→ Returns: task_id (poll with POST /api/simulation/prepare/status)

# Step 5: Start simulation
POST /api/simulation/start
{"simulation_id": "sim_xxx", "platform": "parallel", "max_rounds": 20}
→ Returns: runner_status, process_pid

# Step 6: Monitor simulation
GET /api/simulation/{simulation_id}/run-status
→ Returns: current_round, total_rounds, progress_percent

# Step 7: Generate report (ASYNC)
POST /api/report/generate
{"simulation_id": "sim_xxx"}
→ Returns: task_id, report_id

# Get report
GET /api/report/by-simulation/{simulation_id}

# Other useful endpoints
GET /api/simulation/history?limit=20
GET /api/graph/project/list?limit=50
GET /api/simulation/{simulation_id}/actions?limit=100
POST /api/simulation/stop  {"simulation_id": "sim_xxx"}
```

### Authentication
Currently disabled for development. When enabled:
```
Header: X-API-Key: <key>
# or
Header: Authorization: Bearer <key>
```

---

## IMPLEMENTATION ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                    MIROFISH INTEGRATION HUB                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ TerminatorBot│    │ Arb Pharma   │    │ Legion       │      │
│  │ Connector    │    │ Analyzer     │    │ Optimizer    │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌─────────────────────────────────────────────────────┐       │
│  │              MiroFish Integration Layer              │       │
│  │         C:\Users\USER\clawd\mirofish-hub\           │       │
│  │                                                      │       │
│  │  - mirofish_client.py (API wrapper)                 │       │
│  │  - project_factory.py (create/manage projects)      │       │
│  │  - simulation_runner.py (batch simulations)         │       │
│  │  - result_parser.py (extract predictions)           │       │
│  └─────────────────────────────────────────────────────┘       │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────┐       │
│  │                 MiroFish Backend                     │       │
│  │           http://localhost:5001/api                  │       │
│  │                                                      │       │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐    │       │
│  │  │ Graph  │  │Profile │  │ OASIS  │  │Report  │    │       │
│  │  │Builder │  │ Gen    │  │ Sim    │  │ Agent  │    │       │
│  │  └────────┘  └────────┘  └────────┘  └────────┘    │       │
│  └─────────────────────────────────────────────────────┘       │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────┐       │
│  │              Ollama LLM (qwen2.5:14b)               │       │
│  │                 GPU-Accelerated                      │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## PHASE 1: INTEGRATION HUB (ALREADY CREATED)

The integration hub has been created at `C:\Users\USER\clawd\mirofish-hub\`:

```
mirofish-hub/
├── mirofish_client.py          # Corrected API client (matches real endpoints)
├── terminator_connector.py     # TerminatorBot integration
├── requirements.txt            # Dependencies (requests)
└── predictions.jsonl           # Prediction log (created on first run)
```

### Quick Start:
```bash
cd C:\Users\USER\clawd\mirofish-hub
pip install -r requirements.txt
python mirofish_client.py                          # Health check
python terminator_connector.py                     # Check connectivity
python terminator_connector.py --test              # Test simulation
python terminator_connector.py --scan --top 3      # Scan top 3 markets
python terminator_connector.py --market "trump"    # Simulate specific market
```

### ORIGINAL Step 2 (for reference): Create MiroFish API Client
```python
# File: C:\Users\USER\clawd\mirofish-hub\mirofish_client.py

import requests
import json
from typing import Optional, Dict, Any, List
from pathlib import Path

class MiroFishClient:
    """Client for MiroFish Swarm Intelligence API"""
    
    def __init__(self, base_url: str = "http://localhost:5001", api_key: Optional[str] = None):
        self.base_url = base_url
        self.session = requests.Session()
        if api_key:
            self.session.headers['X-API-Key'] = api_key
    
    def create_project(self, name: str, description: str) -> Dict[str, Any]:
        """Create a new MiroFish project"""
        response = self.session.post(
            f"{self.base_url}/api/graph/projects",
            json={"name": name, "description": description}
        )
        response.raise_for_status()
        return response.json()
    
    def upload_seed_data(self, project_id: str, file_path: str) -> Dict[str, Any]:
        """Upload seed data (PDF, MD, TXT) to a project"""
        with open(file_path, 'rb') as f:
            response = self.session.post(
                f"{self.base_url}/api/graph/upload/{project_id}",
                files={"file": f}
            )
        response.raise_for_status()
        return response.json()
    
    def upload_text(self, project_id: str, text: str, filename: str = "seed.txt") -> Dict[str, Any]:
        """Upload raw text as seed data"""
        response = self.session.post(
            f"{self.base_url}/api/graph/upload/{project_id}",
            files={"file": (filename, text.encode(), "text/plain")}
        )
        response.raise_for_status()
        return response.json()
    
    def build_graph(self, project_id: str, chunk_size: int = 500) -> Dict[str, Any]:
        """Build knowledge graph from uploaded data"""
        response = self.session.post(
            f"{self.base_url}/api/graph/build/{project_id}",
            json={"chunk_size": chunk_size}
        )
        response.raise_for_status()
        return response.json()
    
    def generate_profiles(self, project_id: str, agent_count: int = 100, 
                         platform: str = "twitter") -> Dict[str, Any]:
        """Generate agent profiles for simulation"""
        response = self.session.post(
            f"{self.base_url}/api/simulation/profiles/{project_id}",
            json={"agent_count": agent_count, "platform": platform}
        )
        response.raise_for_status()
        return response.json()
    
    def run_simulation(self, project_id: str, prediction_query: str,
                      max_rounds: int = 20) -> Dict[str, Any]:
        """Run a swarm simulation"""
        response = self.session.post(
            f"{self.base_url}/api/simulation/run/{project_id}",
            json={
                "max_rounds": max_rounds,
                "prediction_query": prediction_query
            }
        )
        response.raise_for_status()
        return response.json()
    
    def get_simulation_status(self, project_id: str) -> Dict[str, Any]:
        """Get simulation status"""
        response = self.session.get(
            f"{self.base_url}/api/simulation/status/{project_id}"
        )
        response.raise_for_status()
        return response.json()
    
    def get_report(self, simulation_id: str) -> Dict[str, Any]:
        """Get simulation report"""
        response = self.session.get(
            f"{self.base_url}/api/report/{simulation_id}"
        )
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> bool:
        """Check if MiroFish is running"""
        try:
            response = self.session.get(f"{self.base_url}/api/simulation/history?limit=1")
            return response.status_code == 200
        except:
            return False


# Quick test
if __name__ == "__main__":
    client = MiroFishClient()
    if client.health_check():
        print("✅ MiroFish is running!")
    else:
        print("❌ MiroFish is not reachable")
```

### Step 3: Create TerminatorBot Connector (Priority 1)
```python
# File: C:\Users\USER\clawd\mirofish-hub\terminator_connector.py

import sys
sys.path.append(r"C:\Users\USER\clawd\TerminatorBot\src")
sys.path.append(r"C:\Users\USER\clawd\mirofish-hub")

from mirofish_client import MiroFishClient
import json
from datetime import datetime

class TerminatorMiroFishConnector:
    """Connect TerminatorBot to MiroFish for sentiment simulation"""
    
    def __init__(self):
        self.mirofish = MiroFishClient()
        self.project_id = None
    
    def setup_project(self, market_title: str, market_data: dict) -> str:
        """Create MiroFish project for a specific market"""
        project = self.mirofish.create_project(
            name=f"TerminatorBot: {market_title[:50]}",
            description=f"Swarm simulation for prediction market: {market_title}"
        )
        self.project_id = project['project_id']
        
        # Upload market data as seed
        seed_text = f"""
        PREDICTION MARKET ANALYSIS
        ==========================
        
        Market: {market_title}
        Current Price: {market_data.get('yes_price', 'N/A')}
        Volume: {market_data.get('volume', 'N/A')}
        Close Date: {market_data.get('close_date', 'N/A')}
        
        Question: {market_title}
        
        Simulate how the general public would react to this question.
        Consider:
        - Political leanings
        - Recent news events
        - Social media sentiment
        - Historical precedent
        """
        
        self.mirofish.upload_text(self.project_id, seed_text)
        return self.project_id
    
    def simulate_crowd(self, market_title: str, agent_count: int = 50) -> dict:
        """Run crowd simulation for a market"""
        if not self.project_id:
            raise ValueError("Must call setup_project first")
        
        # Build knowledge graph
        self.mirofish.build_graph(self.project_id)
        
        # Generate diverse agent profiles
        self.mirofish.generate_profiles(
            self.project_id, 
            agent_count=agent_count,
            platform="twitter"  # Twitter-style discourse
        )
        
        # Run simulation
        result = self.mirofish.run_simulation(
            self.project_id,
            prediction_query=f"Will '{market_title}' resolve YES or NO? What is the crowd sentiment?",
            max_rounds=10
        )
        
        return result
    
    def get_prediction(self, simulation_result: dict) -> dict:
        """Extract actionable prediction from simulation"""
        # Parse simulation output
        # Return: {"direction": "YES/NO", "confidence": 0.0-1.0, "reasoning": "..."}
        report = self.mirofish.get_report(simulation_result['simulation_id'])
        
        return {
            "simulation_id": simulation_result['simulation_id'],
            "report": report,
            "timestamp": datetime.now().isoformat()
        }


# Example usage
if __name__ == "__main__":
    connector = TerminatorMiroFishConnector()
    
    # Example market
    market = {
        "title": "Will Trump win the 2028 presidential election?",
        "yes_price": 0.45,
        "volume": 1000000,
        "close_date": "2028-11-05"
    }
    
    connector.setup_project(market["title"], market)
    result = connector.simulate_crowd(market["title"], agent_count=100)
    prediction = connector.get_prediction(result)
    
    print(json.dumps(prediction, indent=2))
```

---

## PHASE 2: CONNECT REMAINING PROJECTS

After Phase 1 is working, create connectors for:

1. **arbitrage_connector.py** - Feed pharma targets, simulate BD exec responses
2. **legion_connector.py** - Simulate hiring panels, optimize applications
3. **vault_connector.py** - Simulate retail investor sentiment
4. **freelance_connector.py** - Simulate client evaluation of proposals

---

## PHASE 3: AUTOMATION & CRON

Create scheduled jobs to run simulations automatically:

```python
# File: C:\Users\USER\clawd\mirofish-hub\scheduled_simulations.py

# Run hourly alongside TerminatorBot
# - Identify high-edge markets
# - Run MiroFish simulation on top 5
# - Adjust trading signals based on swarm prediction
```

---

## SUCCESS CRITERIA

1. ✅ MiroFish API client working
2. ✅ TerminatorBot connector functional
3. ✅ Can create project, upload data, run simulation
4. ✅ Extract actionable predictions from simulation reports
5. ✅ Integration tested with real market data
6. ✅ Predictions logged for backtesting

---

## EXECUTION CHECKLIST

- [ ] Create `C:\Users\USER\clawd\mirofish-hub\` directory
- [ ] Implement `mirofish_client.py`
- [ ] Test MiroFish API endpoints
- [ ] Implement `terminator_connector.py`
- [ ] Run first simulation with real Kalshi market
- [ ] Parse and log prediction results
- [ ] Create remaining connectors (pharma, legion, vault)
- [ ] Set up automation/cron jobs
- [ ] Document results and iterate

---

## NOTES

- MiroFish is LIVE at http://localhost:5001 (backend) and http://localhost:3000 (frontend)
- Uses Ollama qwen2.5:14b for LLM (GPU-accelerated, FREE)
- Zep Cloud disabled (graph memory features unavailable without key)
- All projects are on the RTX Workstation unless noted (Mac Mini for Legion)
- Take your time. Build it right. Test each component before moving on.

---

## START

Begin with Phase 1: Create the mirofish-hub directory and implement the API client. Test connectivity. Then build the TerminatorBot connector and run a real simulation.

This is the foundation for AI-powered prediction across all our projects. Build it solid. 🐟🔮
