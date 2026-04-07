"""
Pharma FDA Approval Prediction Engine → MiroFish Connector

Tracks upcoming FDA PDUFA dates, clinical trial readouts, and
Advisory Committee meetings. Runs 20-agent swarm simulations
with specialized pharma personas to predict approval probability.

4 Trading Strategies:
  1. Pre-PDUFA run-up (buy 2-4 weeks out, sell 1-2 days before)
  2. AdCom panel prediction (position before vote)
  3. CRL short plays (when swarm predicts <40% approval)
  4. Post-approval momentum (continuation after gap-up)

Position Sizing:
  Quarter-Kelly criterion with $5K max per trade, 15% min edge.

Usage:
    python pharma_fda_connector.py                  # Health check + calendar + signals
    python pharma_fda_connector.py --test           # Test simulation on sample catalyst
    python pharma_fda_connector.py --scan           # Simulate top upcoming catalysts
    python pharma_fda_connector.py --scan --top 5   # Simulate top 5
"""

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from mirofish_client import MiroFishClient
from outcome_tracker import OutcomeTracker
from report_parser import extract_consensus_from_report

# ── Paths ────────────────────────────────────────────────────
PREDICTIONS_LOG = Path(__file__).parent / "pharma_fda_predictions.jsonl"
SIGNALS_DB = Path(__file__).parent / "data" / "pharma_signals.db"


# ── Data Models ─────────────────────────────────────────────

@dataclass
class FDACatalyst:
    ticker: str
    company: str
    drug_name: str
    catalyst_type: str        # PDUFA, AdCom, Phase3, Phase2, CRL
    target_date: Optional[str]
    therapeutic_area: str
    significance: str         # Blockbuster, Orphan, Standard
    status: str
    base_approval_prob: float  # Historical base rate for this type
    prior_results: str        # Positive, Mixed, Failed
    priority_review: bool
    market_cap: float
    float_size: str           # Low, Medium, High
    mfg_complexity: str = "Medium"   # Low, Medium, High
    cash_runway_months: int = 24


@dataclass
class PredictionMarket:
    """Live odds from Kalshi/Polymarket (demo data when no API key)."""
    market_id: str
    platform: str
    question: str
    yes_price: float
    volume: float
    bid_ask_spread: float = 0.02


@dataclass
class TradeSignal:
    """Actionable trade recommendation with sizing."""
    ticker: str
    drug: str
    strategy: str          # PRE_PDUFA_RUNUP, ADCOM_PANEL, CRL_SHORT, POST_APPROVAL
    direction: str         # LONG, SHORT
    position_size: float   # Dollar amount (quarter-Kelly)
    kelly_fraction: float
    conviction: float      # 0-1
    model_prob: float      # Our swarm prediction
    market_prob: float     # Market implied
    edge: float            # model - market
    horizon_days: int      # Hold period
    catalyst_date: str
    reasoning: List[str] = field(default_factory=list)


# ── FDA Calendar ────────────────────────────────────────────

# Base rates from historical FDA data:
#   PDUFA with positive Phase 3: ~85% approval
#   PDUFA with mixed Phase 3:   ~55% approval
#   AdCom positive vote:         ~80% → FDA approval
#   Orphan drug (completed P3):  ~90% approval
#   Priority Review:             ~90% approval
#   Standard NDA:                ~75% approval

FDA_CALENDAR: List[FDACatalyst] = [
    FDACatalyst(
        ticker="RCKT", company="Rocket Pharmaceuticals",
        drug_name="KRESLADI (lentiviral gene therapy)",
        catalyst_type="PDUFA", target_date="2026-03-28",
        therapeutic_area="Gene Therapy / LAD-I",
        significance="Orphan", status="PDUFA date set",
        base_approval_prob=0.75, prior_results="Positive",
        priority_review=False, market_cap=450e6, float_size="Low",
        mfg_complexity="High", cash_runway_months=8,
    ),
    FDACatalyst(
        ticker="LNTH", company="Lantheus Holdings",
        drug_name="LNTH-2501 (imaging agent)",
        catalyst_type="PDUFA", target_date="2026-03-29",
        therapeutic_area="Neuroendocrine Tumors / Imaging",
        significance="Blockbuster", status="PDUFA date set",
        base_approval_prob=0.82, prior_results="Positive",
        priority_review=True, market_cap=5.2e9, float_size="Medium",
        mfg_complexity="Medium", cash_runway_months=24,
    ),
    FDACatalyst(
        ticker="MRK", company="Merck",
        drug_name="KEYNOTE-905 (pembrolizumab sBLA)",
        catalyst_type="PDUFA", target_date="2026-04-07",
        therapeutic_area="Oncology / Bladder Cancer",
        significance="Blockbuster", status="Priority Review",
        base_approval_prob=0.68, prior_results="Mixed",
        priority_review=True, market_cap=285e9, float_size="High",
        mfg_complexity="Low", cash_runway_months=48,
    ),
    FDACatalyst(
        ticker="BMY", company="Bristol Myers Squibb",
        drug_name="Opdivo (adjuvant esophageal sBLA)",
        catalyst_type="PDUFA", target_date="2026-04-08",
        therapeutic_area="Oncology / Esophageal Cancer",
        significance="Blockbuster", status="sBLA Priority Review",
        base_approval_prob=0.79, prior_results="Positive",
        priority_review=True, market_cap=118e9, float_size="High",
        mfg_complexity="Low", cash_runway_months=36,
    ),
    FDACatalyst(
        ticker="REPL", company="Replimune Group",
        drug_name="RP1+nivolumab (oncolytic virus)",
        catalyst_type="PDUFA", target_date="2026-04-10",
        therapeutic_area="Oncology / Melanoma",
        significance="Blockbuster", status="BLA submitted",
        base_approval_prob=0.71, prior_results="Positive",
        priority_review=False, market_cap=350e6, float_size="Low",
        mfg_complexity="High", cash_runway_months=11,
    ),
    FDACatalyst(
        ticker="COGT", company="Cogent Biosciences",
        drug_name="bezuclastinib",
        catalyst_type="PDUFA", target_date="2026-12-30",
        therapeutic_area="Systemic Mastocytosis",
        significance="Orphan", status="NDA submitted",
        base_approval_prob=0.65, prior_results="Positive",
        priority_review=False, market_cap=890e6, float_size="Medium",
        mfg_complexity="Medium", cash_runway_months=18,
    ),
    FDACatalyst(
        ticker="NVAX", company="Novavax",
        drug_name="COVID-19 + Flu Combo Vaccine",
        catalyst_type="Phase3", target_date="2026-06-15",
        therapeutic_area="Vaccines / Infectious Disease",
        significance="Blockbuster", status="Phase 3 ongoing",
        base_approval_prob=0.55, prior_results="Mixed",
        priority_review=False, market_cap=1.2e9, float_size="High",
        mfg_complexity="High", cash_runway_months=6,
    ),
    FDACatalyst(
        ticker="ALMS", company="Alumis",
        drug_name="ESK-001 (TYK2 inhibitor)",
        catalyst_type="Phase3", target_date="2026-07-15",
        therapeutic_area="Immunology / Psoriasis",
        significance="Blockbuster", status="Phase 3 ONWARD study",
        base_approval_prob=0.60, prior_results="Positive Phase 2",
        priority_review=False, market_cap=1.8e9, float_size="Medium",
        mfg_complexity="Medium", cash_runway_months=15,
    ),
]


# ── Demo Prediction Markets ────────────────────────────────

DEMO_MARKETS: Dict[str, PredictionMarket] = {
    "RCKT": PredictionMarket(
        market_id="KAL-RCKT-001", platform="Kalshi",
        question="Will KRESLADI receive FDA approval by March 28?",
        yes_price=0.74, volume=89_000, bid_ask_spread=0.02,
    ),
    "LNTH": PredictionMarket(
        market_id="KAL-LNTH-001", platform="Kalshi",
        question="Will LNTH-2501 receive FDA approval?",
        yes_price=0.81, volume=450_000, bid_ask_spread=0.01,
    ),
    "MRK": PredictionMarket(
        market_id="KAL-MRK-001", platform="Kalshi",
        question="Will KEYTRUDA bladder indication get approved?",
        yes_price=0.67, volume=120_000, bid_ask_spread=0.02,
    ),
    "BMY": PredictionMarket(
        market_id="KAL-BMY-001", platform="Kalshi",
        question="Will Opdivo esophageal sBLA get approved?",
        yes_price=0.76, volume=95_000, bid_ask_spread=0.03,
    ),
    "REPL": PredictionMarket(
        market_id="POLY-REPL-001", platform="Polymarket",
        question="Will Replimune RP1 get FDA approval by April 10?",
        yes_price=0.72, volume=230_000, bid_ask_spread=0.02,
    ),
}


def get_market(ticker: str) -> Optional[PredictionMarket]:
    """Get prediction market data. Uses demo data; plug in API later."""
    return DEMO_MARKETS.get(ticker)


# ── Helpers ─────────────────────────────────────────────────

def get_upcoming_catalysts(days_ahead: int = 45) -> List[FDACatalyst]:
    """Return catalysts within the next N days, sorted by date."""
    now = datetime.now()
    upcoming = []
    for c in FDA_CALENDAR:
        if not c.target_date:
            continue
        try:
            dt = datetime.strptime(c.target_date, "%Y-%m-%d")
        except ValueError:
            continue
        if now <= dt <= now + timedelta(days=days_ahead):
            upcoming.append(c)
    upcoming.sort(key=lambda x: x.target_date or "9999")
    return upcoming


def days_until(date_str: Optional[str]) -> int:
    if not date_str:
        return 999
    try:
        return max(0, (datetime.strptime(date_str, "%Y-%m-%d") - datetime.now()).days)
    except ValueError:
        return 999


# ── Kelly Criterion Position Sizing ─────────────────────────

MIN_EDGE = 0.15         # 15% minimum edge to trade
MAX_POSITION = 5000     # $5K max per trade
KELLY_DIVISOR = 4       # Quarter-Kelly (conservative)
BANKROLL = 10_000       # Default bankroll


def kelly_size(model_prob: float, market_prob: float,
               bankroll: float = BANKROLL) -> Tuple[float, float]:
    """
    Kelly Criterion for binary bets.
    Returns (kelly_fraction, dollar_size).
    """
    edge = model_prob - market_prob
    if edge <= 0:
        return 0.0, 0.0

    # Kelly: f* = (b*p - q) / b  where b=decimal odds, p=win prob, q=loss prob
    b = (1 - market_prob) / market_prob if market_prob > 0 else 0
    if b <= 0:
        return 0.0, 0.0

    p = model_prob
    q = 1 - p
    kelly = (b * p - q) / b

    # Quarter-Kelly for safety
    kelly_conservative = max(0, kelly / KELLY_DIVISOR)
    dollar = min(kelly_conservative * bankroll, MAX_POSITION)

    return round(kelly_conservative, 4), round(dollar, 2)


# ── Strategy Selection ──────────────────────────────────────

def select_strategy(catalyst: FDACatalyst, model_prob: float,
                    market_prob: float) -> Optional[TradeSignal]:
    """
    Select strategy and generate trade signal.
    Returns None if no trade (edge too small or bad timing).
    """
    d = days_until(catalyst.target_date)
    edge = model_prob - market_prob

    # Must have minimum edge
    if abs(edge) < MIN_EDGE:
        return None

    reasoning: List[str] = []

    # ── Strategy 1: PRE-PDUFA RUN-UP (14-28 days out, positive edge) ──
    if catalyst.catalyst_type == "PDUFA" and 14 <= d <= 28 and edge > 0:
        kf, size = kelly_size(model_prob, market_prob)
        if size < 100:
            return None

        if catalyst.significance == "Orphan":
            reasoning.append("Orphan drug — 90%+ historical approval rate")
        if catalyst.priority_review:
            reasoning.append("Priority Review — expedited FDA timeline")
        if catalyst.prior_results == "Positive":
            reasoning.append("Strong prior Phase 3 data")
        if catalyst.mfg_complexity == "High":
            reasoning.append("[WARN] Complex manufacturing (CMC risk — 30% of CRLs)")
        if catalyst.cash_runway_months < 12:
            reasoning.append("[WARN] Limited cash runway — financing risk")

        return TradeSignal(
            ticker=catalyst.ticker, drug=catalyst.drug_name,
            strategy="PRE_PDUFA_RUNUP", direction="LONG",
            position_size=size, kelly_fraction=kf,
            conviction=min(edge * 4, 1.0),
            model_prob=model_prob, market_prob=market_prob, edge=edge,
            horizon_days=min(d - 2, 14),  # Exit 2 days before PDUFA
            catalyst_date=catalyst.target_date or "",
            reasoning=reasoning,
        )

    # ── Strategy 2: LATE ENTRY (2-13 days out, positive edge) ──
    if catalyst.catalyst_type == "PDUFA" and 2 < d < 14 and edge > 0.10:
        kf, size = kelly_size(model_prob, market_prob)
        # Halve size for late entries (less time for thesis to play out)
        size = min(size * 0.5, MAX_POSITION)
        if size < 100:
            return None

        reasoning.append("Late entry — smaller position, exit T-1")
        if catalyst.priority_review:
            reasoning.append("Priority Review increases approval likelihood")

        return TradeSignal(
            ticker=catalyst.ticker, drug=catalyst.drug_name,
            strategy="LATE_ENTRY", direction="LONG",
            position_size=size, kelly_fraction=kf * 0.5,
            conviction=min(edge * 3, 0.8),
            model_prob=model_prob, market_prob=market_prob, edge=edge,
            horizon_days=d - 1,
            catalyst_date=catalyst.target_date or "",
            reasoning=reasoning,
        )

    # ── Strategy 3: CRL SHORT (negative edge — market too optimistic) ──
    if catalyst.catalyst_type == "PDUFA" and edge < -MIN_EDGE and d <= 28:
        inv_edge = -edge  # Edge is positive from short perspective
        kf, size = kelly_size(1 - model_prob, 1 - market_prob)
        if size < 100:
            return None

        reasoning.append(f"Market at {market_prob:.0%} vs model {model_prob:.0%} — overpriced")
        if catalyst.mfg_complexity == "High":
            reasoning.append("Complex manufacturing = higher CRL risk")
        if catalyst.prior_results == "Mixed":
            reasoning.append("Mixed Phase data — approval far from certain")
        if catalyst.cash_runway_months < 12:
            reasoning.append("Limited cash — CRL could trigger death spiral")

        return TradeSignal(
            ticker=catalyst.ticker, drug=catalyst.drug_name,
            strategy="CRL_SHORT", direction="SHORT",
            position_size=size, kelly_fraction=kf,
            conviction=min(inv_edge * 4, 1.0),
            model_prob=model_prob, market_prob=market_prob, edge=edge,
            horizon_days=min(d, 14),
            catalyst_date=catalyst.target_date or "",
            reasoning=reasoning,
        )

    # ── Strategy 4: ADCOM PLAY (5-10 days before advisory committee) ──
    if catalyst.catalyst_type == "AdCom" and 5 <= d <= 10:
        kf, size = kelly_size(
            model_prob if edge > 0 else 1 - model_prob,
            market_prob if edge > 0 else 1 - market_prob,
        )
        if size < 100:
            return None

        reasoning.append("AdCom panel — 80% of positive votes → FDA approval")
        direction = "LONG" if edge > 0 else "SHORT"

        return TradeSignal(
            ticker=catalyst.ticker, drug=catalyst.drug_name,
            strategy="ADCOM_PANEL", direction=direction,
            position_size=size, kelly_fraction=kf,
            conviction=min(abs(edge) * 4, 1.0),
            model_prob=model_prob, market_prob=market_prob, edge=edge,
            horizon_days=d + 1,  # Exit day after panel vote
            catalyst_date=catalyst.target_date or "",
            reasoning=reasoning,
        )

    return None


def recommend_strategy_text(catalyst: FDACatalyst) -> str:
    """Human-readable strategy recommendation (no market data needed)."""
    d = days_until(catalyst.target_date)

    if catalyst.catalyst_type == "PDUFA":
        if catalyst.base_approval_prob >= 0.75:
            if d > 14:
                return "PRE-PDUFA RUN-UP: Buy now, sell T-2 (avoid binary)"
            elif d > 2:
                return "LATE ENTRY: Smaller position, sell T-1"
            else:
                return "BINARY BET: Full risk, approval likely"
        elif catalyst.base_approval_prob >= 0.55:
            return "COIN FLIP: Straddle/strangle if options available"
        else:
            return "CRL SHORT: Buy NO / short equity on pops"
    elif catalyst.catalyst_type == "AdCom":
        return "ADCOM PLAY: Position T-7, exit post-vote (vol crush)"
    elif catalyst.catalyst_type == "Phase3":
        if "Positive" in catalyst.prior_results:
            return "READOUT MOMENTUM: Small position, ride positive readout"
        return "AVOID: Phase 3 readouts are pure binary with no edge"
    return "MONITOR"


# ── Seed Text Builder ───────────────────────────────────────

FDA_SEED_TEMPLATE = """BIOTECH FDA APPROVAL ANALYSIS — {timestamp}
============================================================

CATALYST PROFILE:
  Ticker: ${ticker}
  Company: {company}
  Drug: {drug_name}
  Therapeutic Area: {therapeutic_area}
  Significance: {significance} {sig_note}

REGULATORY STATUS:
  Event: {catalyst_type}
  Target Date: {target_date} ({days_to} days away) — {urgency}
  Priority Review: {priority_review_text}
  Current Status: {status}

CLINICAL BACKGROUND:
  Prior Phase Results: {prior_results}
  Base Approval Rate (historical): {base_prob:.0%}

COMPANY PROFILE:
  Market Cap: ${market_cap_str}
  Float: {float_size}
  Manufacturing Complexity: {mfg_complexity}
  Cash Runway: {cash_runway} months
  Volatility Profile: {vol_profile}

{market_section}

AGENT ROSTER (20 FDA Approval Specialists):
  1. Regulatory Affairs Expert (FDA veteran) — submission quality, CMC
  2. Clinical Trial Statistician — p-values, endpoint significance
  3. Medical Reviewer (former FDA) — safety/benefit assessment
  4. Pharma Market Analyst — commercial potential, pricing
  5. Biotech Options Trader — implied vol, institutional flow
  6. Short Seller Specialist — CRL patterns, red flags
  7. Scientific KOL — mechanism of action, innovation
  8. AdCom Panel Simulator — voting patterns, panel composition
  9. Manufacturing/QC Expert — CMC issues (30% of CRLs)
  10. Patient Advocacy Rep — unmet need, disease severity
  11. Healthcare Policy Analyst — FDA leadership priorities
  12. Competitive Intelligence — pipeline competitors, me-too risk
  13. Investigational Site Manager — enrollment, protocol deviations
  14. Biotech Investment Banker — M&A, cash runway, dilution
  15. EU Regulatory Consultant — EMA precedent, global trends
  16. Pharmacovigilance Expert — post-marketing safety, REMS
  17. Gene/Cell Therapy Specialist — durability, manufacturing
  18. Oncology Trial Specialist — PFS vs OS, accelerated approval
  19. Rare Disease Expert — orphan incentives, small trials
  20. Risk Aggregator — portfolio construction, hedge sizing

PREDICTION QUESTION:
  Will {drug_name} by {company} receive FDA approval by {target_date}?

SIMULATION INSTRUCTIONS:
  Agents debate this FDA approval decision across Twitter and Reddit.
  Track consensus: what %% of agents predict approval vs CRL?
  Surface key risk factors and information asymmetries.
  Final output: approval probability with confidence interval.
"""


def build_seed_text(catalyst: FDACatalyst) -> str:
    """Build enriched seed text for FDA simulation."""
    d = days_until(catalyst.target_date)

    if d < 7:
        urgency = "IMMEDIATE — within 1 week"
    elif d < 14:
        urgency = "NEAR-TERM — within 2 weeks"
    elif d < 30:
        urgency = "UPCOMING — within 1 month"
    else:
        urgency = f"SCHEDULED — {d} days out"

    if catalyst.significance == "Blockbuster":
        sig_note = "(High revenue potential, major market impact)"
    elif catalyst.significance == "Orphan":
        sig_note = "(Orphan drug — 90%+ historical approval rate if P3 completes)"
    else:
        sig_note = ""

    if catalyst.float_size == "Low" and catalyst.market_cap < 1e9:
        vol_profile = "HIGH VOL — small cap, 50-200% binary moves typical"
    elif catalyst.float_size == "Medium":
        vol_profile = "MODERATE VOL — 20-50% moves on binary events"
    else:
        vol_profile = "LARGE CAP — 5-15% moves, lower beta"

    if catalyst.market_cap >= 1e9:
        mc_str = f"{catalyst.market_cap / 1e9:.1f}B"
    else:
        mc_str = f"{catalyst.market_cap / 1e6:.0f}M"

    # Market section (if we have prediction market data)
    market = get_market(catalyst.ticker)
    if market:
        market_section = (
            f"PREDICTION MARKET DATA:\n"
            f"  Platform: {market.platform}\n"
            f"  Question: \"{market.question}\"\n"
            f"  Current Odds: {market.yes_price:.0%} YES / "
            f"{1 - market.yes_price:.0%} NO\n"
            f"  Volume (24h): ${market.volume:,.0f}\n"
            f"  Bid-Ask Spread: {market.bid_ask_spread:.1%}"
        )
    else:
        market_section = "PREDICTION MARKET DATA: Not available"

    return FDA_SEED_TEMPLATE.format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        ticker=catalyst.ticker,
        company=catalyst.company,
        drug_name=catalyst.drug_name,
        therapeutic_area=catalyst.therapeutic_area,
        significance=catalyst.significance,
        sig_note=sig_note,
        catalyst_type=catalyst.catalyst_type,
        target_date=catalyst.target_date or "TBD",
        days_to=d,
        urgency=urgency,
        priority_review_text=(
            "YES — FDA fast-track 6-month review" if catalyst.priority_review
            else "Standard 10-month review"
        ),
        status=catalyst.status,
        prior_results=catalyst.prior_results,
        base_prob=catalyst.base_approval_prob,
        market_cap_str=mc_str,
        float_size=catalyst.float_size,
        mfg_complexity=catalyst.mfg_complexity,
        cash_runway=catalyst.cash_runway_months,
        vol_profile=vol_profile,
        market_section=market_section,
    )


FDA_SIM_REQUIREMENT = (
    "Simulate expert biotech discourse about the FDA approval decision: "
    "'{question}'. Generate 20 specialized pharma agents including "
    "regulatory affairs experts, clinical statisticians, FDA medical "
    "reviewers, biotech options traders, short sellers, scientific KOLs, "
    "and AdCom panel simulators. Have them debate on Twitter and Reddit "
    "simultaneously, tracking consensus on approval probability vs CRL risk."
)


# ── Trade Signal Persistence ───────────────────────────────

def _init_signals_db():
    """Create trade signals table."""
    Path(SIGNALS_DB).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(SIGNALS_DB)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_signals (
                signal_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                drug TEXT,
                strategy TEXT,
                direction TEXT,
                position_size REAL,
                kelly_fraction REAL,
                conviction REAL,
                model_prob REAL,
                market_prob REAL,
                edge REAL,
                horizon_days INTEGER,
                catalyst_date TEXT,
                reasoning TEXT,
                simulation_id TEXT,
                status TEXT DEFAULT 'ACTIVE',
                pnl REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                resolved_at TEXT
            )
        """)
        conn.commit()


def persist_signal(signal: TradeSignal, simulation_id: str = "") -> str:
    """Save trade signal to database. Returns signal_id."""
    _init_signals_db()
    signal_id = f"{signal.ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    with sqlite3.connect(str(SIGNALS_DB)) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO trade_signals
            (signal_id, ticker, drug, strategy, direction, position_size,
             kelly_fraction, conviction, model_prob, market_prob, edge,
             horizon_days, catalyst_date, reasoning, simulation_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
            """,
            (
                signal_id, signal.ticker, signal.drug, signal.strategy,
                signal.direction, signal.position_size, signal.kelly_fraction,
                signal.conviction, signal.model_prob, signal.market_prob,
                signal.edge, signal.horizon_days, signal.catalyst_date,
                json.dumps(signal.reasoning), simulation_id,
            ),
        )
        conn.commit()
    return signal_id


def get_active_signals() -> List[Dict]:
    """Get all active trade signals."""
    _init_signals_db()
    with sqlite3.connect(str(SIGNALS_DB)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM trade_signals WHERE status = 'ACTIVE' "
            "ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ── Simulation ──────────────────────────────────────────────

def simulate_catalyst(
    client: MiroFishClient,
    catalyst: FDACatalyst,
    max_rounds: int = 24,
    skip_graph: bool = False,
) -> Dict:
    """Run MiroFish simulation for an FDA catalyst."""
    seed_text = build_seed_text(catalyst)
    question = (
        f"Will {catalyst.drug_name} by {catalyst.company} "
        f"receive FDA approval by {catalyst.target_date}?"
    )
    sim_req = FDA_SIM_REQUIREMENT.format(question=question[:200])

    d = days_until(catalyst.target_date)
    market = get_market(catalyst.ticker)

    print(f"\n  Simulating: ${catalyst.ticker} — {catalyst.drug_name}")
    print(f"  {catalyst.catalyst_type} on {catalyst.target_date} ({d} days)")
    print(f"  Base rate: {catalyst.base_approval_prob:.0%} | "
          f"Prior: {catalyst.prior_results} | "
          f"Priority: {'YES' if catalyst.priority_review else 'NO'}")
    if market:
        print(f"  Market odds: {market.yes_price:.0%} YES "
              f"(${market.volume:,.0f} vol on {market.platform})")

    result = client.run_dual_platform(
        simulation_requirement=sim_req,
        seed_text=seed_text,
        project_name=f"FDA: {catalyst.ticker} {catalyst.drug_name[:30]}",
        max_rounds=max_rounds,
        skip_graph=skip_graph,
    )

    prediction = {
        "connector": "pharma_fda",
        "ticker": catalyst.ticker,
        "company": catalyst.company,
        "drug_name": catalyst.drug_name,
        "catalyst_type": catalyst.catalyst_type,
        "target_date": catalyst.target_date,
        "therapeutic_area": catalyst.therapeutic_area,
        "significance": catalyst.significance,
        "base_approval_prob": catalyst.base_approval_prob,
        "prior_results": catalyst.prior_results,
        "priority_review": catalyst.priority_review,
        "market_cap": catalyst.market_cap,
        "mfg_complexity": catalyst.mfg_complexity,
        "cash_runway_months": catalyst.cash_runway_months,
        "days_to_catalyst": d,
        "market_implied": market.yes_price if market else None,
        "simulation_id": result.get("simulation_id"),
        "project_id": result.get("project_id"),
        "report_id": result.get("report_id"),
        "steps": result.get("steps"),
        "timestamp": datetime.now().isoformat(),
    }

    # Generate trade signal if we have market data
    if market:
        # Extract swarm consensus from report (replaces base_approval_prob)
        report_id = result.get("report_id")
        model_prob = catalyst.base_approval_prob  # Fallback
        risk_adjustment = 0.0
        consensus_data = {}
        
        if report_id:
            consensus_data = extract_consensus_from_report(report_id)
            if consensus_data.get("consensus_probability") is not None:
                model_prob = consensus_data["consensus_probability"] / 100.0  # Convert to 0-1
                print(f"\n  [AI] Swarm Consensus: {model_prob:.0%}")
                ci = consensus_data.get('confidence_interval', (None, None))
                if ci[0] is not None:
                    print(f"     Confidence Interval: {ci[0]:.0f}% - {ci[1]:.0f}%")
                    print(f"     Spread: {consensus_data.get('confidence_spread', 'N/A')}")
                
                # Apply risk adjustments
                risk_flags = consensus_data.get("risk_flags", [])
                if risk_flags:
                    print(f"     [WARN] Risk Flags: {', '.join(risk_flags)}")
                    # Haircut for each major risk
                    if consensus_data.get("has_cmc_risk"):
                        risk_adjustment -= 0.03  # -3% for manufacturing risk
                    if consensus_data.get("has_safety_risk"):
                        risk_adjustment -= 0.05  # -5% for safety concerns
                    if risk_adjustment != 0:
                        print(f"     📉 Risk Adjustment: {risk_adjustment:+.0%}")
                        model_prob = max(0.1, model_prob + risk_adjustment)
                        print(f"     Adjusted Model: {model_prob:.0%}")
            else:
                print(f"\n  [WARN] Report parsing failed, using base rate: {model_prob:.0%}")
        
        prediction["swarm_consensus"] = consensus_data
        
        signal = select_strategy(
            catalyst, model_prob, market.yes_price
        )
        if signal:
            sig_id = persist_signal(signal, result.get("simulation_id", ""))
            prediction["trade_signal"] = asdict(signal)
            prediction["signal_id"] = sig_id
            print(f"\n  [STATS] TRADE SIGNAL: {signal.direction} ${catalyst.ticker}")
            print(f"     Strategy: {signal.strategy}")
            print(f"     Size: ${signal.position_size:,.0f} "
                  f"(Kelly: {signal.kelly_fraction:.1%})")
            print(f"     Edge: {signal.edge:+.0%} "
                  f"(Model {signal.model_prob:.0%} vs "
                  f"Market {signal.market_prob:.0%})")
            print(f"     Horizon: {signal.horizon_days}d | "
                  f"Conviction: {signal.conviction:.0%}")
            for r in signal.reasoning:
                print(f"     • {r}")
        else:
            print(f"\n  No trade — edge < {MIN_EDGE:.0%} or bad timing")

    return prediction


def log_prediction(prediction: Dict) -> None:
    """Append prediction to JSONL log."""
    with open(PREDICTIONS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(prediction, ensure_ascii=False, default=str) + "\n")
    print(f"  Logged to {PREDICTIONS_LOG}")


# ── Commands ────────────────────────────────────────────────

def cmd_health(client: MiroFishClient) -> None:
    """Health check + show FDA calendar + active signals."""
    print("=== Pharma FDA Prediction Engine v2 — Status ===\n")

    # MiroFish
    if client.health_check():
        print("MiroFish: ONLINE")
    else:
        print("MiroFish: OFFLINE")

    # FDA Calendar
    print(f"\nFDA Calendar ({len(FDA_CALENDAR)} tracked catalysts):")
    print(f"{'─' * 80}")

    upcoming = get_upcoming_catalysts(days_ahead=90)
    if not upcoming:
        print("  No catalysts in next 90 days")
        upcoming = FDA_CALENDAR[:5]
        print(f"  Showing next {len(upcoming)} catalysts:")

    for c in upcoming:
        d = days_until(c.target_date)
        flag = "[RED]" if d < 7 else "[YELLOW]" if d < 14 else "[GREEN]"
        strat = recommend_strategy_text(c)
        market = get_market(c.ticker)

        print(f"\n  {flag} ${c.ticker} — {c.drug_name}")
        print(f"     {c.catalyst_type} on {c.target_date} ({d}d) | "
              f"Base: {c.base_approval_prob:.0%} | {c.significance}")
        if market:
            edge = c.base_approval_prob - market.yes_price
            edge_icon = "[TARGET]" if abs(edge) > MIN_EDGE else "  "
            print(f"     Market: {market.yes_price:.0%} ({market.platform}) | "
                  f"Edge: {edge:+.0%} {edge_icon}")
        print(f"     Strategy: {strat}")

    # Active signals
    signals = get_active_signals()
    if signals:
        print(f"\n{'─' * 80}")
        print(f"Active Trade Signals ({len(signals)}):")
        for s in signals:
            print(f"  {s['direction']} ${s['ticker']} | "
                  f"{s['strategy']} | "
                  f"${s['position_size']:,.0f} | "
                  f"Edge: {s['edge']:+.0%}")

    # Outcomes
    print(f"\n{'─' * 80}")
    tracker = OutcomeTracker()
    print(tracker.summary())


def cmd_test(client: MiroFishClient) -> None:
    """Run test simulation on nearest catalyst."""
    print("Running FDA test simulation...\n")

    test_catalyst = FDA_CALENDAR[0]
    prediction = simulate_catalyst(
        client, test_catalyst, max_rounds=5, skip_graph=True,
    )
    log_prediction(prediction)

    tracker = OutcomeTracker()
    tracker.record_prediction(
        prediction_id=prediction.get("simulation_id", "fda_test"),
        market_id=f"{test_catalyst.ticker}_{test_catalyst.catalyst_type}",
        connector="pharma_fda",
        market_title=f"{test_catalyst.drug_name} FDA Approval",
        predicted_probability=test_catalyst.base_approval_prob,
        market_price=test_catalyst.base_approval_prob,
        model_version="pharma_fda_v2_test",
        agent_count=5,
        metadata=asdict(test_catalyst),
    )

    print("\nTest complete!")
    print(json.dumps(prediction, indent=2, default=str))


def cmd_scan(client: MiroFishClient, top_n: int = 3) -> None:
    """Simulate top upcoming FDA catalysts."""
    upcoming = get_upcoming_catalysts(days_ahead=90)
    if not upcoming:
        upcoming = sorted(FDA_CALENDAR, key=lambda c: c.target_date or "9999")

    targets = upcoming[:top_n]
    print(f"Simulating {len(targets)} FDA catalysts...\n")

    tracker = OutcomeTracker()
    signals_generated = 0

    for i, catalyst in enumerate(targets, 1):
        d = days_until(catalyst.target_date)
        print(f"{'=' * 60}")
        print(f"Catalyst {i}/{len(targets)}: ${catalyst.ticker} — "
              f"{catalyst.drug_name}")
        print(f"  {catalyst.catalyst_type} in {d} days | "
              f"Base: {catalyst.base_approval_prob:.0%} | "
              f"Strategy: {recommend_strategy_text(catalyst)}")

        try:
            prediction = simulate_catalyst(
                client, catalyst, skip_graph=False,
            )
            log_prediction(prediction)

            if prediction.get("trade_signal"):
                signals_generated += 1

            tracker.record_prediction(
                prediction_id=prediction.get("simulation_id", f"fda_{i}"),
                market_id=f"{catalyst.ticker}_{catalyst.catalyst_type}",
                connector="pharma_fda",
                market_title=f"{catalyst.drug_name} FDA Approval",
                predicted_probability=catalyst.base_approval_prob,
                market_price=catalyst.base_approval_prob,
                model_version="pharma_fda_v2",
                agent_count=20,
                metadata=asdict(catalyst),
            )
        except Exception as e:
            print(f"  FAILED: {e}")

    print(f"\n{'=' * 60}")
    print(f"Done! {len(targets)} catalysts simulated, "
          f"{signals_generated} trade signals generated.")
    print(f"Predictions: {PREDICTIONS_LOG}")
    print(f"\n{tracker.summary()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pharma FDA Prediction Engine v2 → MiroFish Connector"
    )
    parser.add_argument("--test", action="store_true",
                        help="Test simulation on sample catalyst")
    parser.add_argument("--scan", action="store_true",
                        help="Simulate top upcoming FDA catalysts")
    parser.add_argument("--url", default="http://localhost:5001",
                        help="MiroFish URL")
    parser.add_argument("--api-key", default=None, help="MiroFish API key")
    parser.add_argument("--top", type=int, default=3, help="Number of catalysts")
    args = parser.parse_args()

    client = MiroFishClient(
        base_url=args.url, api_key=args.api_key,
        poll_timeout=1800, request_timeout=300,
    )

    if args.test:
        cmd_test(client)
    elif args.scan:
        cmd_scan(client, top_n=args.top)
    else:
        cmd_health(client)
