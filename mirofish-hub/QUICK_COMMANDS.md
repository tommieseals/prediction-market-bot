# Quick Commands Reference

## Daily Workflow

### Morning (6 AM)
```bash
cd C:\Users\USER\clawd\mirofish-hub
python morning_report.py --send
```

### Throughout Day (Every 4h)
```bash
python elite_tracker.py --list
python market_scanner.py --top 10
python elite_signals.py --scan --alert
```

### Evening Review
```bash
python whale_dashboard.py
python performance_tracker.py
python strategy_improver.py --quick
```

---

## Tool Reference

### Check Dashboard
```bash
python whale_dashboard.py
```

### List Elite Whales
```bash
python elite_tracker.py --list
python elite_tracker.py --report  # Send to Telegram
```

### Scan Markets
```bash
python market_scanner.py --top 20
python market_scanner.py --alert  # Send to Telegram
```

### Compare Whales
```bash
python whale_compare.py yesmamaok tradecraft
python whale_compare.py BWArmageddon joosangyoo
```

### Check Performance
```bash
python performance_tracker.py
python elite_backtester.py
```

### Generate Signals
```bash
python elite_signals.py --scan
python elite_signals.py --scan --alert
```

### AI Strategy Analysis
```bash
python strategy_improver.py --quick
python strategy_improver.py --question "Why are NO bets losing?"
```

### Category Analysis
```bash
python category_analyzer.py
```

### Debug Signal Issues
```bash
python signal_debugger.py
```

---

## Key Findings Reference

### Whale Count
- 3-5 whales = 64% ✅
- 7+ whales = 31% ❌

### Confidence
- 70-89% = 72% ✅
- 90%+ = 47% ❌

### Days
- Mon-Wed = GOOD ✅
- Thu-Fri = AVOID ❌

### Categories
- Tennis = 94% ✅
- Spreads = 91% ✅
- Politics = 49% ❌

---

## Legendary Whales (100% WR)
1. yesmamaok (54/0)
2. UnfortunateSon (52/0)
3. BWArmageddon (50/0)
4. one8tyfive (37/0)
5. joosangyoo (26/0)
