# MiroFish API Compatibility Issue - April 4, 2026

## Problem
The `pharma_fda_connector.py` was written for an older/simpler MiroFish API that doesn't exist in the current version.

### What pharma connector expects:
- Simple POST to `/api/predict` or `/api/graph/ontology/generate`
- JSON body with question, context, agents, model
- Immediate response

### What current MiroFish actually has:
- Complex multi-step API requiring:
  1. File uploads (multipart/form-data)
  2. Required `simulation_requirement` parameter
  3. Multi-step process: create project → generate ontology → build graph → prepare simulation → run simulation → generate report
  4. Task-based async operations with polling

## Current MiroFish API Endpoints
```
/health - Health check (✅ works)
/api/graph/project/list - List projects
/api/graph/project/<id> - Get project
/api/graph/ontology/generate - Create project + upload files + generate ontology (multipart/form-data)
/api/graph/build - Build knowledge graph (async, returns task_id)
/api/simulation/prepare/<project_id> - Prepare simulation (async)
/api/simulation/run/<simulation_id> - Run simulation
/api/report/generate - Generate report
```

## Why pharma connector fails:
1. `/api/predict` doesn't exist (404)
2. `/api/graph/ontology/generate` requires files + simulation_requirement (400/500 error)
3. No simple "ask a question, get an answer" endpoint

## Solutions

### Option A: Manual FDA Database (Recommended)
Manually populate `outcomes.db` with upcoming FDA PDUFAs from public sources:
- FDA.gov PDUFA calendar
- BioPharmCatalyst
- Scrape from FDA press releases

**Pro:** Simple, reliable, no API dependency  
**Con:** Manual data entry

### Option B: Rewrite pharma connector
Update pharma_fda_connector.py to use new MiroFish API properly:
- Upload FDA documents as files
- Use full project workflow
- Much more complex

**Pro:** Uses MiroFish AI analysis  
**Con:** Significant rewrite needed, slower

### Option C: Find/deploy old MiroFish version
Find the simpler MiroFish API version pharma connector was written for.

**Pro:** Connector works as-is  
**Con:** May not exist, outdated

## Recommendation
**Go with Option A** - Manual FDA database population. The FDA PDUFA calendar doesn't change that frequently (maybe 10-20 entries per month), so manual entry is totally manageable.

## Status
- MiroFish API running ✅ (port 5001, health check OK)
- Pharma connector incompatible ❌ (API mismatch)
- Simple FDA checker created ✅ (`check_fda_simple.py`)
- Needs: FDA database population

## Created
April 4, 2026 04:15 CDT
