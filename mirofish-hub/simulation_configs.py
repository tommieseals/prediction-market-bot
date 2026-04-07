"""
Dual-Platform Simulation Configurations for All 5 Projects

Each config maps a real money-making project to a MiroFish simulation
with properly named projects, seed text, and simulation requirements.

All configs use:
  - platform="parallel" (Twitter + Reddit simultaneously)
  - max_rounds=24 (covers full 24-hour agent activity cycle)
  - Zep graph memory enabled (ZEP_API_KEY configured)
"""

from dataclasses import dataclass


@dataclass
class SimulationConfig:
    """Configuration for a single MiroFish dual-platform simulation."""

    # Project identity
    project_key: str                # Internal key (e.g., "terminator")
    project_name: str               # Display name in MiroFish
    real_project: str               # Actual project name
    description: str                # Short description

    # Simulation parameters
    simulation_requirement: str     # What to simulate (drives ontology + agents)
    seed_text_template: str         # Template with {placeholders} for live data
    platform: str = "parallel"      # "twitter", "reddit", or "parallel"
    max_rounds: int = 24            # 24 = full day cycle for agent active_hours
    skip_graph: bool = False        # False = use Zep knowledge graph

    # Agent tuning
    parallel_profile_count: int = 5  # Profiles generated in parallel
    use_llm_for_profiles: bool = True

    # Data source
    data_source: str = ""           # Where to read live data from


# ══════════════════════════════════════════════════════════════════
# 1. TERMINATORBOT — Prediction Market Sentiment
# ══════════════════════════════════════════════════════════════════

TERMINATOR_CONFIG = SimulationConfig(
    project_key="terminator",
    project_name="TerminatorBot: Prediction Market Intelligence",
    real_project="TerminatorBot",
    description="Swarm simulation of prediction market crowd sentiment on Kalshi/Polymarket",
    data_source=r"C:\Users\USER\clawd\TerminatorBot\data\market_cache.db",
    simulation_requirement=(
        "Simulate public discourse about prediction markets where real money is at stake. "
        "Generate diverse agents representing: retail bettors, political junkies, data scientists, "
        "professional traders, news commentators, and contrarian thinkers. "
        "Have them discuss and debate market questions as they would on Twitter and Reddit. "
        "Track how opinions shift during discussion, identify consensus and dissent patterns, "
        "and surface information asymmetries that could indicate mispriced markets."
    ),
    seed_text_template="""PREDICTION MARKET ANALYSIS — TERMINATORBOT
============================================================

Market Question: {title}
Platform: {platform}
Current YES Price: {yes_price} (implied probability: {yes_price_pct}%)
Current NO Price: {no_price}
Trading Volume: ${volume:,.0f}
Category: {category}
Close Date: {close_date}

MARKET CONTEXT:
This is a real prediction market where traders bet real money on outcomes.
The current price reflects the crowd's probability estimate.
When price = 0.50, maximum uncertainty. When near 0 or 1, strong conviction.

SIMULATION OBJECTIVE:
Simulate how different segments of the public — informed citizens, political
commentators, data analysts, casual bettors, and industry experts — would
discuss this question on social media. Model opinion dynamics, information
cascading, and sentiment shifts to predict whether the current market price
accurately reflects true probability, or if there's an edge to exploit.

KEY ANALYSIS POINTS:
- Political leanings and partisan bias effects
- Recent news events and breaking developments
- Historical precedent for similar outcomes
- Social media echo chambers vs. contrarian voices
- Information gaps between retail and institutional participants
- Black swan potential and tail risk scenarios
""",
)


# ══════════════════════════════════════════════════════════════════
# 2. ARBITRAGE PHARMA — Biotech Deal Sentiment
# ══════════════════════════════════════════════════════════════════

PHARMA_CONFIG = SimulationConfig(
    project_key="pharma",
    project_name="Arbitrage Pharma: Biotech Deal Intelligence",
    real_project="Arbitrage Pharma",
    description="Swarm simulation of biotech industry sentiment on distressed orphan drug acquisitions",
    data_source=r"C:\Users\USER\clawd\arbitrage-pharma\data\opportunities.json",
    simulation_requirement=(
        "Simulate professional discourse about distressed biotech assets and orphan drug acquisitions. "
        "Generate diverse agents representing: pharma BD executives, biotech analysts, FDA regulatory "
        "experts, rare disease patient advocates, hedge fund biotech specialists, clinical trial "
        "investigators, and pharma industry journalists. "
        "Have them discuss the viability of acquiring terminated or suspended clinical-stage drugs, "
        "debating acquisition timing, regulatory pathways, competitive landscapes, and deal valuations. "
        "Model how industry sentiment forms around distressed assets and identify contrarian opportunities."
    ),
    seed_text_template="""BIOTECH DEAL INTELLIGENCE — ARBITRAGE PHARMA
============================================================

Asset: {asset_name}
Company: {company}
Indication: {indication}
Phase: {phase}
Trial ID: {trial_id}
Status: {status}
Why Stopped: {why_stopped}

FINANCIAL MODEL:
Market Estimate: ${market_low:,.0f} - ${market_high:,.0f}
Acquisition Cost Estimate: ${acq_low:,.0f} - ${acq_high:,.0f}
Success Probability: {success_prob:.0%}
Probability-Weighted Value: ${weighted_value:,.0f}
Arbitrage Score: {arb_score}/10

COMPETITIVE INTELLIGENCE:
{competitive_intel}

DEAL THESIS:
This is a distressed orphan drug asset that was terminated/suspended by its original
sponsor. The Orphan Drug Act provides 7-year market exclusivity, 50% tax credits on
clinical trials, and FDA fee waivers. If the drug can be acquired cheaply and the
clinical program completed, the potential ROI is 10-100x.

SIMULATION OBJECTIVE:
Model how pharma industry professionals, analysts, and patient advocates would assess
this acquisition opportunity. Identify consensus views on: drug viability, regulatory
risk, competitive threats, optimal deal structure, and fair valuation. Surface blind
spots and contrarian perspectives that could indicate the deal is over/under-valued.

PORTFOLIO CONTEXT:
Pipeline: {pipeline_count} opportunities, ${pipeline_value:,.0f} probability-weighted
Priority: {priority}
Outreach Status: {outreach_status}
""",
)


# ══════════════════════════════════════════════════════════════════
# 3. PROJECT LEGION — Job Market Sentiment
# ══════════════════════════════════════════════════════════════════

LEGION_CONFIG = SimulationConfig(
    project_key="legion",
    project_name="Project Legion: Job Market Intelligence",
    real_project="Project Legion",
    description="Swarm simulation of job market sentiment and hiring trends for automated applications",
    data_source="ssh://tommie@100.88.105.106:~/legion-v3/legion.db",
    simulation_requirement=(
        "Simulate discourse about the current job market, hiring trends, and job search strategies. "
        "Generate diverse agents representing: HR recruiters, hiring managers, job seekers at various "
        "experience levels, career coaches, LinkedIn influencers, tech industry insiders, layoff "
        "survivors, and remote work advocates. "
        "Have them discuss: which industries are hiring, salary expectations, resume optimization, "
        "ATS (Applicant Tracking System) gaming strategies, the effectiveness of mass-applying, "
        "interview preparation tactics, and the impact of AI on hiring. "
        "Model how job market sentiment shifts on social media and identify actionable patterns."
    ),
    seed_text_template="""JOB MARKET INTELLIGENCE — PROJECT LEGION
============================================================

TARGET ROLE: {job_title}
COMPANY: {company}
LOCATION: {location}
SALARY RANGE: {salary_range}
PLATFORM: {platform}
MATCH SCORE: {match_score}/100

APPLICANT PROFILE:
Name: Tommie Seals
Location: Houston, TX
Background: IT Administration, Systems Engineering
Experience: 5+ years enterprise IT
Skills: Python, Linux, Windows Server, Network Admin, Cloud (AWS/Azure)

LEGION SYSTEM STATS:
Total Jobs Discovered: {total_jobs}
Applications Submitted: {total_submitted}
Success Rate: {success_rate:.1%}
Active Pipeline: {pipeline_count} jobs in queue

JOB MARKET CONTEXT:
The job market in {industry} is currently {market_state}. Key trends include:
- {trend_1}
- {trend_2}
- {trend_3}

SIMULATION OBJECTIVE:
Model social media discourse about this specific job opportunity and the broader
hiring landscape in {industry}. Generate insights on: likelihood of interview,
competitive application pool size, salary negotiation leverage, company culture
signals, and red/green flags from the posting. Surface hidden patterns that could
optimize application strategy and timing.
""",
)


# ══════════════════════════════════════════════════════════════════
# 4. PROJECT VAULT — Market Sentiment & Trading Intelligence
# ══════════════════════════════════════════════════════════════════

VAULT_CONFIG = SimulationConfig(
    project_key="vault",
    project_name="Project Vault: Market Sentiment Intelligence",
    real_project="Project Vault",
    description="Swarm simulation of stock market sentiment and crowd psychology for trading signals",
    data_source=r"C:\Users\USER\clawd\project-vault\data\dashboard_backup.json",
    simulation_requirement=(
        "Simulate financial market discourse across retail and professional trading communities. "
        "Generate diverse agents representing: retail traders (WSB-style), institutional analysts, "
        "quant fund managers, financial journalists, permabears, permabulls, technical analysts, "
        "value investors (Buffett school), momentum traders, and options flow watchers. "
        "Have them discuss current market conditions, specific stock positions, macro risks, "
        "sector rotation, and trading strategies. Model how market sentiment cascades through "
        "social media and identify crowd psychology patterns that precede major moves."
    ),
    seed_text_template="""MARKET INTELLIGENCE — PROJECT VAULT
============================================================

PORTFOLIO SNAPSHOT:
Total Equity: ${total_equity:,.2f}
Cash: ${cash:,.2f}
Day P&L: ${day_pnl:,.2f} ({day_pnl_pct:+.2f}%)
Buying Power: ${buying_power:,.2f}

CURRENT POSITIONS:
{positions_text}

ACTIVE STRATEGIES:
- Deep Value (Burry): Screening for EV/EBITDA < 8x + insider buying
- Volatility (Barclays): IV/RV ratio + VIX regime positioning
- Macro Regression (Cowen): Interest rate + inflation factor allocation
- Contrarian (OpenClaw): Fear & Greed extremes + RSI divergence

RISK METRICS:
Kill Switch: {kill_switch_status}
Max Drawdown Limit: 15%
Daily Loss Limit: 3%
Position Concentration Limit: 10% per symbol

MARKET REGIME:
{regime_text}

FOCUS ANALYSIS: {focus_symbol}
Current Price: ${focus_price}
Position Size: {focus_shares} shares
Cost Basis: ${focus_cost:,.2f}
Unrealized P&L: ${focus_pnl:,.2f}

SIMULATION OBJECTIVE:
Simulate social media discourse about {focus_symbol} and the broader market.
Model retail vs. institutional sentiment divergence, identify crowd positioning
extremes, and detect narrative shifts that could signal upcoming price moves.
Surface contrarian opportunities where social media consensus is likely wrong.
""",
)


# ══════════════════════════════════════════════════════════════════
# 5. MONEY MACHINE — Freelance Market Intelligence
# ══════════════════════════════════════════════════════════════════

MONEY_MACHINE_CONFIG = SimulationConfig(
    project_key="money_machine",
    project_name="Money Machine: Freelance Market Intelligence",
    real_project="Money Machine",
    description="Swarm simulation of freelance market demand and pricing intelligence",
    data_source=r"C:\Users\USER\clawd\memory\money-machine-tracker.md",
    simulation_requirement=(
        "Simulate discourse about the freelance economy, gig work, and AI-powered services market. "
        "Generate diverse agents representing: Upwork top-rated freelancers, Fiverr sellers, "
        "startup founders hiring freelancers, agency owners, digital nomads, AI automation "
        "skeptics, career coaches, platform moderators, and corporate outsourcing managers. "
        "Have them discuss: pricing strategies, platform algorithms, client acquisition tactics, "
        "the impact of AI tools on freelance rates, niche market opportunities, and how to "
        "build sustainable freelance income. Model market dynamics and identify underserved "
        "niches with high demand and low competition."
    ),
    seed_text_template="""FREELANCE MARKET INTELLIGENCE — MONEY MACHINE
============================================================

ACTIVE INCOME STREAMS: {stream_count}
TARGET MONTHLY REVENUE: $5,000+
CURRENT STATUS: {current_status}

TOP INCOME STREAM OPPORTUNITIES:
{streams_text}

FIVERR GIGS (READY TO POST):
1. AI-Powered Business Automation — Starting $150
   (Data extraction, chatbots, API integrations, workflow automation)
2. Python Scripts & Data Analysis — Starting $50
   (Web scrapers, data cleaning, ML models, trading bots)
3. Research Reports & Market Analysis — Starting $100
   (Competitor analysis, market sizing, due diligence, lead lists)
4. Trading Bot & Crypto Automation — Starting $300
   (Crypto bots, stock automation, backtesting, risk management)

PLATFORM PRICING INTELLIGENCE:
- Upwork: $50-200/gig for automation, $500-1500 for full projects
- Fiverr: $50-300/gig tiered pricing (Basic/Standard/Premium)
- Direct Clients: $100-500/project, $50-100/hr consulting
- Micro-tasks: $15-30/hr (Scale AI, Outlier, Prolific)

MARKET CONTEXT:
The AI services freelance market is {market_state}. Key trends:
- {trend_1}
- {trend_2}
- {trend_3}

SIMULATION OBJECTIVE:
Model social media discourse about freelance AI services, pricing dynamics,
and client acquisition. Identify: optimal pricing for each service tier,
underserved niches with high demand, platform algorithm gaming strategies,
and emerging opportunities as AI tools reshape the freelance economy.
Surface insights on what services to prioritize for maximum revenue.
""",
)


# ══════════════════════════════════════════════════════════════════
# Registry: All configs in one place
# ══════════════════════════════════════════════════════════════════

ALL_CONFIGS = {
    "terminator": TERMINATOR_CONFIG,
    "pharma": PHARMA_CONFIG,
    "legion": LEGION_CONFIG,
    "vault": VAULT_CONFIG,
    "money_machine": MONEY_MACHINE_CONFIG,
}

# Project name mapping: MiroFish display name → real project
PROJECT_NAME_MAP = {
    "TerminatorBot: Prediction Market Intelligence": "TerminatorBot",
    "Arbitrage Pharma: Biotech Deal Intelligence": "Arbitrage Pharma",
    "Project Legion: Job Market Intelligence": "Project Legion",
    "Project Vault: Market Sentiment Intelligence": "Project Vault",
    "Money Machine: Freelance Market Intelligence": "Money Machine",
}


def get_config(key: str) -> SimulationConfig:
    """Get a simulation config by project key."""
    if key not in ALL_CONFIGS:
        raise KeyError(f"Unknown project key: {key}. Available: {list(ALL_CONFIGS.keys())}")
    return ALL_CONFIGS[key]


def list_configs() -> list[str]:
    """List all available config keys."""
    return list(ALL_CONFIGS.keys())
