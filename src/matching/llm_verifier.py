"""
TerminatorBot - LLM Match Verifier

Optional component that uses an LLM to verify whether two markets
from different platforms are asking the exact same question.

Only called for borderline fuzzy matches (score 70-85).
"""

from __future__ import annotations

import logging
from typing import Optional

from platforms.base import UnifiedMarket
from config import Config

logger = logging.getLogger(__name__)


class LLMMatchVerifier:
    """
    Uses OpenAI or another LLM to verify market matches.

    Falls back to fuzzy-only matching if no API key is configured.
    """

    def __init__(self, api_key: str = ""):
        self._api_key = api_key or Config.OPENAI_API_KEY
        self._client = None
        self._enabled = bool(self._api_key)

        if self._enabled:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self._api_key)
                logger.info("LLM verifier enabled (OpenAI)")
            except ImportError:
                logger.warning("openai package not installed, LLM verifier disabled")
                self._enabled = False

    def verify_match(self, market_a: UnifiedMarket, market_b: UnifiedMarket) -> bool:
        """
        Ask the LLM whether two markets resolve on the same event.

        Returns True if the LLM confirms they are the same.
        """
        if not self._enabled or not self._client:
            return False

        prompt = (
            "Compare these two prediction markets:\n"
            f"Market A ({market_a.platform}): {market_a.title}\n"
            f"  Description: {market_a.description[:200]}\n"
            f"  Close date: {market_a.close_date}\n\n"
            f"Market B ({market_b.platform}): {market_b.title}\n"
            f"  Description: {market_b.description[:200]}\n"
            f"  Close date: {market_b.close_date}\n\n"
            "Are these two markets asking the exact same question and "
            "resolving on the exact same event and timeframe?\n"
            "Answer ONLY with 'MATCH' or 'NO_MATCH'."
        )

        try:
            response = self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0,
            )
            answer = response.choices[0].message.content.strip().upper()
            is_match = "MATCH" in answer and "NO_MATCH" not in answer
            logger.info(
                "LLM verify: %s vs %s -> %s",
                market_a.title[:30], market_b.title[:30], answer,
            )
            return is_match
        except Exception as e:
            logger.error("LLM verification failed: %s", e)
            return False
