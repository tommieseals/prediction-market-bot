# Smart LLM Routing Guide - April 4, 2026

## 🎯 Route by Task Type (UPDATED WITH QWEN3:4B)

### RTX Workstation (100.115.12.91) - PRIMARY WORKHORSE
**Hardware:** RTX 3060 (12GB VRAM), 32GB RAM  
**Models:** qwen3:4b (97.5 tok/sec!), qwen2.5-coder:7b, gemma4:e4b

**Use for:**
- ✅ **Trading decisions** (qwen3:4b - FASTEST at 97.5 tok/sec!)
- ✅ **Consensus voting** (qwen3:4b - 2.4x faster than before)
- ✅ **Code generation** (qwen2.5-coder:7b - specialist)
- ✅ **Heavy reasoning** (gemma4:e4b - 9.6GB model)
- ✅ **Batch processing**
- ✅ **Anything time-sensitive**

**RTX is now the DEFAULT for most tasks!**

---

### Mac Mini (100.88.105.106) - FAST & SIMPLE
**Hardware:** 16GB RAM (3GB max model size!)  
**Model:** qwen2.5:3b (~30 tok/sec)

**Use for:**
- ✅ Simple questions (weather, time, lookups)
- ✅ Quick queries (when RTX is busy)
- ✅ Tiebreaker in ensemble voting (weight: 10%)
- ❌ **NOT FOR:** Code, heavy reasoning, trading (too slow)

**Rule:** If prompt >200 tokens or complex → use RTX instead

---

### Mac Pro (100.85.43.98) - SECONDARY COMPUTE
**Hardware:** 32GB RAM  
**Model:** qwen2.5:7b

**Use for:**
- ✅ Ensemble voting (weight: 30%)
- ✅ Overflow when RTX is maxed
- ✅ Medium-complexity tasks

---

### Google Cloud (100.107.231.87) - ALWAYS-ON BACKUP
**Hardware:** 8GB RAM  
**Model:** qwen2.5:7b  
**Cost:** ~$103/month

**Use for:**
- ✅ Ensemble voting (weight: 20%)
- ✅ High availability (always running)
- ⚠️ **Minimize usage** - costs money!

---

## 🔥 SMART ROUTING RULES (April 2026)

### 1. Trading & Market Analysis → RTX qwen3:4b
```python
# Speed: 97.5 tok/sec (fastest available!)
# Use for: Whale Hunter, Strategy Improver, Consensus Swarm
model = "qwen3:4b"
host = "100.115.12.91:11434"
```

### 2. Code Tasks → RTX qwen2.5-coder:7b
```python
# Specialist model, ~60 tok/sec
# Use for: Code generation, debugging, reviews
model = "qwen2.5-coder:7b"
host = "100.115.12.91:11434"
```

### 3. Heavy Reasoning → RTX gemma4:e4b
```python
# Large model (9.6 GB), ~40 tok/sec
# Use for: Complex analysis, multi-step reasoning
model = "gemma4:e4b"
host = "100.115.12.91:11434"
```

### 4. Simple Queries → Mac Mini qwen2.5:3b
```python
# Fast for simple tasks (~30 tok/sec)
# Use for: Weather, time, quick lookups
model = "qwen2.5:3b"
host = "100.88.105.106:11434"
```

### 5. Ensemble Voting → All Nodes
```python
# Multi-node consensus with weighted voting
nodes = {
    "rtx": {"model": "qwen3:4b", "host": "100.115.12.91:11434", "weight": 0.40},  # PRIMARY
    "macpro": {"model": "qwen2.5:7b", "host": "100.85.43.98:11434", "weight": 0.30},
    "cloud": {"model": "qwen2.5:7b", "host": "100.107.231.87:11434", "weight": 0.20},
    "macmini": {"model": "qwen2.5:3b", "host": "100.88.105.106:11434", "weight": 0.10}
}
```

---

## 📊 PERFORMANCE COMPARISON

| Task Type | Old Way | New Way | Speedup |
|-----------|---------|---------|---------|
| Trading decisions | qwen2.5:14b @ 40 tok/s | **qwen3:4b @ 97.5 tok/s** | **2.4x faster** |
| Code generation | qwen2.5:14b @ 40 tok/s | **qwen2.5-coder @ 60 tok/s** | **1.5x faster** |
| Simple queries | External API | Mac Mini qwen2.5:3b | FREE + fast |
| Heavy reasoning | qwen2.5:14b @ 40 tok/s | gemma4:e4b @ 40 tok/s | Same speed, better quality |

---

## 💰 COST OPTIMIZATION

### FREE Tier (Unlimited)
- RTX Ollama (all models) - $0
- Mac Mini Ollama - $0  
- Mac Pro Ollama - $0

### Paid/Limited
- Google Cloud VM - $103/month (minimize!)
- NVIDIA API - 50 calls/day (track usage!)

**Goal:** 90%+ inference on local RTX/Mac Mini, <10% on paid services

---

## 🎯 DECISION TREE

```
Is it a trading decision?
  YES → RTX qwen3:4b (97.5 tok/sec!)
  NO ↓

Is it code-related?
  YES → RTX qwen2.5-coder:7b (specialist)
  NO ↓

Is it heavy reasoning (>1000 tokens)?
  YES → RTX gemma4:e4b (9.6GB model)
  NO ↓

Is it a simple query (<200 tokens)?
  YES → Mac Mini qwen2.5:3b (fast & free)
  NO ↓

Does it need ensemble voting?
  YES → All nodes (weighted voting)
  NO ↓

DEFAULT → RTX qwen3:4b (fastest general-purpose)
```

---

## 🔄 DYNAMIC LOAD BALANCING (Future)

**Not implemented yet, but could add:**
- Check GPU utilization before routing
- Fallback to Mac Pro if RTX maxed
- Queue management for batch jobs
- Priority routing (trading > code > simple)

---

**Updated:** April 4, 2026  
**Status:** PRODUCTION - RTX optimization complete!  
**Next Review:** After 1 week of production use
