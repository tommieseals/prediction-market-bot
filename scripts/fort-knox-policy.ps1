# Fort Knox Backup Policy for Dell (Windows)
# Compresses backups older than 7 days and sends to Mac Pro
# Run daily via Task Scheduler

$BackupDir = "C:\Users\User\clawd\backups"
$FortKnox = "administrator@100.86.80.74"
$FortKnoxPath = "~/fort-knox/dell-backups"
$LogFile = "C:\Users\User\clawd\logs\fort-knox.log"
$DaysToKeepLocal = 7
$DaysToKeepRemote = 30

function Log($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $msg"
    Add-Content -Path $LogFile -Value $line
    Write-Host $line
}

# Ensure log directory exists
$logDir = Split-Path $LogFile -Parent
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force }

Log "FORT KNOX POLICY Dell - Starting"

# Ensure Fort Knox directory exists on Mac Pro
ssh $FortKnox "mkdir -p $FortKnoxPath"

# Find files older than 7 days
$cutoffDate = (Get-Date).AddDays(-$DaysToKeepLocal)
$oldFiles = Get-ChildItem -Path $BackupDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt $cutoffDate }

if ($oldFiles) {
    foreach ($file in $oldFiles) {
        $relativePath = $file.FullName.Replace($BackupDir, "").TrimStart("\")
        Log "Processing: $relativePath"
        
        # If not already compressed, compress it
        if ($file.Extension -ne ".gz" -and $file.Extension -ne ".zip") {
            $zipPath = "$($file.FullName).zip"
            Compress-Archive -Path $file.FullName -DestinationPath $zipPath -Force
            Remove-Item $file.FullName -Force
            $file = Get-Item $zipPath
            Log "  Compressed to: $($file.Name)"
        }
        
        # Transfer to Fort Knox
        $destPath = "$FortKnoxPath/$($file.Name)"
        scp $file.FullName "${FortKnox}:$destPath"
        if ($LASTEXITCODE -eq 0) {
            Remove-Item $file.FullName -Force
            Log "  Transferred to Fort Knox and removed local copy"
        } else {
            Log "  Transfer failed, keeping local copy"
        }
    }
} else {
    Log "No files older than $DaysToKeepLocal days found"
}

# Clean up old files on Fort Knox
Log "Phase 2: Cleaning Fort Knox old files"
ssh $FortKnox "find $FortKnoxPath -type f -mtime +$DaysToKeepRemote -delete -print 2>/dev/null"

Log "FORT KNOX POLICY Dell - Complete"
