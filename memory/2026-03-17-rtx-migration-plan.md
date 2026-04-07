# RTX Machine Migration - Master Plan
## Created: 2026-03-17 23:15 CDT
## Status: IN PROGRESS

---

## 🎯 OBJECTIVE
Complete infrastructure documentation update for new RTX machine migration. 
This must be done THOROUGHLY and CORRECTLY - no rushing.

---

## 📋 PHASE 1: INVESTIGATION (Before ANY changes)

### Task 1.1: Network Topology Audit
- [ ] Confirm all Tailscale nodes and their current status
- [ ] Identify which Mac Pros are active vs retired
- [ ] Investigate home-srv (100.115.235.86) - what is this?
- [ ] Confirm old Dell (100.119.87.108) status - retired?
- [ ] Document the ACTUAL current network topology

### Task 1.2: Role Assessment
- [ ] Determine optimal role for RTX machine
- [ ] Assess if Mac Mini should remain hub or change
- [ ] Evaluate which machine should run which services
- [ ] Consider GPU acceleration opportunities

### Task 1.3: Service Inventory
- [ ] List all services on each active node
- [ ] Identify any services that should migrate
- [ ] Check for conflicts or redundancies

---

## 📋 PHASE 2: DOCUMENTATION UPDATES

### Task 2.1: MASTER_KNOWLEDGE.md
- [ ] Update network table with correct IPs
- [ ] Add RTX machine with proper specs
- [ ] Remove/update CrowdStrike warnings
- [ ] Update role descriptions
- [ ] Verify all links and references

### Task 2.2: docs/infrastructure.md
- [ ] Full hardware specs for RTX
- [ ] Updated Tailscale topology
- [ ] New SSH config entries
- [ ] Monitoring commands for GPU
- [ ] Service inventory per node

### Task 2.3: memory/docs/MACHINE_ROLES.md
- [ ] Rewrite RTX/Dell section completely
- [ ] Update decision matrix
- [ ] New role assignments
- [ ] Update cross-machine commands

### Task 2.4: HEARTBEAT.md
- [ ] Add GPU health checks (nvidia-smi)
- [ ] Update IP addresses
- [ ] Add new nodes to monitoring
- [ ] Update thresholds for GPU

### Task 2.5: TOOLS.md
- [ ] Document GPU capabilities
- [ ] Update Ollama section for CUDA
- [ ] Add model capacity info
- [ ] Remove CrowdStrike warnings

### Task 2.6: SOUL.md
- [ ] Update Dell references
- [ ] Update infrastructure section

---

## 📋 PHASE 3: CROSS-BOT COORDINATION

### Task 3.1: Shared Memory Update
- [ ] Create migration status document
- [ ] Update shared-memory/infrastructure.json
- [ ] Notify other bots of changes

### Task 3.2: Verification
- [ ] Test SSH connections with new config
- [ ] Verify all documentation is consistent
- [ ] Cross-reference all files for accuracy

---

## 🔧 TOOLS TO USE

| Tool | Purpose |
|------|---------|
| **Sub-agents** | Parallel investigation tasks |
| **Kimi** | Vision analysis if needed |
| **Codex** | Generate config files/scripts |
| **Memory search** | Find all references to update |
| **SSH** | Verify node connectivity |

---

## 📝 PROGRESS LOG

| Time | Action | Status |
|------|--------|--------|
| 23:15 | Created migration plan | ✅ |
| 23:20 | Completed network investigation | ✅ |
| 23:25 | Completed RTX hardware audit | ✅ |
| 23:30 | Created shared-memory migration file | ✅ |
| 23:35 | Updated MASTER_KNOWLEDGE.md | ✅ |
| 23:38 | Updated docs/infrastructure.md | ✅ |
| 23:40 | Updated docs/security.md | ✅ |
| 23:42 | Updated memory/docs/MACHINE_ROLES.md | ✅ |
| 23:44 | Updated HEARTBEAT.md | ✅ |
| 23:46 | Updated TOOLS.md (GPU section + references) | ✅ |
| 23:48 | Created SSH config file | ✅ |
| | | |

---

## ⚠️ RULES FOR THIS MIGRATION

1. **INVESTIGATE before changing** - Confirm facts first
2. **ONE file at a time** - Complete each fully before moving on
3. **Document progress** - Update this file and shared memory
4. **Verify after each change** - Read back what was written
5. **No assumptions** - If unsure, ASK or investigate

---
