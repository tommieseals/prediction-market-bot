#!/usr/bin/env python3
"""
ALERT FORMATTER — Enhanced Telegram alert formatting with inline buttons

Creates rich, actionable alerts with:
- Priority indicators
- Confidence bars
- Quick action buttons
- Market context
"""

import requests
from datetime import datetime
from typing import Optional, Dict, List

TELEGRAM_BOT_TOKEN = "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU"
TELEGRAM_CHAT_ID = "939543801"


def create_edge_bar(edge: float, width: int = 10) -> str:
    """Create a visual edge bar."""
    filled = int(min(edge / 0.20, 1.0) * width)  # 20% = full bar
    return '#' * filled + '-' * (width - filled)


def create_confidence_bar(confidence: str) -> str:
    """Create confidence indicator."""
    levels = {
        "HIGH": "[####]",
        "NORMAL": "[##--]",
        "CAUTION": "[#---]",
        "LOW": "[----]",
    }
    return levels.get(confidence, "[????]")


def format_signal_alert(
    market_title: str,
    direction: str,
    edge: float,
    size_usd: float,
    whale_name: str,
    whale_score: float,
    signal_type: str = "FOLLOW",
    confidence: str = "NORMAL",
    swarm_prob: float = None,
    market_price: float = None,
    signal_id: str = None,
) -> str:
    """
    Format a trade signal alert with rich formatting.
    
    Returns:
        Formatted HTML string for Telegram.
    """
    # Priority based on edge
    if edge >= 0.15:
        priority = "[!!] URGENT"
        emoji = "!!"
    elif edge >= 0.10:
        priority = "[!] HIGH"
        emoji = "!"
    else:
        priority = "[OK] SIGNAL"
        emoji = "OK"
    
    # Edge bar
    edge_bar = create_edge_bar(edge)
    conf_bar = create_confidence_bar(confidence)
    
    # Direction with emoji
    dir_emoji = "+" if direction == "YES" else "-"
    
    # Format message
    msg = f"<b>{priority}</b>\n"
    msg += f"<b>{signal_type}</b> via {whale_name}\n\n"
    
    msg += f"<b>{market_title[:50]}</b>\n"
    msg += f"{dir_emoji} <b>{direction}</b> @ ${size_usd:,.0f}\n\n"
    
    msg += f"Edge: {edge:+.1%} [{edge_bar}]\n"
    msg += f"Conf: {confidence} {conf_bar}\n"
    
    if swarm_prob and market_price:
        msg += f"Swarm: {swarm_prob:.0%} vs Mkt: {market_price:.0%}\n"
    
    msg += f"\nWhale Score: {whale_score:.0f}\n"
    
    if signal_id:
        msg += f"\n<code>{signal_id[:12]}</code>"
    
    return msg


def format_whale_move_alert(
    whale_name: str,
    whale_score: float,
    whale_pnl: float,
    market_title: str,
    side: str,
    entry_price: float,
    size_usd: float,
    tracked_bets: int = 0,
    tracked_acc: float = 0,
) -> str:
    """
    Format a whale move detection alert.
    """
    # Priority based on whale quality
    if whale_score >= 70 or size_usd >= 10000:
        priority = "[!!] HOT"
    elif whale_score >= 50 or size_usd >= 5000:
        priority = "[!] ACTIVE"
    else:
        priority = "[OK] NEW"
    
    msg = f"<b>{priority} WHALE MOVE</b>\n\n"
    
    msg += f"<b>{whale_name}</b>\n"
    msg += f"Score: {whale_score:.0f} | PnL: ${whale_pnl:,.0f}\n"
    
    if tracked_bets >= 5:
        msg += f"Tracked: {tracked_bets} bets @ {tracked_acc:.0%}\n"
    
    msg += f"\n<b>{market_title[:45]}</b>\n"
    msg += f"{side} @ ${entry_price:.4f}\n"
    msg += f"Size: ${size_usd:,.0f}\n"
    
    msg += "\n[~] Validating..."
    
    return msg


def format_digest_alert(
    stats: Dict,
    top_whales: List[Dict],
    recent_signals: List[Dict],
) -> str:
    """
    Format daily digest alert.
    """
    now = datetime.now()
    
    msg = f"<b>[DIGEST] Daily Summary</b>\n"
    msg += f"<i>{now.strftime('%Y-%m-%d %H:%M')}</i>\n\n"
    
    # Stats
    wr = stats.get('win_rate', 0)
    wr_bar = '#' * int(wr / 10) + '-' * (10 - int(wr / 10))
    
    msg += f"<b>7-Day Performance</b>\n"
    msg += f"Win Rate: {wr:.1f}% [{wr_bar}]\n"
    msg += f"W:{stats.get('won', 0)} L:{stats.get('lost', 0)} P:{stats.get('pending', 0)}\n\n"
    
    # Top whales
    msg += f"<b>Top Whales</b>\n"
    for w in top_whales[:3]:
        msg += f"  {w['name'][:12]} - {w.get('score', 0):.0f}pts\n"
    
    # Recent
    msg += f"\n<b>Recent</b>\n"
    for s in recent_signals[:3]:
        outcome = s.get('outcome', 'pending')
        emoji = "[OK]" if outcome == 'won' else "[FAIL]" if outcome == 'lost' else "[~]"
        msg += f"  {emoji} {s.get('side', '?')} {s.get('market', 'Unknown')[:20]}\n"
    
    return msg


def send_formatted_alert(message: str, buttons: List[List[Dict]] = None) -> bool:
    """
    Send a formatted alert to Telegram with optional inline buttons.
    
    Args:
        message: HTML-formatted message
        buttons: Optional inline keyboard [[{text, callback_data}]]
    
    Returns:
        True if sent successfully
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    
    if buttons:
        data["reply_markup"] = {"inline_keyboard": buttons}
    
    try:
        resp = requests.post(url, json=data, timeout=10)
        return resp.ok
    except Exception:
        return False


if __name__ == "__main__":
    # Test signal alert
    print("Testing signal alert format...")
    msg = format_signal_alert(
        market_title="Will Lakers beat Celtics tonight?",
        direction="YES",
        edge=0.15,
        size_usd=500,
        whale_name="swisstony",
        whale_score=80,
        signal_type="FOLLOW",
        confidence="HIGH",
        swarm_prob=0.70,
        market_price=0.55,
        signal_id="wh_abc123def456"
    )
    print(msg)
    print()
    
    # Test whale move alert
    print("Testing whale move alert format...")
    msg = format_whale_move_alert(
        whale_name="TheOneto3",
        whale_score=79.5,
        whale_pnl=29718,
        market_title="Will BTC hit 100k by end of March?",
        side="YES",
        entry_price=0.65,
        size_usd=5000,
        tracked_bets=31,
        tracked_acc=1.0
    )
    print(msg)
