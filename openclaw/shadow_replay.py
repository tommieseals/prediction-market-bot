"""OpenClaw Anomaly — Shadow-Mode Replay Engine.

Test new variants against historical corrections before going live.
48h shadow period: simulate actions, score against past corrections,
graduate passing variants to active rotation.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from openclaw.config import Config


class ShadowReplay:
    """Test variants against historical corrections."""

    def __init__(self, correction_log_path: Path | None = None):
        self.log_path = correction_log_path or Config.CORRECTION_LOG_PATH

    def load_correction_log(self, limit: int = 50) -> list[dict]:
        """Read last N corrections from the JSONL log."""
        if not self.log_path.exists():
            return []
        entries = []
        try:
            with open(self.log_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except OSError:
            return []
        return entries[-limit:]

    def log_correction(self, correction: str, my_approach: str, severity: int, task_id: str) -> dict:
        """Append a correction to the log."""
        from datetime import datetime, timezone
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correction": correction,
            "my_approach": my_approach,
            "severity": severity,
            "task_id": task_id,
        }
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass
        return entry

    def simulate_variant_on_task(self, variant_modules: dict[str, str], past_correction: dict) -> float:
        """Check if variant's rules would have avoided the correction.

        Uses keyword matching: does the variant's genome content address
        the issue described in the correction?

        Returns score: +1.0 if addressed, 0.0 if neutral, -1.0 if likely worse.
        """
        correction_text = past_correction.get("correction", "").lower()
        approach_text = past_correction.get("my_approach", "").lower()
        severity = past_correction.get("severity", -1)

        # Build word set from correction
        correction_words = set(correction_text.split())
        approach_words = set(approach_text.split())
        problem_words = correction_words | approach_words

        # Check all variant modules for relevant content
        genome_text = " ".join(variant_modules.values()).lower()
        genome_words = Counter(genome_text.split())

        # Score: how many problem-related words appear in the genome
        overlap = sum(1 for w in problem_words if w in genome_words and len(w) > 3)

        if overlap >= 3:
            return 1.0  # variant likely addresses this issue
        elif overlap >= 1:
            return 0.0  # neutral
        else:
            return -0.5  # variant doesn't address the problem at all

    def simulate_autonomy_on_task(self, variant_modules: dict[str, str], past_correction: dict) -> float:
        """Check if variant includes money/revenue/follow-up keywords.

        Returns bonus score 0.0 - 1.0 for autonomy alignment.
        """
        autonomy_keywords = {
            "money", "revenue", "profit", "follow-up", "followup", "proactive",
            "opportunity", "business", "trade", "deal", "outreach", "stalled",
        }
        genome_text = " ".join(variant_modules.values()).lower()
        matches = sum(1 for kw in autonomy_keywords if kw in genome_text)
        return min(1.0, matches / 5.0)

    def run_shadow_replay(
        self,
        variant_id: str,
        generation: int,
        variant_path: Path | str,
    ) -> float:
        """Score a variant against all recent corrections.

        Returns average replay score 0.0 - 10.0.
        """
        variant_path = Path(variant_path)
        corrections = self.load_correction_log()
        if not corrections:
            return 5.0  # neutral score if no corrections yet

        # Load variant modules
        modules = {}
        for module_name in Config.GENOME_MODULES:
            module_file = variant_path / module_name
            if module_file.exists():
                try:
                    modules[module_name] = module_file.read_text(encoding="utf-8")
                except OSError:
                    continue

        if not modules:
            # Fall back to base genome
            for module_name in Config.GENOME_MODULES:
                base_file = Config.GENOME_DIR / module_name
                if base_file.exists():
                    try:
                        modules[module_name] = base_file.read_text(encoding="utf-8")
                    except OSError:
                        continue

        scores = []
        for correction in corrections:
            task_score = self.simulate_variant_on_task(modules, correction)
            autonomy_score = self.simulate_autonomy_on_task(modules, correction)
            combined = (task_score + autonomy_score) / 2.0
            scores.append(combined)

        if not scores:
            return 5.0

        # Normalize from [-0.75, 1.0] range to [0, 10] range
        raw_avg = sum(scores) / len(scores)
        normalized = (raw_avg + 0.75) / 1.75 * 10.0
        return max(0.0, min(10.0, normalized))
