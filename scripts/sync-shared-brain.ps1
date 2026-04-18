# Sync local shared-brain to/from Mac Pro (with git)
# Usage: sync-shared-brain.ps1 [push|pull|status]

param(
    [Parameter(Position=0)]
    [ValidateSet("push", "pull", "status")]
    [string]$Action = "pull"
)

$RepoPath = "C:\Users\User\clawd"
$LocalPath = "C:\Users\User\clawd\shared-brain"
$RemoteHost = "administrator@100.86.80.74"
$RemotePath = "~/shared-brain"

function Log($msg) {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg"
}

switch ($Action) {
    "push" {
        Log "Pushing shared-brain changes via git..."
        if (!(Test-Path $LocalPath)) {
            throw "Shared-brain path not found: $LocalPath"
        }
        git -C $RepoPath add -- "shared-brain"
        git -C $RepoPath commit -m "shared-brain sync $(Get-Date -Format 'yyyy-MM-dd HH:mm')" 2>$null | Out-Null
        git -C $RepoPath push origin HEAD
        Log "Done! Shared-brain changes pushed to origin."
    }
    "pull" {
        Log "Pulling latest shared-brain changes via git..."
        git -C $RepoPath pull --ff-only origin HEAD
        Log "Done! Local copy updated."
    }
    "status" {
        Log "Checking shared-brain status..."
        git -C $RepoPath remote -v
        git -C $RepoPath log -3 --format="%h %s (%cr by %an)"
        git -C $RepoPath status --short -- "shared-brain"
    }
}
