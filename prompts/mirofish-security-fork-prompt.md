# Claude Code Prompt: MiroFish AI Security Fork

## MISSION
Fork and secure the MiroFish AI platform (github.com/666ghj/MiroFish) for self-hosted deployment. This is a SECURITY-CRITICAL task requiring exhaustive code review. The platform is Chinese-backed (Shanda Group) - assume hostile until proven safe.

---

## PHASE 1: RECONNAISSANCE & PLANNING

### 1.1 Clone and Map the Codebase
```bash
git clone https://github.com/666ghj/MiroFish.git mirofish-secure
cd mirofish-secure
```

Create a complete map of:
- All Python files and their purposes
- All JavaScript/frontend files
- All configuration files
- All dependency files (requirements.txt, package.json, etc.)
- Any binary files (HIGHLY SUSPICIOUS - flag immediately)
- Any obfuscated or minified code that shouldn't be

### 1.2 Dependency Audit
For EVERY dependency in requirements.txt and package.json:
- Verify it's a legitimate, well-known package
- Check for typosquatting (e.g., `reqeusts` instead of `requests`)
- Check package ownership and download counts on PyPI/npm
- Flag any dependencies with:
  - Low download counts (<10,000)
  - Recent ownership transfers
  - Suspicious names
  - Chinese-only documentation (not inherently bad, but note it)

### 1.3 Network Behavior Analysis
Search the ENTIRE codebase for:
- All URLs, IPs, domains (grep for http://, https://, any IP patterns)
- All outbound network calls (requests, urllib, fetch, axios, etc.)
- Websocket connections
- Any DNS lookups
- Any code that could phone home or exfiltrate data

**Document every single external endpoint the code contacts.**

---

## PHASE 2: LINE-BY-LINE SECURITY AUDIT

### 2.1 Known Vulnerabilities to Patch

We've already identified these - FIX THEM:

| Issue | Location | Fix |
|-------|----------|-----|
| Error traceback exposed | API error handlers | Remove `traceback.format_exc()` from client responses |
| No authentication | All API endpoints | Implement proper auth (JWT or session-based) |
| Hardcoded SECRET_KEY | Flask config | Generate cryptographically secure key, load from env |
| Wide-open CORS | Flask CORS config | Restrict to specific origins |
| Debug mode default True | Flask config | Default to False, only enable via env var |
| File upload no validation | Upload handlers | Validate file content, not just extension |
| No rate limiting | All endpoints | Implement rate limiting |
| Predictable resource IDs | Database models | Use UUIDs instead of sequential IDs |

### 2.2 Backdoor Detection Checklist

Search for and flag ANY of the following patterns:

**Code Execution:**
- `eval()`, `exec()`, `compile()`
- `subprocess` with user input
- `os.system()`, `os.popen()`
- `__import__()` with dynamic strings
- `pickle.loads()` on untrusted data
- Any deserialization of external data

**Data Exfiltration:**
- Hardcoded external URLs (especially non-HTTPS)
- Base64 encoded strings (decode and inspect each one)
- Any data being sent externally that shouldn't be
- Clipboard access
- File system scanning beyond project scope

**Obfuscation Red Flags:**
- Hex-encoded strings
- Character code manipulation (chr(), ord() chains)
- String reversal or XOR patterns
- Comments in Chinese that don't match code behavior
- Dead code that still gets loaded
- Import statements that don't match actual usage

**Timing-Based Attacks:**
- `time.sleep()` in unusual places
- Scheduled tasks that aren't documented
- Any code that activates after a certain date/time

**Environment Snooping:**
- Reading env vars beyond what's needed
- Accessing system information (hostname, username, etc.)
- Network interface enumeration
- Process listing

### 2.3 File-by-File Audit

Go through EVERY file and document:
1. What it does (one sentence)
2. Any security concerns found
3. Any suspicious patterns
4. Recommended changes

Output this as a security audit report.

---

## PHASE 3: IMPLEMENTATION

### 3.1 Create Secure Fork Structure
```
mirofish-secure/
├── .env.example          # Template with required env vars
├── .env                   # GITIGNORED - actual secrets
├── docker-compose.yml     # Self-contained deployment
├── SECURITY_AUDIT.md      # Your findings
├── CHANGES.md             # All modifications made
└── src/                   # Modified source code
```

### 3.2 Implement Security Patches

For each vulnerability:
1. Create a fix
2. Document the original code
3. Document your fix
4. Explain why it's secure now

### 3.3 Remove or Sandbox Suspicious Code

If you find code you can't verify is safe:
- DO NOT just delete it (might break functionality)
- Sandbox it with logging
- Document what it does
- Flag for human review

### 3.4 Add Security Hardening

Implement:
- [ ] Proper authentication system
- [ ] Role-based access control
- [ ] Input validation on ALL endpoints
- [ ] Output encoding
- [ ] Security headers (CSP, HSTS, X-Frame-Options, etc.)
- [ ] Audit logging (who did what, when)
- [ ] Rate limiting per user/IP
- [ ] Request size limits
- [ ] Secure session management

---

## PHASE 4: VERIFICATION (SECOND PASS)

### 4.1 Re-Audit All Changes
Go through every modification you made and verify:
- It actually fixes the issue
- It doesn't introduce new vulnerabilities
- It doesn't break functionality

### 4.2 Dependency Lock
- Pin ALL dependencies to exact versions
- Generate lock files (pip freeze, package-lock.json)
- Document why each dependency is needed

### 4.3 Test for Regressions
- Core functionality still works
- No new security warnings
- No unexpected network traffic

### 4.4 Final Report

Create `SECURITY_AUDIT.md` with:
1. Executive summary
2. All vulnerabilities found (original code)
3. All suspicious code found (even if benign)
4. All changes made
5. Remaining concerns or unknowns
6. Deployment recommendations

---

## OUTPUT REQUIREMENTS

When complete, provide:

1. **SECURITY_AUDIT.md** - Complete findings
2. **CHANGES.md** - Every modification documented
3. **Patched codebase** - Ready for self-hosted deployment
4. **Deployment guide** - How to run it securely
5. **Confidence assessment** - Your honest assessment of remaining risk

---

## CONSTRAINTS

- Take your time. Thoroughness over speed.
- When in doubt, flag it for human review rather than assuming it's safe.
- Do NOT execute any code from this repo during audit (static analysis only)
- Document EVERYTHING - your reasoning matters as much as your fixes
- If you find something truly malicious, STOP and report immediately

---

## START

Begin with Phase 1. Create your plan, then execute methodically. This is a pharaoh-level job - build it to last.
