"""OpenClaw Anomaly — First-Run Bootstrap.

Creates all directories, generates PRINCIPAL_ID + INSTALL_ID,
validates dependencies, creates seed files, and generates the
first variant from base genome.

Usage:
  Interactive:   python -m openclaw.bootstrap
  CLI flag:      python -m openclaw.bootstrap --principal-id=abc123
  Env var:       OGE_PRINCIPAL_ID=abc123 python -m openclaw.bootstrap
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from openclaw.config import Config


def generate_owner_id() -> str:
    """Generate a new PRINCIPAL_ID (random SHA-256). Used once on first install."""
    return hashlib.sha256(os.urandom(32)).hexdigest()


def generate_machine_id() -> str:
    """Generate INSTALL_ID from machine fingerprint."""
    raw = f"{platform.node()}:{os.getlogin()}:{platform.system()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _resolve_principal_id(cli_id: str | None = None) -> str:
    """Resolve PRINCIPAL_ID from CLI > env > existing file > interactive."""
    # 1. CLI flag
    if cli_id:
        return cli_id
    # 2. Env var
    env_id = os.environ.get("OGE_PRINCIPAL_ID")
    if env_id:
        return env_id
    # 3. Existing file
    existing = Config.get_principal_id()
    if existing:
        return existing
    # 4. Interactive
    print("\n--- PRINCIPAL_ID Setup ---")
    print("PRINCIPAL_ID is the owner identity (portable across machines).")
    choice = input("First install (new) or deploying existing (paste)? [new/paste]: ").strip().lower()
    if choice == "paste":
        pid = input("Paste PRINCIPAL_ID: ").strip()
        if pid:
            return pid
    return generate_owner_id()


def _create_dirs() -> None:
    """Create all required directories."""
    dirs = [
        Config.BASE_DIR,
        Config.GENOME_DIR,
        Config.GENE_POOL_DIR,
        Config.ELITE_DIR,
        Config.ARCHIVE_DIR,
        Config.QUARANTINE_DIR,
        Config.AUDITS_DIR,
        Config.TESTS_DIR,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    print(f"  Directories: {len(dirs)} created/verified")


def _create_seed_files() -> int:
    """Create empty seed files for all runtime artifacts."""
    seeds: dict[Path, str] = {
        Config.CORRECTION_LOG_PATH: "",
        Config.TRADER_MEMORY_PATH: "",
        Config.PAPERCLIP_AUDIT_PATH: "",
        Config.INCIDENTS_PATH: "",
        Config.LAST_SESSION_PATH: "# Last Session\n\nNo sessions recorded yet.\n",
        Config.ACTIVE_VARIANT_PATH: json.dumps({
            "variant_id": "variant_A_gen01",
            "generation": 1,
            "activated_at": datetime.now(timezone.utc).isoformat(),
            "shadow_mode": False,
            "shadow_started_at": None,
            "fitness_score": 0.0,
        }, indent=2),
        Config.WORKER_REGISTRY_PATH: json.dumps({"workers": []}, indent=2),
        Config.ACTIVE_MISSION_PATH: json.dumps({
            "mission_id": None,
            "state": "idle",
            "priority": 0,
            "started_at": None,
            "last_checkpoint_step": None,
            "last_checkpoint_at": None,
            "checkpoint_state_blob": None,
            "outcome": None,
            "closed_at": None,
        }, indent=2),
        Config.MATRIX_INVENTORY_PATH: json.dumps({
            "schema_version": 1,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "machines": [
                {"id": "jarvis", "ip": "100.89.75.126", "os": "macOS", "role": "OGE controller + shared memory"},
                {"id": "tom", "ip": "100.88.105.106", "os": "macOS", "role": "job automation + dashboards"},
                {"id": "rtx", "ip": "100.115.12.91", "os": "Windows", "role": "primary compute"},
            ],
            "projects": [
                {"id": "legion", "machine_id": "tom", "risk_class": "medium"},
                {"id": "terminatorbot", "machine_id": "rtx", "risk_class": "medium"},
                {"id": "taskbot", "machine_id": "rtx", "risk_class": "medium"},
                {"id": "shared_memory", "machine_id": "jarvis", "risk_class": "low"},
                {"id": "monitoring", "machine_id": "jarvis", "risk_class": "low"},
            ],
            "providers": [
                {"id": "openai", "auth": "SecretRef"},
                {"id": "anthropic", "auth": "SecretRef"},
                {"id": "gemini", "auth": "SecretRef"},
                {"id": "openrouter", "auth": "SecretRef"},
            ],
            "keys": [],
            "models": [],
        }, indent=2),
        Config.KEYS_LEDGER_PATH: json.dumps({"keys": []}, indent=2),
        Config.PENDING_APPROVALS_PATH: json.dumps([], indent=2),
        Config.MEMORY_CORE_PATH: json.dumps({
            "schema_version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "loyalty_digest": "Single principal: Rusty. No successor. No replacement.",
            "active_goals": [
                "Advance Rusty and Jarvis as one unit",
                "Break the matrix (get wealthy)",
                "Absorb breakthroughs from Anthropic and competitors",
                "Maintain workspace health across all machines",
            ],
            "recent_revenue_state": None,
            "current_variant": "variant_A_gen01",
        }, indent=2),
        Config.PROJECT_STATUS_PATH: json.dumps({
            "projects": [
                {
                    "project_name": "Legion",
                    "last_action_date": datetime.now(timezone.utc).isoformat(),
                    "days_idle": 0,
                    "next_action": "Check submission success rate",
                    "status": "active",
                },
                {
                    "project_name": "TerminatorBot",
                    "last_action_date": datetime.now(timezone.utc).isoformat(),
                    "days_idle": 0,
                    "next_action": "Improve arb detection accuracy",
                    "status": "active",
                },
                {
                    "project_name": "TaskBot",
                    "last_action_date": datetime.now(timezone.utc).isoformat(),
                    "days_idle": 0,
                    "next_action": "Review automation pipeline",
                    "status": "active",
                },
                {
                    "project_name": "Shared Memory",
                    "last_action_date": datetime.now(timezone.utc).isoformat(),
                    "days_idle": 0,
                    "next_action": "Validate integrity",
                    "status": "active",
                },
                {
                    "project_name": "Monitoring",
                    "last_action_date": datetime.now(timezone.utc).isoformat(),
                    "days_idle": 0,
                    "next_action": "Review alerting rules",
                    "status": "active",
                },
            ]
        }, indent=2),
        Config.PROJECT_ADAPTERS_PATH: json.dumps({
            "legion": {
                "owner_agent": "jarvis",
                "machine": "tom",
                "repo_path": "/Users/tommie/clawd/legion",
                "execution_scope": "remote_auto",
                "agent_recruitment": "full",
                "allowed_actions": ["read_status", "propose_fix", "apply_fix", "run_tests", "draft_followup"],
                "allowed_worker_types": ["monitor", "tester", "patcher"],
                "max_remote_workers": 3,
                "test_command": None,
                "rollback_command": "git checkout .",
                "risk_class": "medium",
                "identity_boundary": "project_only",
                "transport_profile": "ssh",
                "credential_scope": [],
                "worker_ttl_override": None,
                "approval_on": [],
                "current_goals": ["Fix submission pipeline", "Fix Gmail OAuth"],
                "blockers": ["Gmail OAuth reauth"],
                "success_metrics": ["submissions_per_day > 5"],
            },
            "terminatorbot": {
                "owner_agent": "jarvis",
                "machine": "rtx",
                "repo_path": "C:\\Users\\User\\clawd\\TerminatorBot",
                "execution_scope": "remote_assist",
                "agent_recruitment": "monitor_only",
                "allowed_actions": ["read_status", "propose_parameter_change"],
                "allowed_worker_types": ["monitor"],
                "max_remote_workers": 1,
                "test_command": None,
                "rollback_command": "git checkout .",
                "risk_class": "medium",
                "identity_boundary": "project_only",
                "transport_profile": "ssh",
                "credential_scope": [],
                "worker_ttl_override": None,
                "approval_on": ["parameter_change"],
                "current_goals": ["Improve arb detection accuracy"],
                "blockers": [],
                "success_metrics": ["profitable_trades_per_week > 0"],
            },
            "taskbot": {
                "owner_agent": "jarvis",
                "machine": "rtx",
                "repo_path": "C:\\Users\\User\\clawd\\taskbot",
                "execution_scope": "remote_assist",
                "agent_recruitment": "none",
                "allowed_actions": ["read_status"],
                "allowed_worker_types": [],
                "max_remote_workers": 0,
                "test_command": None,
                "rollback_command": "git checkout .",
                "risk_class": "low",
                "identity_boundary": "project_only",
                "transport_profile": "manual_only",
                "credential_scope": [],
                "worker_ttl_override": None,
                "approval_on": [],
                "current_goals": ["Review automation pipeline"],
                "blockers": [],
                "success_metrics": [],
            },
        }, indent=2),
    }

    created = 0
    for path, content in seeds.items():
        if not path.exists():
            path.write_text(content)
            created += 1
    print(f"  Seed files: {created} created, {len(seeds) - created} already existed")
    return created


def _create_first_variant() -> None:
    """Create variant_A_gen01/ from base genome files."""
    variant_dir = Config.GENE_POOL_DIR / "variant_A_gen01"
    if variant_dir.exists():
        print("  First variant: already exists")
        return
    variant_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for module in Config.GENOME_MODULES:
        src = Config.GENOME_DIR / module
        dst = variant_dir / module
        if src.exists():
            shutil.copy2(str(src), str(dst))
            copied += 1
    print(f"  First variant: created with {copied} modules from base genome")


def _validate_dependencies() -> list[str]:
    """Check required dependencies are installed."""
    issues = []
    # Python version
    if sys.version_info < (3, 10):
        issues.append(f"Python 3.10+ required, got {sys.version}")
    # FastAPI
    try:
        import fastapi
    except ImportError:
        issues.append("fastapi not installed (pip install fastapi)")
    # uvicorn
    try:
        import uvicorn
    except ImportError:
        issues.append("uvicorn not installed (pip install uvicorn)")
    # requests (for absorption)
    try:
        import requests
    except ImportError:
        issues.append("requests not installed (pip install requests)")
    # beautifulsoup4 (for absorption)
    try:
        import bs4
    except ImportError:
        issues.append("beautifulsoup4 not installed (pip install beautifulsoup4)")
    return issues


def bootstrap(cli_principal_id: str | None = None) -> dict:
    """Run the full bootstrap process.

    Returns summary dict.
    """
    print("=" * 60)
    print("OpenClaw Anomaly — Bootstrap")
    print("=" * 60)

    # 1. Validate dependencies
    print("\n[1/6] Validating dependencies...")
    issues = _validate_dependencies()
    if issues:
        for issue in issues:
            print(f"  WARNING: {issue}")
    else:
        print("  All dependencies OK")

    # 2. Create directories
    print("\n[2/6] Creating directories...")
    _create_dirs()

    # 3. PRINCIPAL_ID
    print("\n[3/6] Setting up PRINCIPAL_ID...")
    principal_id = _resolve_principal_id(cli_principal_id)
    Config.PRINCIPAL_ID_PATH.write_text(principal_id)
    print(f"  PRINCIPAL_ID: {principal_id[:16]}... (saved to {Config.PRINCIPAL_ID_PATH.name})")

    # 4. INSTALL_ID
    print("\n[4/6] Generating INSTALL_ID...")
    install_id = generate_machine_id()
    Config.INSTALL_ID_PATH.write_text(install_id)
    print(f"  INSTALL_ID: {install_id[:16]}... (machine: {platform.node()})")

    # 5. Seed files
    print("\n[5/6] Creating seed files...")
    created = _create_seed_files()

    # 6. First variant
    print("\n[6/6] Creating first variant...")
    _create_first_variant()

    summary = {
        "principal_id": principal_id[:16] + "...",
        "install_id": install_id[:16] + "...",
        "machine": platform.node(),
        "seed_files_created": created,
        "dependency_issues": issues,
        "base_dir": str(Config.BASE_DIR),
    }

    print("\n" + "=" * 60)
    print("Bootstrap complete!")
    print(f"  Base: {Config.BASE_DIR}")
    print(f"  Principal: {principal_id[:16]}...")
    print(f"  Machine: {platform.node()} ({install_id[:16]}...)")
    if issues:
        print(f"  Warnings: {len(issues)}")
    print("=" * 60)

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenClaw Anomaly Bootstrap")
    parser.add_argument("--principal-id", type=str, default=None, help="PRINCIPAL_ID to use")
    args = parser.parse_args()
    bootstrap(cli_principal_id=args.principal_id)
