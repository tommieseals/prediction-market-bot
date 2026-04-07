# MiroFish AI - Complete Knowledge Base

*Last Updated: 2026-03-19*

---

## What Is MiroFish?

**MiroFish** is a multi-agent swarm intelligence platform for simulating social media opinion and predicting outcomes. "Predict Anything" - it simulates how crowds of AI agents would react to any scenario.

### Core Capabilities
- **Swarm Simulation**: 100+ AI agents simulate Twitter/Reddit discussions
- **Opinion Prediction**: Predict public reaction to events, announcements, questions
- **GraphRAG Memory**: Uses Zep Cloud for persistent knowledge graphs
- **Multi-Platform**: Simulates Twitter AND Reddit simultaneously

### Tech Stack
| Component | Technology |
|-----------|------------|
| Frontend | Vue.js 3 + Vite |
| Backend | Python Flask |
| LLM | Ollama (qwen2.5:14b on RTX) |
| Graph Memory | Zep Cloud (optional) |
| Simulation Engine | OASIS (CAMEL-AI) |

### Origin
- **GitHub**: github.com/666ghj/MiroFish
- **Backed by**: Shanda Group (盛大集团) - Chinese company
- **Status**: Open source, self-hosted fork secured

---

## Our MiroFish Deployment

### Location
```
C:\Users\USER\Desktop\mirofish-secure\
├── backend\           # Flask API (Python 3.12)
├── frontend\          # Vue.js UI
├── .env              # Configuration
└── SECURITY_AUDIT.md # Security review completed
```

### Services
| Service | URL |
|---------|-----|
| Frontend UI | http://localhost:3000 |
| Backend API | http://localhost:5001 |
| LLM | Ollama qwen2.5:14b (local GPU) |

### Status
- ✅ Security audited and patched
- ✅ Self-hosted (no external dependencies)
- ✅ GPU-accelerated (RTX 3060)
- ⚠️ Zep Cloud DISABLED (optional feature)

---

## API Reference (Corrected Endpoints)

### Full Pipeline Flow
```
1. Create Project + Upload Files → POST /api/graph/ontology/generate
2. Build Knowledge Graph (async) → POST /api/graph/build
3. Create Simulation → POST /api/simulation/create
4. Prepare Simulation (async) → POST /api/simulation/prepare
5. Start Simulation → POST /api/simulation/start
6. Monitor Progress → GET /api/simulation/{id}/run-status
7. Generate Report (async) → POST /api/report/generate
8. Get Report → GET /api/report/by-simulation/{id}
```

### Key Endpoints

```bash
# Step 1: Create project + ontology (combined)
POST /api/graph/ontology/generate
Content-Type: multipart/form-data
Fields: simulation_requirement, project_name, additional_context
Files: files (PDF/MD/TXT)
→ Returns: project_id, ontology

# Step 2: Build graph (ASYNC - needs ZEP_API_KEY)
POST /api/graph/build
{"project_id": "proj_xxx", "chunk_size": 500}
→ Returns: task_id (poll with GET /api/graph/task/{task_id})

# Step 3: Create simulation
POST /api/simulation/create
{"project_id": "proj_xxx", "enable_twitter": true, "enable_reddit": true}
→ Returns: simulation_id

# Step 4: Prepare simulation (ASYNC)
POST /api/simulation/prepare
{"simulation_id": "sim_xxx", "use_llm_for_profiles": true}
→ Returns: task_id

# Step 5: Start simulation
POST /api/simulation/start
{"simulation_id": "sim_xxx", "platform": "parallel", "max_rounds": 20}

# Step 6: Monitor
GET /api/simulation/{simulation_id}/run-status

# Step 7: Report
POST /api/report/generate {"simulation_id": "sim_xxx"}
GET /api/report/by-simulation/{simulation_id}

# Utility
GET /api/simulation/history?limit=20
GET /api/graph/project/list?limit=50
POST /api/simulation/stop {"simulation_id": "sim_xxx"}
```

---

## Integration Hub

### Location
```
C:\Users\USER\clawd\mirofish-hub\
├── mirofish_client.py          # API client (corrected endpoints)
├── terminator_connector.py     # TerminatorBot integration
├── requirements.txt            # Dependencies
└── predictions.jsonl           # Prediction log
```

### MiroFishClient Class

Full Python client with methods:
- `health_check()` - Check if MiroFish is running
- `create_project(simulation_requirement, files/text)` - Create project + upload + ontology
- `build_graph(project_id)` - Start async graph build
- `wait_for_task(task_id)` - Poll until task completes
- `create_simulation(project_id)` - Create simulation from project
- `prepare_simulation(simulation_id)` - Generate profiles + config
- `start_simulation(simulation_id)` - Run the simulation
- `wait_for_simulation(simulation_id)` - Wait for completion
- `generate_report(simulation_id)` - Create analysis report
- `run_pipeline(...)` - Full end-to-end automation

### Quick Start
```bash
cd C:\Users\USER\clawd\mirofish-hub
python mirofish_client.py  # Health check
```

---

## Target Project Integrations

### Priority 1: TerminatorBot (Prediction Markets) 💰
**Location:** `C:\Users\USER\clawd\TerminatorBot\`
**Use Case:** Simulate crowd sentiment on Kalshi markets
**Flow:** Market data → MiroFish simulation → Sentiment prediction → Trading signals

### Priority 2: Arbitrage Pharma (Biotech Deals) 💊
**Location:** `C:\Users\USER\clawd\arbitrage-pharma\`
**Use Case:** Simulate FDA panel reactions, BD exec responses
**Flow:** Company data → MiroFish simulation → Acquisition probability

### Priority 3: Project Legion (Job Applications) 🚀
**Location:** Mac Mini: `/Users/tommie/project-legion-rusty-fix/Project-Legion/`
**Use Case:** Simulate hiring panel review of applications
**Flow:** Job posting → MiroFish simulation → Optimize cover letters

### Priority 4: Project Vault (Stock Trading) 📈
**Location:** `C:\Users\USER\clawd\project-vault\`
**Use Case:** Simulate retail investor panic/euphoria
**Flow:** Stock news → MiroFish simulation → Position sizing

---

## Security Audit Summary

### Vulnerabilities Found & Fixed

| Issue | Severity | Status |
|-------|----------|--------|
| Error traceback exposed | HIGH | ✅ Fixed |
| No API authentication | HIGH | ✅ Fixed |
| Hardcoded SECRET_KEY | MEDIUM | ✅ Fixed |
| Wide-open CORS | MEDIUM | ✅ Fixed |
| Debug mode default True | MEDIUM | ✅ Fixed |
| File upload no validation | MEDIUM | ✅ Fixed |
| No rate limiting | LOW | ✅ Fixed |
| Predictable resource IDs | LOW | ✅ Fixed |

### Security Documents
- `C:\Users\USER\clawd\prompts\mirofish-security-fork-prompt.md` - Audit methodology
- `C:\Users\USER\Desktop\mirofish-secure\SECURITY_AUDIT.md` - Full findings

---

## Architecture Diagram

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

## Troubleshooting

### Common Issues

**500 Server Error on ontology/generate:**
- Check Ollama is running: `ollama ps`
- Check MiroFish backend: `curl http://localhost:5001/health`
- Check file upload format (multipart/form-data)

**Graph build fails:**
- Zep API key may not be configured
- Skip graph build with `skip_graph=True` in `run_pipeline()`

**Simulation preparation timeout:**
- LLM profile generation is slow
- Increase `poll_timeout` in client
- Use smaller `agent_count`

### Start MiroFish
```bash
cd C:\Users\USER\Desktop\mirofish-secure
python backend/run.py
```

---

## Future Work

- [ ] Complete TerminatorBot connector testing
- [ ] Build Arbitrage Pharma analyzer
- [ ] Create Legion optimizer (Mac Mini)
- [ ] Set up automated cron jobs
- [ ] Backtest predictions vs actual outcomes
- [ ] Train custom models on simulation data

---

*This is the complete MiroFish knowledge base. Update as integration progresses.*
