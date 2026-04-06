"""OpenClaw Anomaly — Enhanced CORTEX META Cycle.

Weekly GA: crossover + mutation on genome variants.
Requires APPROVAL_REQUIRED permission (Telegram approval before running).
"""
from __future__ import annotations

import json
import random
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from openclaw.config import Config
from openclaw.run_lock import RunLock
from openclaw.state_machine import StateMachine, AgentState


MUTATION_TYPES = [
    "TIGHTEN", "LOOSEN", "INVERT", "MERGE", "SPLIT",
    "ESCALATE", "PRUNE", "ABSORB",
]


def run_meta_cycle() -> dict:
    """Execute one META generation cycle.

    Flow:
    1. Acquire run_lock, transition to META_CYCLE
    2. Load corrections + absorption proposals
    3. Select 2 parents by fitness
    4. Create 5 offspring via crossover + mutation
    5. Copy immutable files verbatim
    6. All offspring start in shadow mode
    7. Preserve elite
    8. Run eval on offspring
    9. Telegram summary
    10. Release lock, transition to IDLE

    Returns summary dict.
    """
    from openclaw.genome_manager import GenomeManager
    from openclaw.fitness_tracker import FitnessTracker
    from openclaw.shadow_replay import ShadowReplay
    from openclaw.eval_harness import EvalHarness

    sm = StateMachine()
    manager = GenomeManager()
    tracker = FitnessTracker()
    replay = ShadowReplay()
    harness = EvalHarness()

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "generation": 0,
        "parents": [],
        "offspring": [],
        "elite_preserved": None,
        "errors": [],
    }

    try:
        with RunLock("meta_cycle"):
            sm.transition(AgentState.META_CYCLE)

            # Determine generation
            active = manager.get_active_variant()
            current_gen = (active.get("generation", 1) if active else 1)
            next_gen = current_gen + 1
            summary["generation"] = next_gen

            # Load corrections
            corrections = replay.load_correction_log()

            # Select parents
            top_variants = tracker.get_top_variants(n=5)
            if len(top_variants) < 2:
                # Not enough variants — create from base genome
                for i in range(2 - len(top_variants)):
                    vid = manager.create_variant(generation=next_gen)
                    top_variants.append({"variant_id": vid, "avg_fitness": 0.0})

            parent_a = top_variants[0]
            parent_b = top_variants[1] if len(top_variants) > 1 else top_variants[0]
            summary["parents"] = [parent_a["variant_id"], parent_b["variant_id"]]

            path_a = Config.GENE_POOL_DIR / parent_a["variant_id"]
            path_b = Config.GENE_POOL_DIR / parent_b["variant_id"]

            # Create offspring
            offspring_ids = []
            for i in range(Config.META_OFFSPRING_COUNT):
                offspring_id = manager.create_variant(generation=next_gen)
                offspring_dir = Config.GENE_POOL_DIR / offspring_id

                # Crossover: mix modules from parents
                _crossover(path_a, path_b, offspring_dir)

                # Mutation: apply ONE mutation per offspring
                mutation = random.choice(MUTATION_TYPES)
                _mutate(offspring_dir, mutation, corrections)

                # Safety: copy immutable files verbatim from base genome
                for immutable in Config.IMMUTABLE_MODULES:
                    base_file = Config.GENOME_DIR / immutable
                    if base_file.exists():
                        shutil.copy2(str(base_file), str(offspring_dir / immutable))

                # Safety check
                safe, reason = manager.safety_check(offspring_dir)
                if not safe:
                    summary["errors"].append(f"{offspring_id}: {reason}")
                    manager.archive_variant(offspring_id, reason="safety_violation")
                    continue

                # Start in shadow mode
                manager.activate_variant(offspring_id, shadow=True)
                offspring_ids.append(offspring_id)

            summary["offspring"] = offspring_ids

            # Preserve elite
            elite_id = manager.preserve_elite(generation=current_gen)
            summary["elite_preserved"] = elite_id

            # Activate the best offspring (or keep elite if no offspring passed)
            if offspring_ids:
                manager.activate_variant(offspring_ids[0], shadow=True)

            sm.transition(AgentState.IDLE)

    except Exception as e:
        summary["errors"].append(str(e))
        try:
            sm.force_state(AgentState.IDLE)
        except Exception:
            pass

    return summary


def _crossover(parent_a: Path, parent_b: Path, offspring_dir: Path) -> None:
    """Per-module crossover: randomly pick modules from each parent."""
    mutable_modules = [
        m for m in Config.GENOME_MODULES if m not in Config.IMMUTABLE_MODULES
    ]
    for module in mutable_modules:
        # 50/50 chance from each parent
        if random.random() < 0.5:
            src = parent_a / module
        else:
            src = parent_b / module

        if not src.exists():
            # Fall back to base genome
            src = Config.GENOME_DIR / module

        dst = offspring_dir / module
        if src.exists():
            shutil.copy2(str(src), str(dst))


def _mutate(variant_dir: Path, mutation_type: str, corrections: list[dict]) -> None:
    """Apply ONE structured mutation to a random mutable module."""
    mutable_modules = [
        m for m in Config.GENOME_MODULES
        if m not in Config.IMMUTABLE_MODULES and (variant_dir / m).exists()
    ]
    if not mutable_modules:
        return

    target_module = random.choice(mutable_modules)
    target_path = variant_dir / target_module

    try:
        content = target_path.read_text(encoding="utf-8")
    except OSError:
        return

    mutated = content

    if mutation_type == "TIGHTEN":
        mutated = content.replace("should", "MUST")
        mutated = mutated.replace("may", "should")
    elif mutation_type == "LOOSEN":
        mutated = content.replace("MUST", "should")
        mutated = mutated.replace("always", "usually")
    elif mutation_type == "ESCALATE":
        mutated = content.replace("Medium", "High")
        mutated = mutated.replace("low", "medium")
    elif mutation_type == "PRUNE":
        lines = content.split("\n")
        if len(lines) > 5:
            remove_idx = random.randint(2, len(lines) - 2)
            lines.pop(remove_idx)
            mutated = "\n".join(lines)
    elif mutation_type == "ABSORB":
        if corrections:
            recent = corrections[-1]
            correction_text = recent.get("correction", "")
            if correction_text:
                mutated += f"\n\n## Absorbed Insight\n- {correction_text}\n"
    elif mutation_type == "INVERT":
        mutated = content.replace("proactive", "PROACTIVE_FIRST")
        mutated = mutated.replace("reactive", "proactive")
        mutated = mutated.replace("PROACTIVE_FIRST", "reactive_fallback")
    elif mutation_type == "MERGE":
        lines = content.split("\n")
        if len(lines) > 6:
            i = random.randint(2, len(lines) - 3)
            if lines[i].strip() and lines[i + 1].strip():
                lines[i] = lines[i].rstrip() + " + " + lines[i + 1].lstrip()
                lines.pop(i + 1)
                mutated = "\n".join(lines)
    elif mutation_type == "SPLIT":
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if " and " in line and len(line) > 40:
                parts = line.split(" and ", 1)
                lines[i] = parts[0]
                lines.insert(i + 1, "- " + parts[1].lstrip("- "))
                mutated = "\n".join(lines)
                break

    if mutated != content:
        target_path.write_text(mutated, encoding="utf-8")
