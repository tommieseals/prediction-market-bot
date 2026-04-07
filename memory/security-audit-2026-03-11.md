# Security Audit Report
**Generated:** 2026-03-11 09:02:27
**Security Score:** -105/100 (Grade: F - Critical)

## Firewall Status

| Node | Firewall | Stealth | Status |
|------|----------|---------|--------|
| Dell | âŒ OFF | âŒ OFF | VULNERABLE |
| Mac-Mini | âŒ OFF | âŒ OFF | VULNERABLE |
| Mac-Pro | âŒ OFF | âŒ OFF | VULNERABLE |
## Exposed Ports

| Node | Port | Risk | Process |
|------|------|------|---------|
| Mac-Mini | 22 | HIGH | Unknown |
| Mac-Mini | 3000 | MEDIUM | Unknown |
| Mac-Mini | 5900 | HIGH | Unknown |
| Mac-Mini | 6379 | MEDIUM | Unknown |
| Mac-Mini | 8080 | MEDIUM | Unknown |
| Dell | 22 | HIGH | sshd |
| Dell | 3389 | HIGH | svchost |
| Dell | 5900 | HIGH | tvnserver |
| Dell | 11434 | MEDIUM | ollama |
## Secrets Detected

| File | Type |
|------|------|
| scripts\bot-watchdog.sh | Telegram Bot Token |
| scripts\captcha_solver.py | API Key |
| scripts\captcha_solver_v2.py | API Key |
| scripts\captcha_solver_v3.py | API Key |
| scripts\clean_secrets.py | Telegram Bot Token |
| scripts\dashboard-integrity.py | Telegram Bot Token |
| scripts\load-api-keys.ps1 | API Key |
| scripts\mac-pro-phase-a-foundation.sh | Password |
| scripts\monitor-bottom-bitch-bot.sh | Telegram Bot Token |
| scripts\proactive-monitor.sh | Telegram Bot Token |
| scripts\service-auto-healer.ps1 | Telegram Bot Token |
| scripts\taskbot-tunnel.ps1 | Telegram Bot Token |
| scripts\test-security-alert.sh | API Key |
| scripts\test_2captcha_demo.py | API Key |
| scripts\test_2captcha_direct.py | API Key |
| scripts\test_2captcha_old.py | API Key |
| scripts\test_challenge.py | API Key |
| scripts\test_regex.py | API Key |
| memory\2026-01-29.md | Telegram Bot Token |
| memory\2026-02-08.md | Telegram Bot Token |
| memory\2026-02-09-n8n-login.md | Password |
| memory\2026-03-01.md | API Key |
| memory\2026-03-02-big-four-audit.md | API Key |
| memory\CRITICAL-GROUP-CHAT-ATTENTION.md | Telegram Bot Token |
| configs\FULL_CODE_SETUP.md | API Key |
## Recommendations
- [Dell] Enable Private firewall profile
- [Dell] Enable Public firewall profile
- [Mac-Mini] Enable firewall: sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
- [Mac-Mini] Enable stealth mode: sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on
- [Mac-Pro] Enable firewall: sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
- [Mac-Pro] Enable stealth mode: sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on
- [Mac-Mini] Review exposed ports: 22, 3000, 5900, 6379, 8080
- [Dell] Review exposed ports: 22, 3389, 5900, 11434
- Review and rotate secrets in: scripts\bot-watchdog.sh, scripts\captcha_solver.py, scripts\captcha_solver_v2.py, scripts\captcha_solver_v3.py, scripts\clean_secrets.py, scripts\dashboard-integrity.py, scripts\load-api-keys.ps1, scripts\mac-pro-phase-a-foundation.sh, scripts\monitor-bottom-bitch-bot.sh, scripts\proactive-monitor.sh, scripts\service-auto-healer.ps1, scripts\taskbot-tunnel.ps1, scripts\test-security-alert.sh, scripts\test_2captcha_demo.py, scripts\test_2captcha_direct.py, scripts\test_2captcha_old.py, scripts\test_challenge.py, scripts\test_regex.py, memory\2026-01-29.md, memory\2026-02-08.md, memory\2026-02-09-n8n-login.md, memory\2026-03-01.md, memory\2026-03-02-big-four-audit.md, memory\CRITICAL-GROUP-CHAT-ATTENTION.md, configs\FULL_CODE_SETUP.md

---
*Automated security audit by security-audit.ps1*
