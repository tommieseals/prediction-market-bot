#!/usr/bin/env python3
"""
MiroFish Report Parser - Extract consensus probability from swarm reports.

Parses full_report.md and meta.json to extract:
1. Explicit probability mentions (e.g., "90%", "75% likelihood")
2. Sentiment signals from agent quotes
3. Risk factors (CMC, safety, financing)
4. Confidence spread (agreement vs disagreement)

Usage:
    python report_parser.py <report_id>
    python report_parser.py report_bdb4ae63cf03
"""

import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# MiroFish reports directory
REPORTS_DIR = Path(r"C:\Users\USER\Desktop\mirofish-secure\backend\uploads\reports")

@dataclass
class AgentSignal:
    """Signal extracted from an agent's statement."""
    agent_type: str
    stance: str  # bullish, bearish, neutral
    probability: Optional[float]  # If explicit number mentioned
    confidence: float  # How strong the statement is (0-1)
    risk_flags: List[str] = field(default_factory=list)

@dataclass
class ParsedReport:
    """Parsed MiroFish report with extracted probability."""
    report_id: str
    simulation_id: str
    ticker: str
    drug: str
    
    # Core outputs
    consensus_probability: float  # 0-100%
    confidence_interval: Tuple[float, float]  # (low, high)
    confidence_spread: float  # How much disagreement (0-1, lower = more consensus)
    
    # Agent breakdown
    bullish_count: int
    bearish_count: int
    neutral_count: int
    agent_signals: List[AgentSignal] = field(default_factory=list)
    
    # Risk factors
    risk_flags: List[str] = field(default_factory=list)
    
    # Raw data
    explicit_probabilities: List[float] = field(default_factory=list)
    
    def edge_vs_market(self, market_price: float) -> float:
        """Calculate edge vs prediction market price."""
        return self.consensus_probability - market_price


# Agent weight mapping — market-type-aware
# Default (pharma): regulatory experts matter more
PHARMA_AGENT_WEIGHTS = {
    'MedicalReviewer': 1.5,
    'RegulatoryAffairsExpert': 1.5,
    'AdComPanelSimulator': 1.4,
    'ClinicalStatistician': 1.3,
    'ScientificKOL': 1.2,
    'PharmaAnalyst': 1.1,
    'BiotechTrader': 1.0,
    'ShortSeller': 0.9,
    'Person': 0.8,
    'Organization': 0.8,
}

SPORTS_AGENT_WEIGHTS = {
    'QuantitativeAnalyst': 1.5,
    'MarketMicrostructureExpert': 1.4,
    'InstitutionalFlowAnalyst': 1.3,
    'WhaleBehaviorAnalyst': 1.3,
    'RiskManager': 1.2,
    'PredictionMarketResearcher': 1.1,
    'ContrarianTrader': 0.9,   # Useful but often wrong on sports
    'RetailSentimentTracker': 0.7,
    'Person': 0.9,
    'Organization': 0.9,
}

POLITICS_AGENT_WEIGHTS = {
    'PredictionMarketResearcher': 1.5,
    'InstitutionalFlowAnalyst': 1.4,
    'QuantitativeAnalyst': 1.3,
    'ContrarianTrader': 1.1,   # More useful in politics (contrarian edges)
    'RiskManager': 1.0,
    'WhaleBehaviorAnalyst': 1.0,
    'RetailSentimentTracker': 0.8,
    'Person': 0.9,
    'Organization': 0.9,
}

CRYPTO_AGENT_WEIGHTS = {
    'BlockchainAnalyst': 1.5,
    'QuantitativeAnalyst': 1.4,
    'WhaleBehaviorAnalyst': 1.3,
    'MarketMaker': 1.2,
    'ContrarianTrader': 1.0,
    'RetailSentimentTracker': 0.9,
    'Person': 0.8,
    'Organization': 0.8,
}

# Market type → weights map
MARKET_AGENT_WEIGHTS = {
    'pharma': PHARMA_AGENT_WEIGHTS,
    'sports': SPORTS_AGENT_WEIGHTS,
    'soccer': SPORTS_AGENT_WEIGHTS,
    'esports': SPORTS_AGENT_WEIGHTS,
    'politics': POLITICS_AGENT_WEIGHTS,
    'crypto': CRYPTO_AGENT_WEIGHTS,
    'macro': POLITICS_AGENT_WEIGHTS,
    'culture': POLITICS_AGENT_WEIGHTS,
}

# Default — used when market_type is unknown or 'other'
AGENT_WEIGHTS = PHARMA_AGENT_WEIGHTS


def get_agent_weights(market_type: str = "pharma") -> dict:
    """Get agent weights for a given market type."""
    return MARKET_AGENT_WEIGHTS.get(market_type, PHARMA_AGENT_WEIGHTS)

# Probability extraction patterns
PROBABILITY_PATTERNS = [
    r'(\d{1,3})%\s*(?:approval|likelihood|probability|chance|rate)',
    r'(?:approval|likelihood|probability|chance|rate)\s*(?:of\s+)?(\d{1,3})%',
    r'(\d{1,3})%以上',  # Chinese: "90%以上" = "90% or above"
    r'(\d{1,3})%的',    # Chinese: "90%的" = "90% of"
    r'(\d{1,3})%.*?审批',  # Chinese: "90%...审批" = "90%...approval"
    r'审批率.*?(\d{1,3})%',  # Chinese: "审批率...90%"
    r'(\d{1,3})\s*percent',
    r'(\d{1,3})%',  # Catch-all: any percentage (filtered later for context)
]

# Chinese qualitative probability phrases → approximate numeric ranges
# These map qualitative Chinese expressions to probability estimates
CHINESE_PROB_PHRASES = [
    # Very high probability (85-95%)
    (r'可能性(?:很|非常|极)(?:大|高)', 90.0),
    (r'获(?:得|批).*?可能性较高', 85.0),
    (r'较高的获批(?:可能性|概率)', 85.0),
    (r'有较高的获批', 85.0),
    (r'批准的可能性(?:很大|较高)', 85.0),
    (r'获得FDA批准的可能性较高', 85.0),
    (r'审批.*?可能性较高', 85.0),
    (r'前景.*?(?:乐观|积极)', 80.0),
    # Moderate probability (60-75%)
    (r'可能性(?:一般|中等)', 60.0),
    (r'有一定的.*?可能', 55.0),
    # Low probability (20-40%)
    (r'可能性(?:较低|不大|很小)', 25.0),
    (r'不太可能', 25.0),
]

# Bullish signals
BULLISH_KEYWORDS = [
    'approve', 'approval', 'likely', 'positive', 'strong', 'favorable',
    'optimistic', 'confident', 'success', 'breakthrough', 'innovative',
    'promising', 'significant', 'effective', 'efficacy', 'benefit',
    '批准', '可能性较高', '很大', '积极', '乐观', '成功', '突破',  # Chinese bullish
    '显著疗效', '有效性', '认可', '支持', '获批', '前景',          # More Chinese bullish
    '表现出色', '达到了预期', '良好的安全性', '良好的有效性',
    '符合.*标准', '数据支持', '出色',
]

# Bearish signals
BEARISH_KEYWORDS = [
    'reject', 'crl', 'delay', 'concern', 'fail', 'negative',
    'skeptic', 'doubt', 'unlikely', 'caution', 'warning',
    'adverse', 'toxicity', 'side effect',
    '拒绝', '担忧', '下跌', '谨慎', '怀疑',  # Chinese bearish
    '不良反应', '延迟审批', '拒绝批准', '股价大幅下跌',
]

# Note: '风险' and '安全性' removed from bearish - they appear in neutral/positive
# contexts too often (e.g., "安全性评估通过" = safety evaluation passed)
# Instead, only flag them as risk_flags (below), not sentiment bearish

# Risk flag patterns (these indicate risk TOPICS, not necessarily bearish sentiment)
RISK_PATTERNS = {
    'cmc': r'CMC|manufacturing|production|quality\s+control|制造|生产|质量控制',
    'safety': r'safety\s+concern|adverse\s+event|side\s+effect|toxicity|不良反应|毒性|安全性(?:问题|担忧|风险)',
    'efficacy': r'efficacy\s+concern|weak\s+data|疗效(?:不足|问题)',
    'financing': r'cash\s+runway|dilution|financing|融资|稀释|现金跑道',
    'regulatory': r'complete\s+response|CRL|delay|延迟审批|拒绝',
}


def extract_probabilities(text: str) -> List[float]:
    """Extract all explicit probability mentions from text."""
    probabilities = []
    for pattern in PROBABILITY_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                prob = float(match)
                if 1 <= prob <= 99:  # Skip 0% and 100% (usually not real probs)
                    probabilities.append(prob)
            except ValueError:
                continue
    return probabilities


def extract_chinese_qualitative_probs(text: str) -> List[float]:
    """Extract probability estimates from Chinese qualitative phrases."""
    probs = []
    for pattern, prob_value in CHINESE_PROB_PHRASES:
        if re.search(pattern, text):
            probs.append(prob_value)
    return probs


def analyze_sentiment(text: str) -> Tuple[str, float]:
    """
    Analyze sentiment of text.
    Returns: (stance, confidence)
    """
    text_lower = text.lower()

    bullish_score = sum(1 for kw in BULLISH_KEYWORDS if kw.lower() in text_lower)
    bearish_score = sum(1 for kw in BEARISH_KEYWORDS if kw.lower() in text_lower)

    total = bullish_score + bearish_score
    if total == 0:
        return 'neutral', 0.5

    if bullish_score > bearish_score:
        confidence = bullish_score / (total + 1)  # +1 to dampen extreme confidence
        return 'bullish', min(0.95, 0.5 + confidence * 0.5)
    elif bearish_score > bullish_score:
        confidence = bearish_score / (total + 1)
        return 'bearish', min(0.95, 0.5 + confidence * 0.5)
    else:
        return 'neutral', 0.5


def extract_risk_flags(text: str) -> List[str]:
    """Extract risk flags from text."""
    flags = []
    for flag_name, pattern in RISK_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            flags.append(flag_name)
    return flags


def parse_agent_quotes(text: str) -> List[AgentSignal]:
    """Extract agent quotes and analyze them."""
    signals = []

    # Pattern 1: > "statement" —— agent_name_123 (original format)
    quote_patterns = [
        r'>\s*["\"\u201c](.+?)["\"\u201d].*?——\s*(\w+)_(\d+)',
        # Pattern 2: [twitter] agent_name_123: statement
        r'\[twitter\]\s*(\w+)_(\d+):\s*(.+?)(?:\n|$)',
        # Pattern 3: @agent_name mentions (Chinese reports)
        r'@(\w+).*?["\"\u201c](.+?)["\"\u201d]',
    ]

    # Try pattern 1 first (most specific)
    matches = re.findall(quote_patterns[0], text, re.DOTALL)
    for quote, agent_type_raw, agent_id in matches:
        signal = _make_agent_signal(agent_type_raw, quote)
        if signal:
            signals.append(signal)

    # Try pattern 2 if no matches
    if not signals:
        matches = re.findall(quote_patterns[1], text, re.DOTALL)
        for agent_type_raw, agent_id, quote in matches:
            signal = _make_agent_signal(agent_type_raw, quote)
            if signal:
                signals.append(signal)

    # If still no agent quotes, do paragraph-level analysis
    if not signals:
        signals = _analyze_paragraphs(text)

    return signals


def _make_agent_signal(agent_type_raw: str, quote: str) -> Optional[AgentSignal]:
    """Create an AgentSignal from raw agent type and quote text."""
    agent_type = agent_type_raw.replace('_', '')
    for known_type in AGENT_WEIGHTS:
        if known_type.lower() in agent_type.lower():
            agent_type = known_type
            break

    stance, confidence = analyze_sentiment(quote)
    probs = extract_probabilities(quote)
    chinese_probs = extract_chinese_qualitative_probs(quote)
    all_probs = probs + chinese_probs
    risk_flags = extract_risk_flags(quote)

    return AgentSignal(
        agent_type=agent_type,
        stance=stance,
        probability=all_probs[0] if all_probs else None,
        confidence=confidence,
        risk_flags=risk_flags,
    )


def _analyze_paragraphs(text: str) -> List[AgentSignal]:
    """
    Fallback: analyze paragraphs as pseudo-agent signals.
    Used when no agent quotes are found in the text.
    """
    signals = []
    # Split by double newlines or section headers
    paragraphs = re.split(r'\n\s*\n|(?=^##\s)', text, flags=re.MULTILINE)

    for para in paragraphs:
        para = para.strip()
        if len(para) < 30:  # Skip very short fragments
            continue

        stance, confidence = analyze_sentiment(para)
        probs = extract_probabilities(para)
        chinese_probs = extract_chinese_qualitative_probs(para)
        all_probs = probs + chinese_probs

        # Try to identify agent type from paragraph content
        agent_type = 'Person'
        for known_type in AGENT_WEIGHTS:
            type_lower = known_type.lower()
            # Check for Chinese equivalents too
            type_map = {
                'medicalreviewer': ['医学审查', '医学评审', '审查员'],
                'regulatoryaffairsexpert': ['监管事务', '监管专家'],
                'clinicalstatistician': ['临床统计', '统计学家'],
                'scientifickol': ['意见领袖', 'KOL', '科学界'],
                'biotechtrader': ['交易员', '期权交易', '生物技术交易'],
                'shortseller': ['卖空', '短卖', '做空'],
                'pharmaanalyst': ['分析师', '市场分析'],
                'adcompanelsimulator': ['AdCom', '委员会'],
            }
            cn_terms = type_map.get(type_lower, [])
            if type_lower in para.lower() or any(t in para for t in cn_terms):
                agent_type = known_type
                break

        signals.append(AgentSignal(
            agent_type=agent_type,
            stance=stance,
            probability=all_probs[0] if all_probs else None,
            confidence=confidence,
            risk_flags=extract_risk_flags(para),
        ))

    return signals


def calculate_consensus(signals: List[AgentSignal], explicit_probs: List[float]) -> Tuple[float, float]:
    """
    Calculate weighted consensus probability.
    Returns: (consensus_probability, confidence_spread)
    """
    if not signals and not explicit_probs:
        return (None, None)  # No data — caller must handle missing signal
    
    # Start with explicit probabilities (weighted heavily)
    weighted_probs = []
    weights = []
    
    for prob in explicit_probs:
        weighted_probs.append(prob)
        weights.append(2.0)  # Explicit mentions weighted 2x
    
    # Add agent signal-derived probabilities
    for signal in signals:
        agent_weight = AGENT_WEIGHTS.get(signal.agent_type, 1.0)
        
        if signal.probability is not None:
            # Agent gave explicit probability
            weighted_probs.append(signal.probability)
            weights.append(agent_weight * signal.confidence)
        else:
            # Derive probability from sentiment
            if signal.stance == 'bullish':
                # Bullish → 65-85% depending on confidence
                derived_prob = 65 + (signal.confidence - 0.5) * 40
            elif signal.stance == 'bearish':
                # Bearish → 25-45% depending on confidence
                derived_prob = 45 - (signal.confidence - 0.5) * 40
            else:
                derived_prob = 50
            
            weighted_probs.append(derived_prob)
            weights.append(agent_weight * signal.confidence * 0.5)  # Derived probs weighted less
    
    if not weighted_probs:
        return (None, None)  # No usable data
    
    # Weighted average
    total_weight = sum(weights)
    consensus = sum(p * w for p, w in zip(weighted_probs, weights)) / total_weight
    
    # Confidence spread (standard deviation normalized)
    if len(weighted_probs) > 1:
        variance = sum(w * (p - consensus) ** 2 for p, w in zip(weighted_probs, weights)) / total_weight
        spread = min(1.0, (variance ** 0.5) / 25)  # Normalize: 25% std dev = max spread
    else:
        spread = 0.5  # Single data point = medium uncertainty
    
    return round(consensus, 1), round(spread, 2)


def parse_report(report_id: str) -> Optional[ParsedReport]:
    """
    Parse a MiroFish report and extract consensus probability.
    
    Args:
        report_id: The report ID (e.g., "report_bdb4ae63cf03")
    
    Returns:
        ParsedReport with extracted data, or None if not found
    """
    report_dir = REPORTS_DIR / report_id
    
    if not report_dir.exists():
        print(f"Report not found: {report_dir}")
        return None
    
    # Load meta.json
    meta_path = report_dir / "meta.json"
    if not meta_path.exists():
        print(f"meta.json not found in {report_dir}")
        return None
    
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    
    # Load full report
    report_path = report_dir / "full_report.md"
    if report_path.exists():
        with open(report_path, 'r', encoding='utf-8') as f:
            report_text = f.read()
    else:
        # Try section files
        report_text = ""
        for section_file in sorted(report_dir.glob("section_*.md")):
            with open(section_file, 'r', encoding='utf-8') as f:
                report_text += f.read() + "\n"
    
    if not report_text:
        print(f"No report content found in {report_dir}")
        return None
    
    # Extract ticker and drug from simulation requirement
    sim_req = meta.get('simulation_requirement', '')
    ticker_match = re.search(r'\$(\w+)', sim_req)
    # Try multiple drug name patterns
    drug_patterns = [
        r"'Will\s+(\S+)\s+\(",          # 'Will DRUG_NAME (type)
        r'(\w[\w-]*)\s*\(',              # DRUG-NAME (type)
        r'(\w+)\s*(?:gene therapy|drug|treatment|imaging agent|vaccine|antibody)',
    ]
    drug = 'UNKNOWN'
    for dp in drug_patterns:
        drug_match = re.search(dp, sim_req, re.IGNORECASE)
        if drug_match:
            drug = drug_match.group(1)
            break

    ticker = ticker_match.group(1) if ticker_match else 'UNKNOWN'

    # Try to extract ticker from "by CompanyName" in sim_req
    if ticker == 'UNKNOWN':
        # Check for known company→ticker mappings
        company_tickers = {
            'Rocket Pharmaceuticals': 'RCKT', 'Lantheus': 'LNTH',
            'Merck': 'MRK', 'Bristol-Myers': 'BMY', 'Bristol Myers': 'BMY',
            'Replicel': 'REPL', 'Cogent': 'COGT', 'Novavax': 'NVAX',
            'Alamos': 'ALMS',
        }
        for company, tk in company_tickers.items():
            if company.lower() in sim_req.lower():
                ticker = tk
                break

    # Also check report title for known drugs
    title = meta.get('outline', {}).get('title', '')
    known_drugs = {
        'KRESLADI': 'RCKT', 'LNTH-2501': 'LNTH', 'KEYTRUDA': 'MRK',
        'OPDIVO': 'BMY', 'NVAX': 'NVAX',
    }
    for drug_name, tk in known_drugs.items():
        if drug_name in title or drug_name in sim_req:
            drug = drug_name
            ticker = tk
            break
    
    # Extract all data
    explicit_probs = extract_probabilities(report_text)
    chinese_qual_probs = extract_chinese_qualitative_probs(report_text)
    agent_signals = parse_agent_quotes(report_text)
    all_risk_flags = extract_risk_flags(report_text)

    # Also analyze the summary
    summary = meta.get('outline', {}).get('summary', '')
    summary_probs = extract_probabilities(summary)
    summary_cn_probs = extract_chinese_qualitative_probs(summary)
    explicit_probs.extend(summary_probs)
    chinese_qual_probs.extend(summary_cn_probs)
    all_risk_flags.extend(extract_risk_flags(summary))

    # Merge: Chinese qualitative probs weighted less than explicit numeric
    all_probs = explicit_probs + chinese_qual_probs

    # Calculate consensus
    consensus, spread = calculate_consensus(agent_signals, all_probs)
    
    # Count stances
    bullish = sum(1 for s in agent_signals if s.stance == 'bullish')
    bearish = sum(1 for s in agent_signals if s.stance == 'bearish')
    neutral = sum(1 for s in agent_signals if s.stance == 'neutral')
    
    # Calculate confidence interval
    ci_width = spread * 20  # ±10% at max spread
    ci_low = max(0, consensus - ci_width)
    ci_high = min(100, consensus + ci_width)
    
    return ParsedReport(
        report_id=report_id,
        simulation_id=meta.get('simulation_id', 'unknown'),
        ticker=ticker,
        drug=drug,
        consensus_probability=consensus,
        confidence_interval=(round(ci_low, 1), round(ci_high, 1)),
        confidence_spread=spread,
        bullish_count=bullish,
        bearish_count=bearish,
        neutral_count=neutral,
        agent_signals=agent_signals,
        risk_flags=list(set(all_risk_flags)),
        explicit_probabilities=list(set(all_probs)),
    )


def format_report(parsed: ParsedReport, market_price: Optional[float] = None) -> str:
    """Format parsed report for display."""
    lines = [
        f"===========================================",
        f"[STATS] MiroFish Consensus Report",
        f"===========================================",
        f"",
        f"Ticker: ${parsed.ticker}",
        f"Drug: {parsed.drug}",
        f"Report: {parsed.report_id}",
        f"Simulation: {parsed.simulation_id}",
        f"",
        f"+-------------------------------------------+",
        f"| CONSENSUS PROBABILITY: {parsed.consensus_probability:>5.1f}%           |",
        f"| Confidence Interval: {parsed.confidence_interval[0]:.0f}% - {parsed.confidence_interval[1]:.0f}%       |",
        f"| Spread: {parsed.confidence_spread:.2f} (0=consensus, 1=chaos)    |",
        f"+-------------------------------------------+",
        f"",
    ]
    
    if market_price is not None:
        edge = parsed.edge_vs_market(market_price)
        edge_icon = "[TARGET]" if abs(edge) >= 15 else "[DOWN]" if edge < 0 else "[UP]"
        lines.extend([
            f"Market Price: {market_price:.1f}%",
            f"Edge: {edge:+.1f}% {edge_icon}",
            f"",
        ])
    
    lines.extend([
        f"Agent Sentiment:",
        f"  [GREEN] Bullish: {parsed.bullish_count}",
        f"  [RED] Bearish: {parsed.bearish_count}",
        f"  [  ] Neutral: {parsed.neutral_count}",
        f"",
    ])
    
    if parsed.explicit_probabilities:
        lines.append(f"Explicit Probabilities Found: {parsed.explicit_probabilities}")
        lines.append("")
    
    if parsed.risk_flags:
        lines.append(f"[WARN]  Risk Flags: {', '.join(parsed.risk_flags)}")
        lines.append("")
    
    return "\n".join(lines)


# =============================================================================
# Integration with pharma_fda_connector.py
# =============================================================================

def extract_consensus_from_report(report_id: str) -> Dict:
    """
    Main integration point for pharma_fda_connector.py
    
    Returns dict ready for trade signal evaluation:
    {
        'consensus_probability': float,
        'confidence_interval': (low, high),
        'confidence_spread': float,
        'risk_flags': list,
        'bullish_ratio': float,  # 0-1
        'has_cmc_risk': bool,
        'has_safety_risk': bool,
    }
    """
    parsed = parse_report(report_id)
    
    if parsed is None:
        return {
            'consensus_probability': None,
            'error': 'Report not found or unparseable',
        }
    
    total_signals = parsed.bullish_count + parsed.bearish_count + parsed.neutral_count
    bullish_ratio = parsed.bullish_count / max(1, total_signals)
    
    return {
        'consensus_probability': parsed.consensus_probability,
        'confidence_interval': parsed.confidence_interval,
        'confidence_spread': parsed.confidence_spread,
        'risk_flags': parsed.risk_flags,
        'bullish_ratio': round(bullish_ratio, 2),
        'has_cmc_risk': 'cmc' in parsed.risk_flags,
        'has_safety_risk': 'safety' in parsed.risk_flags,
        'has_financing_risk': 'financing' in parsed.risk_flags,
        'explicit_probs': parsed.explicit_probabilities,
        'ticker': parsed.ticker,
        'drug': parsed.drug,
    }


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python report_parser.py <report_id> [market_price]")
        print("Example: python report_parser.py report_bdb4ae63cf03 74")
        sys.exit(1)
    
    report_id = sys.argv[1]
    market_price = float(sys.argv[2]) if len(sys.argv) > 2 else None
    
    parsed = parse_report(report_id)
    
    if parsed:
        print(format_report(parsed, market_price))
        print("\n--- Integration Dict ---")
        print(json.dumps(extract_consensus_from_report(report_id), indent=2))
    else:
        print(f"Failed to parse report: {report_id}")
        sys.exit(1)
