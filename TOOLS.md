# TOOLS.md

Full content moved to docs-archive/TOOLS.md to reduce context size.
Use `/memory search <topic>` to find relevant info from Mem0.

---

## PowerShell from the exec tool — use `-File`, not `-Command`

**Problem:** The exec tool's shell layer strips or mis-expands `$` tokens before PowerShell sees them. Any inline `-Command "..."` that references `$env:`, `$_`, `$matches`, `$var`, or pipes through `ForEach-Object { $_.Foo }` will silently have the `$` chewed up, leaving you with invalid PS syntax like `Where-Object { _.Foo }` and empty results.

**Workaround:** Write the PS code to a file first, then invoke with `-File`. `cmd.exe` does not touch `$` inside a file.

### Pattern

```powershell
# 1. Write the script (via the write-file tool, not inline)
# Location convention: scripts/_tmp/ under the workspace
New-Item -Type Directory -Force C:\Users\User\clawd\scripts\_tmp | Out-Null

# 2. Example script body (saved as scripts\_tmp\probe.ps1)
$log = "$env:USERPROFILE\.clawdbot\logs\clawdbot.log"
Get-Content $log -Tail 50 | Where-Object { $_ -match 'error' } | ForEach-Object {
    if ($_ -match '"date":"([^"]+)"') { $matches[1] }
}

# 3. Run it
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\User\clawd\scripts\_tmp\probe.ps1
```

### When to prefer `-File`

Always reach for `-File` when your PowerShell needs:
- `$env:` variables
- `$_` in pipelines (`Where-Object`, `ForEach-Object`, `Select-Object -Property @{...}`)
- `$matches` from `-match` regex
- Named variables in scripts (`$var = ...`)
- Here-strings with `@"..."@`
- `ConvertFrom-Json` piping into filters
- Anything with quoted strings that contain `$`

Inline `-Command` is acceptable ONLY for trivial one-liners with no `$` at all, e.g.:
```
powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"
```

### Cleanup

Delete scripts under `_tmp/` once you're done reading their output. The `_tmp/` dir is git-ignored.

### Debugging the stripping itself

If you need to verify whether `$` is getting through, write this exact script and run it:

```powershell
# C:\Users\User\clawd\scripts\_tmp\dollar_test.ps1
"PID=$PID"
"USER=$env:USERNAME"
$x = 42; "x=$x"
@(1,2,3) | ForEach-Object { "item=$_" }
```

If the output shows blanks or `item=`, the script file itself is being mangled. If the output is correct, the stripping only affects inline `-Command` — which means `-File` fully avoids the problem.
