# 🐋 Whale Intelligence System

## Overview
A comprehensive system for tracking and analyzing Polymarket whale activity. Built overnight on 2026-03-27.

## Key Discovery
**Consensus is DESTROYING our edge!**
- Top 5 whales alone: 194W/0L = 100%
- Our old consensus: 40W/38L = 51%
- **Solution:** Follow elite whales individually, not as a crowd

## Quick Start

### 1. View Dashboard
```bash
cd mirofish-hub
python whale_dashboard.py
```

### 2. Check Elite Whales
```bash
python elite_tracker.py --list
```

### 3. Generate Signals
```bash
python elite_signals.py --scan --alert
```

### 4. Run Backtest
```bash
python elite_backtester.py
```

### 5. Morning Report
```bash
python morning_report.py --send
```

---

## Tools Reference

### Core Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| `whale_dashboard.py` | Real-time monitoring | `python whale_dashboard.py` |
| `elite_tracker.py` | Track 33 elite whales | `python elite_tracker.py --list` |
| `elite_signals.py` | Generate elite signals | `python elite_signals.py --scan` |
| `morning_report.py` | Daily summary | `python morning_report.py --send` |

### Analysis Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| `whale_profiler.py` | Build whale profiles | `python whale_profiler.py` |
| `whale_intel_v2.py` | Full intelligence report | `python whale_intel_v2.py` |
| `category_analyzer.py` | Category performance | `python category_analyzer.py` |
| `signal_debugger.py` | Debug consensus issues | `python signal_debugger.py` |
| `elite_backtester.py` | Backtest strategies | `python elite_backtester.py` |

### Utility Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| `strategy_improver.py` | AI analysis | `python strategy_improver.py --quick` |
| `smart_consensus.py` | Quality-filtered picks | `python smart_consensus.py` |
| `whale_alerts.py` | Alert system | `python whale_alerts.py --scan` |

---

## Validated Patterns

### Whale Count Effect
| Whales | Win Rate | Action |
|--------|----------|--------|
| 3-5 | 64.3% | ✅ TRADE |
| 6 | 54.5% | ⚠️ CAUTION |
| 7+ | 25-31% | ❌ AVOID |

### Confidence Effect
| Confidence | Win Rate | Action |
|------------|----------|--------|
| 70-89% | 72.7% | ✅ BEST |
| 60-70% | 60.0% | ✅ GOOD |
| 90%+ | 46.4% | ❌ TRAP |

### Day of Week
| Day | Win Rate | Action |
|-----|----------|--------|
| Monday | 75% | ✅ TRADE |
| Wednesday | 60% | ✅ TRADE |
| Thursday | 39% | ❌ AVOID |
| Friday | 42% | ❌ AVOID |

### Category Performance (Whale Positions)
| Category | Win Rate | Sample |
|----------|----------|--------|
| Tennis | 93.8% | n=560 |
| Spreads | 91.5% | n=223 |
| MLB | 95.3% | n=86 |
| Geopolitics | 84.1% | n=258 |
| Politics | 48.8% | n=168 |

---

## Elite Whales

### LEGENDARY Tier (100% Win Rate)
15 whales with perfect records:

1. **yesmamaok** - 54/0 - $8K PnL
2. **UnfortunateSon** - 52/0 - $41K PnL
3. **BWArmageddon** - 50/0 - $45K PnL
4. **one8tyfive** - 37/0 - $15K PnL
5. **joosangyoo** - 26/0 - $199K PnL
6. **How.Dare.You** - 23/0 - $87K PnL
7. Plus 9 more...

### ELITE Tier (95%+ Win Rate)
Additional 18 whales with near-perfect records.

---

## Database Schema

### Tables
- `tracked_whales` - All 372 tracked whales
- `whale_positions` - 48,989 position records
- `whale_profiles` - Individual profiles with follow scores
- `elite_whales` - 33 elite whale records
- `consensus_picks` - Old consensus signals (for comparison)
- `elite_signals` - New elite-only signals

---

## Recommendations

1. **STOP** following consensus when 7+ whales agree
2. **FOLLOW** elite whales individually
3. **FOCUS** on Tennis & Spreads (90%+ WR)
4. **TRADE** Mon-Wed only
5. **AVOID** Politics (49% WR)

---

## Automation

### Heartbeat Integration
Add to HEARTBEAT.md:
```
# Run 3x daily
python elite_tracker.py --list
python elite_signals.py --scan --alert
```

### Cron Jobs
- 6 AM: `python morning_report.py --send`
- Every 4h: `python strategy_improver.py --quick`
- Every 8h: `python elite_tracker.py --report`

---

## Architecture

```
mirofish-hub/
├── data/
│   ├── whale_hunter.db          # Main database
│   └── whale_intelligence_report_*.md
├── whale_dashboard.py           # Real-time dashboard
├── elite_tracker.py             # Elite whale tracking
├── elite_signals.py             # Signal generator
├── elite_backtester.py          # Strategy backtester
├── morning_report.py            # Daily reports
├── whale_profiler.py            # Profile builder
├── whale_intel_v2.py            # Intelligence reports
├── category_analyzer.py         # Category analysis
├── signal_debugger.py           # Debugging tools
├── strategy_improver.py         # AI analysis
├── smart_consensus.py           # Filtered signals
├── whale_alerts.py              # Alert system
└── WHALE_INTELLIGENCE_README.md # This file
```

---

## Contact
Built by Claude for Rusty
2026-03-27 Overnight Session
Three-Agent Workflow Applied Throughout
