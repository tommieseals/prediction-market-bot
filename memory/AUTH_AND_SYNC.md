# AUTH_AND_SYNC.md - Gmail, Indeed, and Shared-Brain State

Last Updated: 2026-04-05 18:40 CT

## Gmail
Last Verified: 2026-04-05
- Status: reauth required on Tom.
- Why: the saved refresh token is revoked or expired.
- Recovery path: `python3 ~/clawd/scripts/gmail-direct-reauth.py` on Tom.
- Source files: `/Users/tommie/clawd/scripts/job-auth-status.py`, `/Users/tommie/clawd/memory/job-monitoring-2026-04-05.log`

## Indeed
Last Verified: 2026-04-05
- Status: signed-in Chrome Default session present on Tom.
- Source files: `/Users/tommie/clawd/scripts/job-auth-status.py`, `/Users/tommie/shared-memory/tom-status.json`

## Shared-Brain Sync
Last Verified: 2026-04-05
- The sync report now distinguishes the clean sync mirror from the dirty local Tom workspace.
- Do not call sync blocked when the mirror is current and only the workspace is dirty.
- Source file: `/Users/tommie/shared-memory/shared-brain-sync-report.json`
