# Improvements Implemented (Plan Execution)
Date: 2026-04-04
Status: Implemented (scripts + audits; no service restarts)

## 1) Doc Drift Control
- Added **generate_infra_snapshot.ps1** to create a living “source-of-truth” snapshot.
- Snapshot notes Mac Pro IP mismatch for verification.

## 2) Service Health Proofing
- Added **infra_health_check.ps1** to probe critical services and log status codes.

## 3) Task Scheduler Audit
- Added **task_audit.ps1** to verify critical scheduled tasks and last results.

## 4) Security Baseline Enforcement
- Added **security_perm_audit.ps1** to detect broad write ACLs on Clawdbot state.

## Logs
All scripts log to: `C:\Users\USER\clawd\logs\`

## Next Steps (optional)
- Schedule these scripts via Task Scheduler (if approved)
- Verify Mac Pro IP and update docs
- Add JSON payload validation for /health endpoints
