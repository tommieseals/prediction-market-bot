# TerminatorBot 🤖💰

**Global Prediction Market Exploitation System**

AI-powered trading bot for prediction markets. Multi-platform arbitrage, ML alpha signals, sentiment analysis, and automated execution.

```
  ████████╗███████╗██████╗ ███╗   ███╗██╗███╗   ██╗ █████╗ ████████╗ ██████╗ ██████╗
  ╚══██╔══╝██╔════╝██╔══██╗████╗ ████║██║████╗  ██║██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗
     ██║   █████╗  ██████╔╝██╔████╔██║██║██╔██╗ ██║███████║   ██║   ██║   ██║██████╔╝
     ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║██║██║╚██╗██║██╔══██║   ██║   ██║   ██║██╔══██╗
     ██║   ███████╗██║  ██║██║ ╚═╝ ██║██║██║ ╚████║██║  ██║   ██║   ╚██████╔╝██║  ██║
     ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
```

## 🎯 Features

- **Multi-Platform Support**: Kalshi, Polymarket, Betfair, Limitless, Smarkets
- **4 Scanner Strategies**: Dumb Bet, Contrarian, Cross-Platform Arbitrage, ML Alpha
- **ML Alpha Model**: XGBoost-based prediction with 15+ features
- **Sentiment Analysis**: News + social media NLP scoring
- **Cross-Platform Matching**: Fuzzy + LLM verification for arbitrage detection
- **Risk Management**: Circuit breaker, position sizing, drawdown limits
- **Paper Trading**: Full simulation with P&L tracking
- **Real-Time Streaming**: WebSocket price feeds with event bus

## 📊 Current Status

| Platform | Balance | Status |
|----------|---------|--------|
| Kalshi | $10,000 | ✅ Funded |
| Polymarket | - | ⏳ Setup pending |
| Betfair | - | ⏳ Setup pending |

**Mode**: Paper Trading (switch to LIVE in `.env`)

## 🚀 Quick Start

```bash
# 1. Setup
cd TerminatorBot
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your API keys

# 3. Run
python src/main.py --status           # Check balances
python src/main.py --scan all         # Run all scanners
python src/main.py --continuous       # 24/7 mode
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TerminatorController                            │
│  (Master orchestrator - coordinates all subsystems)                  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│   Platforms   │          │   Scanners    │          │   Execution   │
│───────────────│          │───────────────│          │───────────────│
│ • Kalshi      │          │ • DumbBet     │          │ • OrderManager│
│ • Polymarket  │◀────────▶│ • Contrarian  │─────────▶│ • ArbExecutor │
│ • Betfair     │          │ • Arbitrage   │          │ • DryRunEngine│
│ • Limitless   │          │ • Alpha (ML)  │          │               │
└───────────────┘          └───────────────┘          └───────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│     Data      │          │      ML       │          │     Risk      │
│───────────────│          │───────────────│          │───────────────│
│ • MarketCache │          │ • AlphaModel  │          │ • CircuitBrkr │
│ • Historical  │◀────────▶│ • FeatureEng  │─────────▶│ • PositionSzr │
│ • Sentiment   │          │ • SentimentNLP│          │ • Rebalancer  │
└───────────────┘          └───────────────┘          └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    ▼
                          ┌───────────────┐
                          │   Matching    │
                          │───────────────│
                          │ • FuzzyMatch  │
                          │ • LLMVerifier │
                          │ • MarketGraph │
                          └───────────────┘
```

## 📁 Project Structure

```
TerminatorBot/
├── src/
│   ├── main.py              # CLI entrypoint & controller
│   ├── config.py            # Environment configuration
│   │
│   ├── platforms/           # Exchange adapters
│   │   ├── base.py          # Abstract broker interface
│   │   ├── platform_registry.py
│   │   ├── demo_broker.py   # Paper trading
│   │   ├── pmxt_broker.py   # pmxt library wrapper
│   │   └── betfair_broker.py
│   │
│   ├── scanners/            # Opportunity detection
│   │   ├── base_scanner.py  # Opportunity dataclass
│   │   ├── dumb_bet_scanner.py
│   │   ├── contrarian_scanner.py
│   │   ├── arbitrage_scanner.py
│   │   └── alpha_scanner.py
│   │
│   ├── ml/                  # Machine learning
│   │   ├── alpha_model.py   # XGBoost predictor
│   │   ├── feature_engine.py
│   │   └── sentiment_nlp.py
│   │
│   ├── matching/            # Cross-platform matching
│   │   ├── fuzzy_matcher.py
│   │   ├── llm_verifier.py
│   │   └── market_graph.py
│   │
│   ├── execution/           # Trade execution
│   │   ├── order_manager.py
│   │   ├── arb_executor.py
│   │   └── dry_run_engine.py
│   │
│   ├── core/                # Risk management
│   │   ├── circuit_breaker.py
│   │   ├── position_sizer.py
│   │   └── rebalancer.py
│   │
│   ├── streams/             # Real-time data
│   │   ├── event_bus.py
│   │   ├── price_aggregator.py
│   │   └── stream_manager.py
│   │
│   ├── data/                # Data layer
│   │   ├── market_cache.py
│   │   ├── historical_loader.py
│   │   └── sentiment_scraper.py
│   │
│   └── utils/               # Utilities
│       ├── logger.py
│       └── alerts.py
│
├── models/                  # Trained ML models
├── data/                    # Historical data, logs
├── tests/                   # Pytest suite
├── .env.example             # Configuration template
└── requirements.txt
```

## 🎰 Scanner Strategies

### 1. Dumb Bet Scanner
Finds markets with obvious mispricings (extreme probabilities that shouldn't be).

### 2. Contrarian Scanner
Detects markets where public sentiment diverges from fundamentals.

### 3. Arbitrage Scanner
Cross-platform arbitrage by matching identical markets across exchanges.
- Fuzzy string matching (85%+ similarity)
- Optional LLM verification for edge cases
- Calculates combined YES cost and arb edge

### 4. Alpha Scanner (ML)
XGBoost model trained on resolved markets to predict outcomes.
- 15+ features (price, volume, time decay, sentiment, category)
- Cross-validated training with synthetic data bootstrap
- Confidence-weighted position sizing

## ⚡ Commands

```bash
# Status & Info
python src/main.py --status          # Platform balances & system health
python src/main.py --match-report    # Cross-platform market matches

# Scanning
python src/main.py --scan dumb_bet   # Run single scanner
python src/main.py --scan arb        # Arbitrage scanner
python src/main.py --scan alpha      # ML alpha scanner
python src/main.py --scan all        # All scanners

# Execution
python src/main.py --scan all --execute  # Scan AND execute trades
python src/main.py --continuous          # 24/7 automated trading

# ML Training
python src/main.py --train           # Train alpha model

# Streaming
python src/main.py --stream          # Real-time WebSocket mode
```

## 🛡️ Risk Management

| Control | Setting | Description |
|---------|---------|-------------|
| Max Daily Drawdown | 5% | Triggers LOCKOUT mode |
| Max Position Size | 2% of equity | Per-market limit |
| Circuit Breaker | Auto | Disables scanners on losses |
| Sentry Mode | 10% drawdown | Hour-long trading pause |

## 🔧 Configuration

Key `.env` settings:

```bash
TRADING_MODE=PAPER           # PAPER or LIVE
KALSHI_API_KEY=xxx          # Your Kalshi credentials
OPENAI_API_KEY=xxx          # For LLM match verification
DISCORD_WEBHOOK_URL=xxx     # Alert notifications
```

## 📈 Performance Tracking

All trades logged to `data/trades.jsonl`:
- Entry/exit prices
- P&L per trade
- Scanner attribution
- Confidence scores

## 🚧 Roadmap

- [ ] Polymarket integration (USDC)
- [ ] Betfair liquidity
- [ ] Advanced sentiment (Twitter, Reddit)
- [ ] Backtesting framework
- [ ] Dashboard visualization
- [ ] Discord bot alerts

## 📜 License

MIT

---

*"I'll be back... with profits."* 🤖
