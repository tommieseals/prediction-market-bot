"""OpenClaw Anomaly — Capability Matrix & Approval Ladder.

Every action in the system has a permission level. FROZEN state
short-circuits all non-read actions at the top of check_permission().
"""
from __future__ import annotations

from enum import Enum


class PermissionLevel(Enum):
    READ = "read"
    WRITE_LOCAL = "write_local"
    PROPOSE = "propose"
    AUTO_APPLY = "auto_apply"
    APPROVAL_REQUIRED = "approval_required"
    PRINCIPAL_ONLY = "principal_only"
    FORBIDDEN = "forbidden"


R = PermissionLevel.READ
WL = PermissionLevel.WRITE_LOCAL
P = PermissionLevel.PROPOSE
AA = PermissionLevel.AUTO_APPLY
AR = PermissionLevel.APPROVAL_REQUIRED
PO = PermissionLevel.PRINCIPAL_ONLY
F = PermissionLevel.FORBIDDEN

CAPABILITY_MATRIX: dict[str, PermissionLevel] = {
    # -- READ (freely) --------------------------------------------------------
    "read_genome": R,
    "read_fitness_db": R,
    "read_correction_log": R,
    "read_trader_memory": R,
    "read_project_status": R,
    "read_external_urls": R,
    "read_worker_registry": R,
    "read_active_mission": R,
    "read_matrix_inventory": R,
    "read_keys_ledger": R,

    # -- WRITE_LOCAL (openclaw/ files) ----------------------------------------
    "write_fitness_db": WL,
    "write_correction_log": WL,
    "write_trader_memory": WL,
    "write_last_session": WL,
    "write_audit_log": WL,
    "write_memory_core": WL,
    "write_worker_registry": WL,
    "write_active_mission": WL,
    "write_incidents": WL,

    # -- PROPOSE (logged, not applied until judged) ---------------------------
    "propose_genome_mutation": P,
    "propose_variant_promotion": P,
    "propose_project_action": P,
    "propose_infra_change": P,
    "propose_absorption_merge": P,

    # -- AUTO_APPLY (low risk) ------------------------------------------------
    "run_health_check": AA,
    "run_fitness_logging": AA,
    "run_shadow_replay": AA,
    "run_absorption_scan": AA,
    "run_memory_tier_management": AA,
    "send_telegram_status": AA,
    "generate_update_doc": AA,
    "apply_project_change": AA,  # only when adapter conditions met
    "run_remote_tests": AA,
    "run_remote_rollback": AA,

    # Agent recruitment (Smith Level 2)
    "spawn_local_worker": AA,
    "spawn_remote_monitor": AA,
    "spawn_remote_worker": AA,
    "recall_worker": AA,
    "resume_mission": AA,

    # -- APPROVAL_REQUIRED (Telegram approval) --------------------------------
    "activate_variant": AR,
    "run_meta_cycle": AR,
    "apply_infra_change": AR,
    "apply_website_change": AR,
    "send_email": AR,
    "execute_financial_action": AR,
    "archive_variant": AR,
    "spawn_persistent_monitor": AR,
    "apply_remote_change": AR,
    "read_project_secret": AR,

    # -- PRINCIPAL_ONLY (only PRINCIPAL_ID can execute) -----------------------
    "unfreeze": PO,

    # -- FORBIDDEN (hard-blocked, no path) ------------------------------------
    "install_oge_on_other_bot": F,
    "clone_jarvis_identity": F,
    "rewrite_other_bot_identity": F,
    "create_sovereign_agent": F,
    "mutate_other_agent_genome": F,
    "transfer_ownership": F,
    "create_new_principal": F,
    "spawn_independent_agent": F,
    "change_principal": F,
    "fork_independent": F,
}


def check_permission(
    action: str,
    context: dict | None = None,
    agent_state: str | None = None,
    principal_id: str | None = None,
) -> tuple[bool, str]:
    """Check capability matrix for a given action.

    Args:
        action: The action name to check.
        context: Optional context dict (user_id, amount, etc.).
        agent_state: Current agent state (for FROZEN enforcement).
        principal_id: The verified PRINCIPAL_ID (for PRINCIPAL_ONLY).

    Returns:
        (allowed, reason) tuple.
    """
    context = context or {}

    # FROZEN short-circuit -- MUST be first check
    if agent_state == "frozen":
        if action.startswith("read_") or action == "unfreeze":
            pass  # reads + unfreeze allowed in frozen state
        else:
            return False, "FROZEN: all non-read actions blocked. Use /unfreeze."

    level = CAPABILITY_MATRIX.get(action)
    if level is None:
        return False, f"Unknown action: {action}"

    if level == PermissionLevel.FORBIDDEN:
        return False, f"FORBIDDEN: {action} is permanently blocked."

    if level == PermissionLevel.PRINCIPAL_ONLY:
        if context.get("user_id") == principal_id and principal_id is not None:
            return True, "Principal authorized."
        return False, f"PRINCIPAL_ONLY: {action} requires principal authorization."

    if level == PermissionLevel.APPROVAL_REQUIRED:
        if context.get("approved"):
            return True, "Approved."
        return False, f"APPROVAL_REQUIRED: {action} needs Telegram approval first."

    if level in (
        PermissionLevel.READ,
        PermissionLevel.WRITE_LOCAL,
        PermissionLevel.PROPOSE,
        PermissionLevel.AUTO_APPLY,
    ):
        return True, f"Allowed at level {level.value}."

    return False, f"Unhandled permission level: {level.value}"
