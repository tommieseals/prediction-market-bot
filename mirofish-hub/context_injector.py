#!/usr/bin/env python3
"""
🧠 CONTEXT INJECTOR — Enriched Data Layer for MiroFish Simulations

Builds rich context prompts by combining:
1. Whale historical data (who's betting, their track record)
2. External news (relevant headlines for the market)
3. Sports data (injuries, stats, odds)
4. Market metadata (volume, price history, liquidity)

Usage:
    from context_injector import ContextInjector
    injector = ContextInjector()
    context = injector.build_context(market_title, condition_id)
"""

import os
import sqlite3
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import json
import re

# Database
DB_PATH = Path(__file__).parent / "data" / "whale_hunter.db"

# News API (free tier)
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")  # Optional: newsapi.org key

# Sports data (free APIs)
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")  # Optional: the-odds-api.com


class ContextInjector:
    """
    Builds enriched context for MiroFish simulations.
    
    Combines whale data + news + sports data into rich prompts.
    """
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self._cache = {}  # Simple cache for repeated lookups
    
    def build_context(self, market_title: str, condition_id: str = "") -> Dict:
        """
        Build full context for a market.
        
        Returns dict with all enrichment data.
        """
        context = {
            "market_title": market_title,
            "condition_id": condition_id,
            "whale_context": self._get_whale_context(condition_id),
            "category": self._detect_category(market_title),
            "news_context": [],
            "sports_context": None,
            "prompt_sections": []
        }
        
        # Add category-specific enrichment
        category = context["category"]
        
        if category in ("sports", "nba", "nfl", "mlb", "tennis", "soccer", "mma"):
            context["sports_context"] = self._get_sports_context(market_title)
        
        if category in ("politics", "geopolitics"):
            context["news_context"] = self._get_news_context(market_title)
        
        if category == "crypto":
            context["news_context"] = self._get_crypto_context(market_title)
        
        # Build the prompt sections
        context["prompt_sections"] = self._build_prompt_sections(context)
        
        return context
    
    def _get_whale_context(self, condition_id: str) -> Dict:
        """Get whale activity and history for this market."""
        if not condition_id:
            return {"whales": [], "summary": "No whale data available"}
        
        # Get all whales on this market
        rows = self.conn.execute("""
            SELECT 
                wp.address,
                wp.side,
                wp.size_usd,
                wp.entry_price,
                wp.detected_at,
                (SELECT COUNT(*) FROM whale_positions wp2 
                 WHERE wp2.address = wp.address AND wp2.outcome = 'won') as wins,
                (SELECT COUNT(*) FROM whale_positions wp2 
                 WHERE wp2.address = wp.address AND wp2.outcome = 'lost') as losses,
                (SELECT GROUP_CONCAT(DISTINCT flag_type) FROM insider_flags if 
                 WHERE if.address = wp.address) as insider_flags
            FROM whale_positions wp
            WHERE wp.condition_id = ?
            ORDER BY wp.size_usd DESC
            LIMIT 10
        """, (condition_id,)).fetchall()
        
        whales = []
        total_yes = 0
        total_no = 0
        
        for r in rows:
            total_trades = (r["wins"] or 0) + (r["losses"] or 0)
            win_rate = (r["wins"] / total_trades * 100) if total_trades > 0 else 0
            
            whale_info = {
                "address": r["address"][:12] + "...",
                "side": r["side"],
                "size": r["size_usd"],
                "entry_price": r["entry_price"],
                "win_rate": round(win_rate, 1),
                "total_trades": total_trades,
                "insider_flags": r["insider_flags"].split(",") if r["insider_flags"] else []
            }
            whales.append(whale_info)
            
            if r["side"] == "YES":
                total_yes += r["size_usd"]
            else:
                total_no += r["size_usd"]
        
        # Calculate weighted consensus
        total = total_yes + total_no
        yes_pct = (total_yes / total * 100) if total > 0 else 50
        
        # Count high-accuracy whales (>80% win rate)
        elite_count = len([w for w in whales if w["win_rate"] >= 80 and w["total_trades"] >= 10])
        
        summary = f"{len(whales)} whales on this market. "
        summary += f"${total_yes:,.0f} on YES, ${total_no:,.0f} on NO. "
        summary += f"Whale consensus: {yes_pct:.0f}% YES. "
        if elite_count > 0:
            summary += f"{elite_count} elite traders (80%+ win rate) involved."
        
        return {
            "whales": whales,
            "total_yes": total_yes,
            "total_no": total_no,
            "yes_pct": yes_pct,
            "elite_count": elite_count,
            "summary": summary
        }
    
    def _detect_category(self, title: str) -> str:
        """Detect market category from title."""
        t = title.lower()
        
        # Sports detection
        if any(w in t for w in ["nba", "lakers", "celtics", "warriors", "bucks", "76ers"]):
            return "nba"
        if any(w in t for w in ["nfl", "chiefs", "eagles", "cowboys", "super bowl"]):
            return "nfl"
        if any(w in t for w in ["mlb", "yankees", "dodgers", "world series"]):
            return "mlb"
        if any(w in t for w in ["open:", "atp", "wta", "tennis", "djokovic", "nadal", "federer"]):
            return "tennis"
        if any(w in t for w in ["ufc", "mma", "fight night", "welterweight", "heavyweight"]):
            return "mma"
        if any(w in t for w in ["premier league", "champions league", "fc ", "arsenal", "liverpool"]):
            return "soccer"
        if any(w in t for w in ["vs.", "spread:", "o/u ", "handicap"]):
            return "sports"
        
        # Other categories
        if any(w in t for w in ["iran", "israel", "ukraine", "russia", "ceasefire", "regime", "military"]):
            return "geopolitics"
        if any(w in t for w in ["trump", "biden", "election", "president", "congress", "vance"]):
            return "politics"
        if any(w in t for w in ["bitcoin", "ethereum", "crypto", "btc", "eth"]):
            return "crypto"
        
        return "other"
    
    def _get_sports_context(self, market_title: str) -> Dict:
        """Get sports-specific context (injuries, stats, odds)."""
        context = {
            "teams": [],
            "injuries": [],
            "recent_form": [],
            "odds_comparison": None,
            "key_factors": []
        }
        
        # Extract team/player names from title
        teams = self._extract_teams(market_title)
        context["teams"] = teams
        
        # Try to get injury data (if API key available)
        if ODDS_API_KEY and teams:
            try:
                context["odds_comparison"] = self._fetch_odds(teams)
            except:
                pass
        
        # Add key factors based on market type
        t = market_title.lower()
        
        if "spread:" in t:
            context["key_factors"].append("Spread bet - margin matters, not just winner")
        if "o/u " in t or "over/under" in t:
            context["key_factors"].append("Over/Under - focus on pace, defense quality")
        if "vs" in t:
            # Head-to-head match
            context["key_factors"].append("H2H - recent matchup history matters")
        
        return context
    
    def _get_news_context(self, market_title: str) -> List[Dict]:
        """Get relevant news headlines for the market."""
        news = []
        
        # Extract key terms for search
        search_terms = self._extract_search_terms(market_title)
        
        if not search_terms:
            return news
        
        # Try NewsAPI if available
        if NEWS_API_KEY:
            try:
                news = self._fetch_news(search_terms)
            except:
                pass
        
        # Fallback: Generate context from what we know
        if not news:
            # Add market-specific context based on keywords
            t = market_title.lower()
            
            if "iran" in t:
                news.append({
                    "source": "context",
                    "headline": "Iran geopolitical situation - consider recent tensions and negotiations",
                    "relevance": "high"
                })
            if "ceasefire" in t:
                news.append({
                    "source": "context", 
                    "headline": "Ceasefire markets are binary - either happens or doesn't by deadline",
                    "relevance": "high"
                })
            if "regime" in t:
                news.append({
                    "source": "context",
                    "headline": "Regime change predictions historically overestimate probability",
                    "relevance": "medium"
                })
        
        return news
    
    def _get_crypto_context(self, market_title: str) -> List[Dict]:
        """Get crypto-specific context."""
        news = []
        t = market_title.lower()
        
        # Add relevant crypto context
        if "bitcoin" in t or "btc" in t:
            news.append({
                "source": "context",
                "headline": "Bitcoin price targets - check current price vs target",
                "relevance": "high"
            })
        
        if "$" in market_title and any(c.isdigit() for c in market_title):
            # Price target market
            news.append({
                "source": "context",
                "headline": "Price target markets - calculate % move required",
                "relevance": "high"
            })
        
        return news
    
    def _extract_teams(self, title: str) -> List[str]:
        """Extract team/player names from title."""
        teams = []
        
        # Common patterns: "Team A vs Team B", "Team A vs. Team B"
        vs_match = re.search(r'(.+?)\s+vs\.?\s+(.+?)(?:\s*[:\(]|$)', title)
        if vs_match:
            teams = [vs_match.group(1).strip(), vs_match.group(2).strip()]
        
        return teams
    
    def _extract_search_terms(self, title: str) -> str:
        """Extract key search terms from market title."""
        # Remove common words
        stopwords = {'will', 'the', 'a', 'an', 'by', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or'}
        words = title.lower().split()
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        
        # Return top 3 keywords
        return ' '.join(keywords[:3])
    
    def _fetch_news(self, query: str) -> List[Dict]:
        """Fetch news from NewsAPI."""
        if not NEWS_API_KEY:
            return []
        
        try:
            url = f"https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "sortBy": "publishedAt",
                "pageSize": 5,
                "apiKey": NEWS_API_KEY
            }
            resp = requests.get(url, params=params, timeout=10)
            if resp.ok:
                data = resp.json()
                articles = data.get("articles", [])
                return [{
                    "source": a.get("source", {}).get("name", "Unknown"),
                    "headline": a.get("title", ""),
                    "published": a.get("publishedAt", ""),
                    "relevance": "medium"
                } for a in articles[:5]]
        except:
            pass
        
        return []
    
    def _fetch_odds(self, teams: List[str]) -> Dict:
        """Fetch odds comparison from The Odds API."""
        if not ODDS_API_KEY or len(teams) < 2:
            return None
        
        # This would integrate with the-odds-api.com
        # For now, return placeholder
        return None
    
    def _build_prompt_sections(self, context: Dict) -> List[str]:
        """Build prompt sections from context."""
        sections = []
        
        # Whale section
        whale = context.get("whale_context", {})
        if whale.get("whales"):
            whale_text = f"""
WHALE INTELLIGENCE:
{whale.get('summary', '')}

Top whales on this market:"""
            for w in whale["whales"][:5]:
                flags = f" [INSIDER: {','.join(w['insider_flags'][:2])}]" if w["insider_flags"] else ""
                whale_text += f"\n  - {w['address']}: ${w['size']:,.0f} {w['side']} @ {w['entry_price']:.2f} (WR: {w['win_rate']}%){flags}"
            sections.append(whale_text)
        
        # News section
        news = context.get("news_context", [])
        if news:
            news_text = "\nRELEVANT CONTEXT:"
            for n in news[:3]:
                news_text += f"\n  - {n['headline']}"
            sections.append(news_text)
        
        # Sports section
        sports = context.get("sports_context")
        if sports and sports.get("key_factors"):
            sports_text = "\nSPORTS FACTORS:"
            for f in sports["key_factors"]:
                sports_text += f"\n  - {f}"
            if sports.get("teams"):
                sports_text += f"\n  Teams: {' vs '.join(sports['teams'])}"
            sections.append(sports_text)
        
        return sections
    
    def format_for_simulation(self, context: Dict) -> str:
        """Format context as a single string for MiroFish simulation."""
        parts = [f"Market: {context['market_title']}", ""]
        parts.extend(context.get("prompt_sections", []))
        return "\n".join(parts)
    
    def close(self):
        """Close database connection."""
        self.conn.close()


# ══════════════════════════════════════════════════════════════
# INTEGRATION WITH ENSEMBLE VOTER
# ══════════════════════════════════════════════════════════════

def enrich_ensemble_prompt(market_title: str, condition_id: str, base_prompt: str) -> str:
    """
    Enrich an ensemble voting prompt with context.
    
    Call this before sending to models.
    """
    try:
        injector = ContextInjector()
        context = injector.build_context(market_title, condition_id)
        enrichment = injector.format_for_simulation(context)
        injector.close()
        
        # Combine base prompt with enrichment
        return f"{enrichment}\n\n---\n\n{base_prompt}"
    except Exception as e:
        print(f"[WARN] Context injection failed: {e}")
        return base_prompt


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Context Injector")
    parser.add_argument("--market", type=str, required=True, help="Market title")
    parser.add_argument("--condition", type=str, default="", help="Condition ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    injector = ContextInjector()
    context = injector.build_context(args.market, args.condition)
    
    if args.json:
        print(json.dumps(context, indent=2, default=str))
    else:
        print("=" * 60)
        print(f"CONTEXT FOR: {args.market[:50]}...")
        print("=" * 60)
        
        print(f"\nCategory: {context['category']}")
        
        print(f"\nWhale Summary:")
        print(f"  {context['whale_context'].get('summary', 'No whale data')}")
        
        if context.get("news_context"):
            print(f"\nNews Context:")
            for n in context["news_context"]:
                print(f"  - {n['headline'][:60]}...")
        
        if context.get("sports_context"):
            sc = context["sports_context"]
            if sc.get("teams"):
                print(f"\nTeams: {' vs '.join(sc['teams'])}")
            if sc.get("key_factors"):
                print("Key Factors:")
                for f in sc["key_factors"]:
                    print(f"  - {f}")
        
        print("\n" + "=" * 60)
        print("FORMATTED PROMPT SECTIONS:")
        print("=" * 60)
        print(injector.format_for_simulation(context))
    
    injector.close()
