# send_transcript.ps1
# Send conversation transcript to Rusty via Telegram
# Usage: .\send_transcript.ps1 "User input" "Bot response"

param(
    [string]$UserInput,
    [string]$BotResponse
)

$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$Transcript = @"
📝 **VOICE TRANSCRIPT**
⏰ $Timestamp

👤 **User:**
$UserInput

💰 **Bottom Bitch:**
$BotResponse

---
"@

# Send via Clawdbot message tool (using Python wrapper)
$TempFile = New-TemporaryFile
$Transcript | Out-File -FilePath $TempFile.FullName -Encoding UTF8

# Call Python script that uses Clawdbot API
python C:\Users\USER\clawd\send_via_clawdbot.py --file $TempFile.FullName

Remove-Item $TempFile.FullName
