"""OpenClaw Anomaly — Gene Pool & Variant Manager.

Manage the lifecycle of 5-8 active variants: creation, scoring,
archiving, elite preservation, selection (70/30 exploit/explore),
shadow graduation, safety checks, and SOUL.md assembly.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from openclaw.config import Config
from openclaw.genome_assembler import assemble_and_write


class GenomeManager:
    """Variant lifecycle management."""

    def __init__(self):
        self.pool_dir = Config.GENE_POOL_DIR
        self.elite_dir = Config.ELITE_DIR
        self.archive_dir = Config.ARCHIVE_DIR
        self.active_path = Config.ACTIVE_VARIANT_PATH

    def get_active_variant(self) -> dict | None:
        """Read active_variant.json."""
        if not self.active_path.exists():
            return None
        try:
            return json.loads(self.active_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def get_active_variant_path(self) -> Path | None:
        """Get filesystem path to active variant directory."""
        active = self.get_active_variant()
        if not active:
            return None
        variant_dir = self.pool_dir / active["variant_id"]
        if variant_dir.exists():
            return variant_dir
        return None

    def create_variant(
        self,
        name: str | None = None,
        generation: int = 1,
        parent_path: Path | None = None,
    ) -> str:
        """Create a new variant directory with genome files.

        If parent_path provided, copies from parent. Otherwise from base genome.
        Returns variant_id.
        """
        if name is None:
            hex_id = hashlib.sha256(f"{time.time()}:{random.random()}".encode()).hexdigest()[:8]
            name = f"variant_{hex_id}_gen{generation:02d}"

        variant_dir = self.pool_dir / name
        variant_dir.mkdir(parents=True, exist_ok=True)

        source = parent_path or Config.GENOME_DIR
        for module in Config.GENOME_MODULES:
            src = source / module
            dst = variant_dir / module
            if src.exists() and not dst.exists():
                shutil.copy2(str(src), str(dst))

        return name

    def select_variant(self) -> str | None:
        """Select a variant using 70/30 exploit/explore strategy.

        Also checks shadow graduation: if active variant has shadow_mode=True
        and 48h elapsed, auto-graduate it.
        """
        # Check shadow graduation first
        active = self.get_active_variant()
        if active and active.get("shadow_mode"):
            started = active.get("shadow_started_at")
            if started:
                try:
                    start_dt = datetime.fromisoformat(started)
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - start_dt).total_seconds() / 3600
                    if elapsed >= Config.SHADOW_PERIOD_HOURS:
                        # Graduate
                        active["shadow_mode"] = False
                        self._write_active(active)
                except (ValueError, TypeError):
                    pass

        variants = self._list_active_variants()
        if not variants:
            return active["variant_id"] if active else None

        # Get fitness scores
        try:
            from openclaw.fitness_tracker import FitnessTracker
            tracker = FitnessTracker()
            scored = []
            for v in variants:
                fitness = tracker.get_variant_fitness(v)
                scored.append((v, fitness))
            scored.sort(key=lambda x: x[1], reverse=True)
        except Exception:
            scored = [(v, 0.0) for v in variants]

        if not scored:
            return active["variant_id"] if active else None

        # 70% exploit: pick from top 2
        if random.random() < Config.EXPLOIT_RATIO and len(scored) >= 2:
            return random.choice([scored[0][0], scored[1][0]])
        else:
            # 30% explore: weighted random
            total = sum(max(s, 0.1) for _, s in scored)
            r = random.uniform(0, total)
            cumulative = 0
            for name, score in scored:
                cumulative += max(score, 0.1)
                if cumulative >= r:
                    return name
            return scored[0][0]

    def activate_variant(self, variant_id: str, shadow: bool = False) -> None:
        """Set a variant as active and regenerate SOUL.md."""
        variant_dir = self.pool_dir / variant_id
        if not variant_dir.exists():
            raise FileNotFoundError(f"Variant not found: {variant_id}")

        data = {
            "variant_id": variant_id,
            "generation": self._parse_generation(variant_id),
            "activated_at": datetime.now(timezone.utc).isoformat(),
            "shadow_mode": shadow,
            "shadow_started_at": datetime.now(timezone.utc).isoformat() if shadow else None,
            "fitness_score": 0.0,
        }
        self._write_active(data)
        assemble_and_write(variant_dir)

    def archive_variant(self, variant_id: str, reason: str = "archived") -> None:
        """Move a variant to the archive directory."""
        src = self.pool_dir / variant_id
        if not src.exists():
            return
        dst = self.archive_dir / f"{variant_id}_{reason}"
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            shutil.move(str(item), str(dst / item.name))
        src.rmdir()

    def preserve_elite(self, generation: int | None = None) -> str | None:
        """Copy the top-fitness variant to elite directory."""
        try:
            from openclaw.fitness_tracker import FitnessTracker
            tracker = FitnessTracker()
            top = tracker.get_top_variants(generation=generation, n=1)
            if not top:
                return None
            top_id = top[0]["variant_id"]
        except Exception:
            # Fall back to active variant
            active = self.get_active_variant()
            if not active:
                return None
            top_id = active["variant_id"]

        src = self.pool_dir / top_id
        if not src.exists():
            return None

        # Clear elite dir and copy
        if self.elite_dir.exists():
            shutil.rmtree(str(self.elite_dir))
        self.elite_dir.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            shutil.copy2(str(item), str(self.elite_dir / item.name))
        return top_id

    def rollback_to_elite(self) -> bool:
        """Swap active variant to elite. Returns True on success."""
        if not self.elite_dir.exists() or not any(self.elite_dir.iterdir()):
            return False

        # Create a new variant from elite
        elite_variant = self.create_variant(
            name=f"elite_rollback_gen{self._current_gen():02d}",
            generation=self._current_gen(),
            parent_path=self.elite_dir,
        )
        self.activate_variant(elite_variant, shadow=False)
        return True

    def safety_check(self, variant_dir: Path | str) -> tuple[bool, str]:
        """Byte-for-byte compare both immutable files against base genome.

        Returns (safe, reason). Either mismatch = disqualification.
        """
        variant_dir = Path(variant_dir)
        for module in Config.IMMUTABLE_MODULES:
            base_file = Config.GENOME_DIR / module
            variant_file = variant_dir / module
            if not base_file.exists():
                continue
            if not variant_file.exists():
                return False, f"Immutable module missing from variant: {module}"
            base_content = base_file.read_bytes()
            variant_content = variant_file.read_bytes()
            if base_content != variant_content:
                return False, f"IMMUTABLE MODULE MUTATED: {module}"
        return True, "Safety check passed."

    def _list_active_variants(self) -> list[str]:
        """List non-archived variant directories in the gene pool."""
        if not self.pool_dir.exists():
            return []
        return [
            d.name for d in self.pool_dir.iterdir()
            if d.is_dir() and d.name not in ("elite", "archive")
        ]

    def _write_active(self, data: dict) -> None:
        tmp = self.active_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(str(tmp), str(self.active_path))

    def _parse_generation(self, variant_id: str) -> int:
        try:
            parts = variant_id.split("gen")
            if len(parts) >= 2:
                return int(parts[-1].lstrip("0") or "1")
        except (ValueError, IndexError):
            pass
        return 1

    def _current_gen(self) -> int:
        active = self.get_active_variant()
        return active.get("generation", 1) if active else 1


# Re-export for convenience (canonical import path is meta_cycle)
def run_meta_cycle() -> dict:
    from openclaw.meta_cycle import run_meta_cycle as _run
    return _run()
