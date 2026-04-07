"""
auto_researcher.py - Pre-simulation research engine for MiroFish swarm simulations.

Gathers real-world data by market type (sports, politics, crypto, macro) to enrich
swarm simulation seed text. Each research pathway queries public APIs and returns
structured text blocks that feed into downstream prediction models.

Usage:
    python auto_researcher.py "Lakers vs Pistons" sports
    python auto_researcher.py "Will Bitcoin hit 100k?" crypto
    python auto_researcher.py "Fed rate decision June" macro
    python auto_researcher.py "Iran nuclear deal" politics
"""

import argparse
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Team / entity mappings
# ---------------------------------------------------------------------------

# NBA team name variants -> (espn_team_id, canonical_name)
NBA_TEAMS: Dict[str, Tuple[str, str]] = {
    "hawks": ("1", "Atlanta Hawks"), "atlanta": ("1", "Atlanta Hawks"),
    "celtics": ("2", "Boston Celtics"), "boston": ("2", "Boston Celtics"),
    "nets": ("17", "Brooklyn Nets"), "brooklyn": ("17", "Brooklyn Nets"),
    "hornets": ("30", "Charlotte Hornets"), "charlotte": ("30", "Charlotte Hornets"),
    "bulls": ("4", "Chicago Bulls"), "chicago": ("4", "Chicago Bulls"),
    "cavaliers": ("5", "Cleveland Cavaliers"), "cavs": ("5", "Cleveland Cavaliers"),
    "cleveland": ("5", "Cleveland Cavaliers"),
    "mavericks": ("6", "Dallas Mavericks"), "mavs": ("6", "Dallas Mavericks"),
    "dallas": ("6", "Dallas Mavericks"),
    "nuggets": ("7", "Denver Nuggets"), "denver": ("7", "Denver Nuggets"),
    "pistons": ("8", "Detroit Pistons"), "detroit": ("8", "Detroit Pistons"),
    "warriors": ("9", "Golden State Warriors"), "golden state": ("9", "Golden State Warriors"),
    "rockets": ("10", "Houston Rockets"), "houston": ("10", "Houston Rockets"),
    "pacers": ("11", "Indiana Pacers"), "indiana": ("11", "Indiana Pacers"),
    "clippers": ("12", "LA Clippers"),
    "lakers": ("13", "Los Angeles Lakers"), "la lakers": ("13", "Los Angeles Lakers"),
    "grizzlies": ("29", "Memphis Grizzlies"), "memphis": ("29", "Memphis Grizzlies"),
    "heat": ("14", "Miami Heat"), "miami": ("14", "Miami Heat"),
    "bucks": ("15", "Milwaukee Bucks"), "milwaukee": ("15", "Milwaukee Bucks"),
    "timberwolves": ("16", "Minnesota Timberwolves"), "wolves": ("16", "Minnesota Timberwolves"),
    "minnesota": ("16", "Minnesota Timberwolves"),
    "pelicans": ("3", "New Orleans Pelicans"), "new orleans": ("3", "New Orleans Pelicans"),
    "knicks": ("18", "New York Knicks"), "new york": ("18", "New York Knicks"),
    "thunder": ("25", "Oklahoma City Thunder"), "okc": ("25", "Oklahoma City Thunder"),
    "magic": ("19", "Orlando Magic"), "orlando": ("19", "Orlando Magic"),
    "76ers": ("20", "Philadelphia 76ers"), "sixers": ("20", "Philadelphia 76ers"),
    "philadelphia": ("20", "Philadelphia 76ers"), "philly": ("20", "Philadelphia 76ers"),
    "suns": ("21", "Phoenix Suns"), "phoenix": ("21", "Phoenix Suns"),
    "trail blazers": ("22", "Portland Trail Blazers"), "blazers": ("22", "Portland Trail Blazers"),
    "portland": ("22", "Portland Trail Blazers"),
    "kings": ("23", "Sacramento Kings"), "sacramento": ("23", "Sacramento Kings"),
    "spurs": ("24", "San Antonio Spurs"), "san antonio": ("24", "San Antonio Spurs"),
    "raptors": ("28", "Toronto Raptors"), "toronto": ("28", "Toronto Raptors"),
    "jazz": ("26", "Utah Jazz"), "utah": ("26", "Utah Jazz"),
    "wizards": ("27", "Washington Wizards"), "washington": ("27", "Washington Wizards"),
}

# NFL team name variants -> (espn_team_id, canonical_name)
NFL_TEAMS: Dict[str, Tuple[str, str]] = {
    "cardinals": ("22", "Arizona Cardinals"), "arizona": ("22", "Arizona Cardinals"),
    "falcons": ("1", "Atlanta Falcons"),
    "ravens": ("33", "Baltimore Ravens"), "baltimore": ("33", "Baltimore Ravens"),
    "bills": ("2", "Buffalo Bills"), "buffalo": ("2", "Buffalo Bills"),
    "panthers": ("29", "Carolina Panthers"), "carolina": ("29", "Carolina Panthers"),
    "bears": ("3", "Chicago Bears"),
    "bengals": ("4", "Cincinnati Bengals"), "cincinnati": ("4", "Cincinnati Bengals"),
    "browns": ("5", "Cleveland Browns"),
    "cowboys": ("6", "Dallas Cowboys"),
    "broncos": ("7", "Denver Broncos"),
    "lions": ("8", "Detroit Lions"),
    "packers": ("9", "Green Bay Packers"), "green bay": ("9", "Green Bay Packers"),
    "texans": ("34", "Houston Texans"),
    "colts": ("11", "Indianapolis Colts"), "indianapolis": ("11", "Indianapolis Colts"),
    "jaguars": ("30", "Jacksonville Jaguars"), "jags": ("30", "Jacksonville Jaguars"),
    "jacksonville": ("30", "Jacksonville Jaguars"),
    "chiefs": ("12", "Kansas City Chiefs"), "kansas city": ("12", "Kansas City Chiefs"),
    "raiders": ("13", "Las Vegas Raiders"), "las vegas": ("13", "Las Vegas Raiders"),
    "chargers": ("24", "Los Angeles Chargers"),
    "rams": ("14", "Los Angeles Rams"),
    "dolphins": ("15", "Miami Dolphins"),
    "vikings": ("16", "Minnesota Vikings"),
    "patriots": ("17", "New England Patriots"), "new england": ("17", "New England Patriots"),
    "saints": ("18", "New Orleans Saints"),
    "giants": ("19", "New York Giants"),
    "jets": ("20", "New York Jets"),
    "eagles": ("21", "Philadelphia Eagles"),
    "steelers": ("23", "Pittsburgh Steelers"), "pittsburgh": ("23", "Pittsburgh Steelers"),
    "49ers": ("25", "San Francisco 49ers"), "niners": ("25", "San Francisco 49ers"),
    "san francisco": ("25", "San Francisco 49ers"),
    "seahawks": ("26", "Seattle Seahawks"), "seattle": ("26", "Seattle Seahawks"),
    "buccaneers": ("27", "Tampa Bay Buccaneers"), "bucs": ("27", "Tampa Bay Buccaneers"),
    "tampa bay": ("27", "Tampa Bay Buccaneers"), "tampa": ("27", "Tampa Bay Buccaneers"),
    "titans": ("10", "Tennessee Titans"), "tennessee": ("10", "Tennessee Titans"),
    "commanders": ("28", "Washington Commanders"),
}

# NHL team name variants -> (espn_team_id, canonical_name)
NHL_TEAMS: Dict[str, Tuple[str, str]] = {
    "ducks": ("25", "Anaheim Ducks"), "anaheim": ("25", "Anaheim Ducks"),
    "coyotes": ("53", "Arizona Coyotes"),
    "bruins": ("1", "Boston Bruins"),
    "sabres": ("2", "Buffalo Sabres"),
    "flames": ("3", "Calgary Flames"), "calgary": ("3", "Calgary Flames"),
    "hurricanes": ("7", "Carolina Hurricanes"),
    "blackhawks": ("4", "Chicago Blackhawks"),
    "avalanche": ("17", "Colorado Avalanche"), "avs": ("17", "Colorado Avalanche"),
    "colorado": ("17", "Colorado Avalanche"),
    "blue jackets": ("29", "Columbus Blue Jackets"), "columbus": ("29", "Columbus Blue Jackets"),
    "stars": ("25", "Dallas Stars"),
    "red wings": ("8", "Detroit Red Wings"),
    "oilers": ("22", "Edmonton Oilers"), "edmonton": ("22", "Edmonton Oilers"),
    "panthers_nhl": ("13", "Florida Panthers"),
    "kings_nhl": ("26", "Los Angeles Kings"),
    "wild": ("30", "Minnesota Wild"),
    "canadiens": ("9", "Montreal Canadiens"), "habs": ("9", "Montreal Canadiens"),
    "montreal": ("9", "Montreal Canadiens"),
    "predators": ("18", "Nashville Predators"), "preds": ("18", "Nashville Predators"),
    "nashville": ("18", "Nashville Predators"),
    "devils": ("10", "New Jersey Devils"), "new jersey": ("10", "New Jersey Devils"),
    "islanders": ("11", "New York Islanders"),
    "rangers": ("12", "New York Rangers"),
    "senators": ("14", "Ottawa Senators"), "sens": ("14", "Ottawa Senators"),
    "ottawa": ("14", "Ottawa Senators"),
    "flyers": ("16", "Philadelphia Flyers"),
    "penguins": ("15", "Pittsburgh Penguins"), "pens": ("15", "Pittsburgh Penguins"),
    "sharks": ("28", "San Jose Sharks"), "san jose": ("28", "San Jose Sharks"),
    "kraken": ("55", "Seattle Kraken"),
    "blues": ("19", "St. Louis Blues"), "st louis": ("19", "St. Louis Blues"),
    "lightning": ("27", "Tampa Bay Lightning"),
    "maple leafs": ("20", "Toronto Maple Leafs"), "leafs": ("20", "Toronto Maple Leafs"),
    "canucks": ("23", "Vancouver Canucks"), "vancouver": ("23", "Vancouver Canucks"),
    "golden knights": ("54", "Vegas Golden Knights"), "vegas": ("54", "Vegas Golden Knights"),
    "capitals": ("24", "Washington Capitals"), "caps": ("24", "Washington Capitals"),
    "jets_nhl": ("52", "Winnipeg Jets"), "winnipeg": ("52", "Winnipeg Jets"),
}

# MLB team name variants -> (espn_team_id, canonical_name)
MLB_TEAMS: Dict[str, Tuple[str, str]] = {
    "diamondbacks": ("29", "Arizona Diamondbacks"), "dbacks": ("29", "Arizona Diamondbacks"),
    "braves": ("15", "Atlanta Braves"),
    "orioles": ("1", "Baltimore Orioles"),
    "red sox": ("2", "Boston Red Sox"),
    "cubs": ("16", "Chicago Cubs"),
    "white sox": ("4", "Chicago White Sox"),
    "reds": ("17", "Cincinnati Reds"),
    "guardians": ("5", "Cleveland Guardians"),
    "rockies": ("27", "Colorado Rockies"),
    "tigers": ("6", "Detroit Tigers"),
    "astros": ("18", "Houston Astros"),
    "royals": ("7", "Kansas City Royals"),
    "angels": ("3", "Los Angeles Angels"),
    "dodgers": ("19", "Los Angeles Dodgers"),
    "marlins": ("28", "Miami Marlins"),
    "brewers": ("8", "Milwaukee Brewers"),
    "twins": ("9", "Minnesota Twins"),
    "mets": ("21", "New York Mets"),
    "yankees": ("10", "New York Yankees"),
    "athletics": ("11", "Oakland Athletics"),
    "phillies": ("22", "Philadelphia Phillies"),
    "pirates": ("23", "Pittsburgh Pirates"),
    "padres": ("25", "San Diego Padres"), "san diego": ("25", "San Diego Padres"),
    "mariners": ("12", "Seattle Mariners"),
    "cardinals_mlb": ("24", "St. Louis Cardinals"),
    "rays": ("30", "Tampa Bay Rays"),
    "rangers_mlb": ("13", "Texas Rangers"), "texas": ("13", "Texas Rangers"),
    "blue jays": ("14", "Toronto Blue Jays"), "jays": ("14", "Toronto Blue Jays"),
    "nationals": ("20", "Washington Nationals"),
}

# Aggregate lookup: team_keyword -> (league, sport, espn_id, canonical)
ALL_TEAMS: Dict[str, Tuple[str, str, str, str]] = {}
for _name, (_id, _canon) in NBA_TEAMS.items():
    ALL_TEAMS[_name] = ("nba", "basketball", _id, _canon)
for _name, (_id, _canon) in NFL_TEAMS.items():
    if _name not in ALL_TEAMS:  # avoid collisions; NBA takes priority for shared city names
        ALL_TEAMS[_name] = ("nfl", "football", _id, _canon)
for _name, (_id, _canon) in NHL_TEAMS.items():
    if _name not in ALL_TEAMS:
        ALL_TEAMS[_name] = ("nhl", "hockey", _id, _canon)
for _name, (_id, _canon) in MLB_TEAMS.items():
    if _name not in ALL_TEAMS:
        ALL_TEAMS[_name] = ("mlb", "baseball", _id, _canon)

# Crypto token name -> CoinGecko ID
CRYPTO_IDS: Dict[str, str] = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana",
    "cardano": "cardano", "ada": "cardano",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "polkadot": "polkadot", "dot": "polkadot",
    "avalanche": "avalanche-2", "avax": "avalanche-2",
    "chainlink": "chainlink", "link": "chainlink",
    "polygon": "matic-network", "matic": "matic-network",
    "litecoin": "litecoin", "ltc": "litecoin",
    "uniswap": "uniswap", "uni": "uniswap",
    "ripple": "ripple", "xrp": "ripple",
    "tron": "tron", "trx": "tron",
    "shiba inu": "shiba-inu", "shib": "shiba-inu",
    "near": "near", "near protocol": "near",
    "arbitrum": "arbitrum", "arb": "arbitrum",
    "optimism": "optimism", "op": "optimism",
    "sui": "sui",
    "aptos": "aptos", "apt": "aptos",
    "pepe": "pepe",
}

# FRED series IDs for macro research
FRED_SERIES: Dict[str, str] = {
    "FEDFUNDS": "Federal Funds Rate",
    "CPIAUCSL": "Consumer Price Index (CPI)",
    "UNRATE": "Unemployment Rate",
    "GDP": "Gross Domestic Product",
    "DGS10": "10-Year Treasury Yield",
    "DGS2": "2-Year Treasury Yield",
    "T10Y2Y": "10Y-2Y Treasury Spread",
    "MORTGAGE30US": "30-Year Mortgage Rate",
}

# Political entity keywords for NewsAPI queries
POLITICAL_ENTITIES: List[str] = [
    "trump", "biden", "harris", "desantis", "obama", "congress",
    "senate", "house", "supreme court", "scotus", "election",
    "republican", "democrat", "gop", "dnc", "rnc",
    "iran", "ukraine", "russia", "china", "nato", "eu",
    "fed", "federal reserve", "tariff", "immigration", "border",
    "impeach", "indictment", "classified", "nuclear", "sanctions",
    "ceasefire", "gaza", "israel", "palestine", "hamas", "hezbollah",
]

HTTP_TIMEOUT: int = 10  # seconds


class AutoResearcher:
    """Pre-simulation research engine that gathers real-world data by market type.

    Supports four market verticals:
        - sports:   ESPN public API for scores, standings, team info
        - politics: NewsAPI for recent headlines
        - crypto:   CoinGecko for price/volume data
        - macro:    FRED for economic indicators, EIA for energy data

    All methods are fault-tolerant: partial failures return whatever data
    was successfully fetched rather than raising exceptions.
    """

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MiroFish-AutoResearcher/1.0",
            "Accept": "application/json",
        })
        self._newsapi_key: Optional[str] = os.environ.get("NEWSAPI_KEY")
        self._fred_key: Optional[str] = os.environ.get("FRED_API_KEY")
        self._eia_key: Optional[str] = os.environ.get("EIA_API_KEY")

    # -------------------------------------------------------------------
    # Public interface
    # -------------------------------------------------------------------

    def research(self, market_title: str, market_type: str) -> str:
        """Main entry point. Dispatches to the appropriate research method.

        Args:
            market_title: The prediction market title/question.
            market_type:  One of 'sports', 'politics', 'crypto', 'macro'.

        Returns:
            Formatted research text block suitable for seeding swarm simulations.
        """
        dispatch = {
            "sports": self._research_sports,
            "politics": self._research_politics,
            "crypto": self._research_crypto,
            "macro": self._research_macro,
        }

        handler = dispatch.get(market_type.lower().strip())
        if handler is None:
            logger.warning("Unknown market type '%s', attempting generic research", market_type)
            return self._research_generic(market_title)

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        header = (
            f"=== AUTO-RESEARCH: {market_type.upper()} ===\n"
            f"Market: {market_title}\n"
            f"Fetched: {timestamp}\n"
            f"{'=' * 50}\n\n"
        )

        try:
            body = handler(market_title)
        except Exception as exc:
            logger.exception("Top-level research failure for '%s'", market_title)
            body = f"[Research error: {exc}]\n"

        return header + body

    # -------------------------------------------------------------------
    # Sports research (ESPN public API)
    # -------------------------------------------------------------------

    def _research_sports(self, title: str) -> str:
        """Fetch sports data from ESPN public API.

        Extracts team names from the market title, resolves them to ESPN IDs,
        then pulls scoreboard and team-level information.

        Args:
            title: Market title, e.g. "Lakers vs Pistons moneyline".

        Returns:
            Formatted text with team records, recent scores, and standings.
        """
        teams = self._extract_teams(title)
        if not teams:
            return "[Could not identify any teams from title]\n"

        sections: List[str] = []

        # Determine league from first matched team
        league = teams[0][0]
        sport = teams[0][1]

        # --- Scoreboard (recent/upcoming games) ---
        scoreboard_text = self._fetch_espn_scoreboard(sport, league)
        if scoreboard_text:
            sections.append(f"--- {league.upper()} Scoreboard ---\n{scoreboard_text}")

        # --- Per-team info ---
        for _league, _sport, team_id, canonical in teams:
            team_text = self._fetch_espn_team(sport, _league, team_id, canonical)
            if team_text:
                sections.append(team_text)

        if not sections:
            return "[No sports data retrieved from ESPN]\n"

        return "\n\n".join(sections) + "\n"

    def _fetch_espn_scoreboard(self, sport: str, league: str) -> str:
        """Fetch current scoreboard from ESPN.

        Args:
            sport:  ESPN sport slug (e.g. 'basketball').
            league: ESPN league slug (e.g. 'nba').

        Returns:
            Formatted scoreboard text, or empty string on failure.
        """
        url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"
        try:
            resp = self.session.get(url, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("ESPN scoreboard fetch failed: %s", exc)
            return ""

        events = data.get("events", [])
        if not events:
            return "No games currently on scoreboard.\n"

        lines: List[str] = []
        for event in events[:8]:  # cap at 8 games
            name = event.get("name", "Unknown")
            status_obj = event.get("status", {})
            status_type = status_obj.get("type", {})
            status_text = status_type.get("shortDetail", "")

            competitions = event.get("competitions", [])
            score_line = ""
            if competitions:
                comp = competitions[0]
                competitors = comp.get("competitors", [])
                parts = []
                for c in competitors:
                    team_name = c.get("team", {}).get("shortDisplayName", "?")
                    score = c.get("score", "?")
                    record_items = c.get("records", [])
                    record = record_items[0].get("summary", "") if record_items else ""
                    rec_str = f" ({record})" if record else ""
                    parts.append(f"{team_name}{rec_str}: {score}")
                score_line = " | ".join(parts)

            lines.append(f"  {name}")
            if score_line:
                lines.append(f"    {score_line}")
            if status_text:
                lines.append(f"    Status: {status_text}")

        return "\n".join(lines)

    def _fetch_espn_team(self, sport: str, league: str, team_id: str,
                         canonical: str) -> str:
        """Fetch team details from ESPN.

        Args:
            sport:     ESPN sport slug.
            league:    ESPN league slug.
            team_id:   ESPN numeric team ID.
            canonical: Human-readable team name.

        Returns:
            Formatted team info text, or empty string on failure.
        """
        url = (
            f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}"
            f"/teams/{team_id}"
        )
        try:
            resp = self.session.get(url, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("ESPN team fetch failed for %s: %s", canonical, exc)
            return ""

        team = data.get("team", {})
        display_name = team.get("displayName", canonical)
        record_obj = team.get("record", {})
        record_items = record_obj.get("items", [])

        lines = [f"--- {display_name} ---"]

        # Overall record
        for item in record_items:
            rec_type = item.get("type", "")
            summary = item.get("summary", "")
            if rec_type == "total" and summary:
                lines.append(f"  Record: {summary}")
            elif summary:
                lines.append(f"  {rec_type.capitalize()}: {summary}")

        # Standing
        standing_summary = team.get("standingSummary", "")
        if standing_summary:
            lines.append(f"  Standing: {standing_summary}")

        # Next event
        next_events = team.get("nextEvent", [])
        if next_events:
            nxt = next_events[0]
            nxt_name = nxt.get("name", "")
            nxt_date = nxt.get("date", "")
            if nxt_name:
                lines.append(f"  Next Game: {nxt_name} ({nxt_date})")

        return "\n".join(lines)

    # -------------------------------------------------------------------
    # Politics research (NewsAPI)
    # -------------------------------------------------------------------

    def _research_politics(self, title: str) -> str:
        """Fetch recent headlines related to the market title via NewsAPI.

        Extracts political entities from the title and uses them as search
        queries. Requires NEWSAPI_KEY environment variable.

        Args:
            title: Market title, e.g. "Will Iran reach a nuclear deal by 2026?"

        Returns:
            Formatted bullet list of recent headlines.
        """
        if not self._newsapi_key:
            return (
                "[NewsAPI key not configured. Set NEWSAPI_KEY env var.]\n"
                "Falling back to entity extraction only.\n\n"
                + self._extract_political_context(title)
            )

        entities = self._extract_political_entities(title)
        if not entities:
            # Fall back to using the whole title as query
            entities = [title[:100]]

        query = " OR ".join(entities[:5])

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "sortBy": "publishedAt",
            "pageSize": 5,
            "apiKey": self._newsapi_key,
            "language": "en",
        }

        try:
            resp = self.session.get(url, params=params, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("NewsAPI fetch failed: %s", exc)
            return f"[NewsAPI error: {exc}]\n" + self._extract_political_context(title)

        articles = data.get("articles", [])
        if not articles:
            return "No recent articles found.\n" + self._extract_political_context(title)

        lines = [f"--- Recent Headlines (query: {query}) ---"]
        for article in articles:
            pub = article.get("publishedAt", "")[:10]
            src = article.get("source", {}).get("name", "Unknown")
            headline = article.get("title", "No title")
            description = article.get("description", "")
            lines.append(f"  * [{pub}] {headline}")
            lines.append(f"    Source: {src}")
            if description:
                # Truncate long descriptions
                desc_short = description[:200] + ("..." if len(description) > 200 else "")
                lines.append(f"    Summary: {desc_short}")

        return "\n".join(lines) + "\n"

    def _extract_political_entities(self, title: str) -> List[str]:
        """Pull political entity keywords from a market title.

        Args:
            title: The market title text.

        Returns:
            List of matched political entity keywords.
        """
        title_lower = title.lower()
        found = []
        for entity in POLITICAL_ENTITIES:
            if entity in title_lower:
                found.append(entity)
        return found

    def _extract_political_context(self, title: str) -> str:
        """Generate a minimal context block from entity extraction alone.

        Args:
            title: Market title.

        Returns:
            Text block listing detected entities.
        """
        entities = self._extract_political_entities(title)
        if entities:
            return f"Detected entities: {', '.join(entities)}\n"
        return "No known political entities detected in title.\n"

    # -------------------------------------------------------------------
    # Crypto research (CoinGecko)
    # -------------------------------------------------------------------

    def _research_crypto(self, title: str) -> str:
        """Fetch cryptocurrency data from CoinGecko.

        Identifies token names in the market title and pulls current
        price, volume, and change data.

        Args:
            title: Market title, e.g. "Will Bitcoin hit 100k by June?"

        Returns:
            Formatted data table with price, volume, and change metrics.
        """
        tokens = self._extract_crypto_tokens(title)
        if not tokens:
            return "[No cryptocurrency tokens identified in title]\n"

        sections: List[str] = []
        for token_id, display_name in tokens:
            section = self._fetch_coingecko(token_id, display_name)
            if section:
                sections.append(section)

        if not sections:
            return "[CoinGecko data fetch failed for all tokens]\n"

        return "\n\n".join(sections) + "\n"

    def _extract_crypto_tokens(self, title: str) -> List[Tuple[str, str]]:
        """Identify crypto tokens mentioned in the title.

        Args:
            title: Market title.

        Returns:
            List of (coingecko_id, display_name) tuples.
        """
        title_lower = title.lower()
        found: List[Tuple[str, str]] = []
        seen_ids: set = set()

        # Check multi-word tokens first, then single words
        for keyword in sorted(CRYPTO_IDS.keys(), key=len, reverse=True):
            if keyword in title_lower:
                cg_id = CRYPTO_IDS[keyword]
                if cg_id not in seen_ids:
                    seen_ids.add(cg_id)
                    found.append((cg_id, keyword.upper()))

        return found

    def _fetch_coingecko(self, token_id: str, display_name: str) -> str:
        """Fetch token data from CoinGecko API.

        Args:
            token_id:     CoinGecko coin ID (e.g. 'bitcoin').
            display_name: Human-readable token name for output.

        Returns:
            Formatted text block with market data, or empty string on failure.
        """
        url = f"https://api.coingecko.com/api/v3/coins/{token_id}"
        params = {
            "localization": "false",
            "tickers": "false",
            "community_data": "false",
            "developer_data": "false",
            "sparkline": "false",
        }

        try:
            resp = self.session.get(url, params=params, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("CoinGecko fetch failed for %s: %s", token_id, exc)
            return ""

        market_data = data.get("market_data", {})
        if not market_data:
            return f"--- {display_name} ---\n  [No market data available]\n"

        current_price = market_data.get("current_price", {}).get("usd", "N/A")
        change_24h = market_data.get("price_change_percentage_24h", "N/A")
        change_7d = market_data.get("price_change_percentage_7d", "N/A")
        change_30d = market_data.get("price_change_percentage_30d", "N/A")
        volume_24h = market_data.get("total_volume", {}).get("usd", "N/A")
        market_cap = market_data.get("market_cap", {}).get("usd", "N/A")
        ath = market_data.get("ath", {}).get("usd", "N/A")
        ath_change = market_data.get("ath_change_percentage", {}).get("usd", "N/A")

        lines = [
            f"--- {data.get('name', display_name)} ({data.get('symbol', '?').upper()}) ---",
            f"  Price:        ${self._fmt_number(current_price)}",
            f"  24h Change:   {self._fmt_pct(change_24h)}",
            f"  7d Change:    {self._fmt_pct(change_7d)}",
            f"  30d Change:   {self._fmt_pct(change_30d)}",
            f"  24h Volume:   ${self._fmt_number(volume_24h)}",
            f"  Market Cap:   ${self._fmt_number(market_cap)}",
            f"  ATH:          ${self._fmt_number(ath)} ({self._fmt_pct(ath_change)} from ATH)",
        ]

        return "\n".join(lines)

    # -------------------------------------------------------------------
    # Macro research (FRED + EIA)
    # -------------------------------------------------------------------

    def _research_macro(self, title: str) -> str:
        """Fetch macroeconomic indicators from FRED and EIA.

        Pulls key economic data series: interest rates, CPI, unemployment,
        GDP, treasury yields. Also fetches oil price data from EIA.

        Args:
            title: Market title, e.g. "Fed rate decision June 2026".

        Returns:
            Formatted text with latest data points for each series.
        """
        sections: List[str] = []

        # --- FRED data ---
        fred_section = self._fetch_fred_data(title)
        if fred_section:
            sections.append(fred_section)

        # --- EIA oil data ---
        oil_section = self._fetch_eia_oil()
        if oil_section:
            sections.append(oil_section)

        if not sections:
            return "[No macro data retrieved. Check FRED_API_KEY and EIA_API_KEY env vars.]\n"

        return "\n\n".join(sections) + "\n"

    def _fetch_fred_data(self, title: str) -> str:
        """Fetch economic data from FRED API.

        Args:
            title: Market title (used to prioritize relevant series).

        Returns:
            Formatted text block with FRED data, or empty string on failure.
        """
        if not self._fred_key:
            return "[FRED_API_KEY not set. Skipping FRED data.]\n"

        # Determine which series are most relevant based on title keywords
        title_lower = title.lower()
        series_to_fetch = list(FRED_SERIES.keys())

        # Prioritize rate-related series for rate-related markets
        if any(kw in title_lower for kw in ["rate", "fed", "fomc", "interest", "monetary"]):
            priority = ["FEDFUNDS", "DGS10", "DGS2", "T10Y2Y", "MORTGAGE30US"]
            series_to_fetch = priority + [s for s in series_to_fetch if s not in priority]

        lines = ["--- FRED Economic Indicators ---"]
        fetched_any = False

        for series_id in series_to_fetch:
            series_name = FRED_SERIES[series_id]
            url = "https://api.stlouisfed.org/fred/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self._fred_key,
                "file_type": "json",
                "limit": 5,
                "sort_order": "desc",
            }

            try:
                resp = self.session.get(url, params=params, timeout=HTTP_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.warning("FRED fetch failed for %s: %s", series_id, exc)
                continue

            observations = data.get("observations", [])
            if not observations:
                continue

            fetched_any = True
            latest = observations[0]
            value = latest.get("value", "N/A")
            date = latest.get("date", "N/A")

            # Show trend if we have multiple observations
            trend = ""
            if len(observations) >= 2:
                prev_val = observations[1].get("value", "")
                try:
                    curr_f = float(value)
                    prev_f = float(prev_val)
                    diff = curr_f - prev_f
                    arrow = "^" if diff > 0 else ("v" if diff < 0 else "=")
                    trend = f" {arrow} (prev: {prev_val})"
                except (ValueError, TypeError):
                    pass

            lines.append(f"  {series_name} ({series_id}): {value} [{date}]{trend}")

        if not fetched_any:
            return ""

        return "\n".join(lines)

    def _fetch_eia_oil(self) -> str:
        """Fetch crude oil spot prices from EIA API.

        Returns:
            Formatted text with recent oil prices, or empty string on failure.
        """
        if not self._eia_key:
            return "[EIA_API_KEY not set. Skipping oil data.]\n"

        url = "https://api.eia.gov/v2/petroleum/pri/spt/data/"
        params = {
            "api_key": self._eia_key,
            "frequency": "daily",
            "data[0]": "value",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 5,
        }

        try:
            resp = self.session.get(url, params=params, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("EIA oil data fetch failed: %s", exc)
            return ""

        response_data = data.get("response", {}).get("data", [])
        if not response_data:
            return ""

        lines = ["--- Crude Oil Spot Prices (EIA) ---"]
        for entry in response_data[:5]:
            period = entry.get("period", "N/A")
            value = entry.get("value", "N/A")
            product = entry.get("product-name", "Crude Oil")
            lines.append(f"  {product}: ${value}/bbl [{period}]")

        return "\n".join(lines)

    # -------------------------------------------------------------------
    # Generic / fallback research
    # -------------------------------------------------------------------

    def _research_generic(self, title: str) -> str:
        """Fallback research for unknown market types.

        Attempts to identify the most likely category and fetch what it can.

        Args:
            title: Market title text.

        Returns:
            Whatever data could be gathered.
        """
        sections: List[str] = []

        # Try team extraction
        teams = self._extract_teams(title)
        if teams:
            sections.append("[Auto-detected: sports market]")
            sections.append(self._research_sports(title))

        # Try crypto extraction
        tokens = self._extract_crypto_tokens(title)
        if tokens:
            sections.append("[Auto-detected: crypto market]")
            sections.append(self._research_crypto(title))

        # Try political entities
        entities = self._extract_political_entities(title)
        if entities:
            sections.append("[Auto-detected: political entities]")
            sections.append(self._research_politics(title))

        if not sections:
            sections.append("[No domain-specific data sources matched. Returning title only.]")
            sections.append(f"Title: {title}")

        return "\n".join(sections) + "\n"

    # -------------------------------------------------------------------
    # Entity extraction helpers
    # -------------------------------------------------------------------

    def _extract_teams(self, title: str) -> List[Tuple[str, str, str, str]]:
        """Extract team names from a market title using keyword matching.

        Handles common formats like:
            "Lakers vs Pistons"
            "Lakers - Pistons moneyline"
            "Will the Chiefs win the Super Bowl?"
            "Celtics over/under 110.5"

        Args:
            title: Market title text.

        Returns:
            List of (league, sport, espn_id, canonical_name) tuples for
            each matched team, deduplicated.
        """
        title_lower = title.lower()
        # Clean up common separators
        title_clean = re.sub(r"[^\w\s]", " ", title_lower)
        title_clean = re.sub(r"\s+", " ", title_clean).strip()

        found: List[Tuple[str, str, str, str]] = []
        seen_ids: set = set()

        # Try multi-word team names first (e.g., "golden state", "green bay")
        for keyword in sorted(ALL_TEAMS.keys(), key=len, reverse=True):
            if " " in keyword and keyword in title_clean:
                league, sport, team_id, canonical = ALL_TEAMS[keyword]
                unique_key = f"{league}_{team_id}"
                if unique_key not in seen_ids:
                    seen_ids.add(unique_key)
                    found.append((league, sport, team_id, canonical))

        # Then check single-word names
        words = set(title_clean.split())
        for word in words:
            if word in ALL_TEAMS:
                league, sport, team_id, canonical = ALL_TEAMS[word]
                unique_key = f"{league}_{team_id}"
                if unique_key not in seen_ids:
                    seen_ids.add(unique_key)
                    found.append((league, sport, team_id, canonical))

        return found

    # -------------------------------------------------------------------
    # Formatting utilities
    # -------------------------------------------------------------------

    @staticmethod
    def _fmt_number(value: object) -> str:
        """Format a number with commas for readability.

        Args:
            value: Numeric value (int, float, or string).

        Returns:
            Formatted string, e.g. '1,234,567.89'.
        """
        if value is None or value == "N/A":
            return "N/A"
        try:
            num = float(value)
            if num >= 1_000_000_000:
                return f"{num / 1_000_000_000:,.2f}B"
            elif num >= 1_000_000:
                return f"{num / 1_000_000:,.2f}M"
            elif num >= 1_000:
                return f"{num:,.2f}"
            elif num >= 1:
                return f"{num:.2f}"
            else:
                # Small numbers, show more precision
                return f"{num:.6f}"
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def _fmt_pct(value: object) -> str:
        """Format a percentage value.

        Args:
            value: Numeric percentage (e.g. 5.23 means 5.23%).

        Returns:
            Formatted string like '+5.23%' or '-2.10%'.
        """
        if value is None or value == "N/A":
            return "N/A"
        try:
            num = float(value)
            sign = "+" if num >= 0 else ""
            return f"{sign}{num:.2f}%"
        except (ValueError, TypeError):
            return str(value)


# -----------------------------------------------------------------------
# CLI entry point
# -----------------------------------------------------------------------

def main() -> None:
    """Command-line interface for the auto-researcher."""
    parser = argparse.ArgumentParser(
        description="MiroFish Auto-Researcher: gather real-world data for swarm simulations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python auto_researcher.py "Lakers vs Pistons" sports\n'
            '  python auto_researcher.py "Will Bitcoin hit 100k?" crypto\n'
            '  python auto_researcher.py "Fed rate cut June" macro\n'
            '  python auto_researcher.py "Iran nuclear deal" politics\n'
        ),
    )
    parser.add_argument("market_title", help="The prediction market title/question.")
    parser.add_argument(
        "market_type",
        choices=["sports", "politics", "crypto", "macro", "auto"],
        help="Market vertical (or 'auto' to attempt detection).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose/debug logging.",
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    researcher = AutoResearcher()

    if args.market_type == "auto":
        # Try to auto-detect market type
        result = researcher.research(args.market_title, "auto")
    else:
        result = researcher.research(args.market_title, args.market_type)

    print(result)


if __name__ == "__main__":
    main()
