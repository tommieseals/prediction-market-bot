# Telegram Transcript Forwarder
# Monitors Clawdbot session and forwards voice transcripts to Telegram

param(
    [string]$LogPath = "C:\Users\USER\.clawdbot\logs\clawdbot.log",
    [string]$BotToken = "7897105421:AAGq-5f3m-H_so4XUUa4X0EiVvsacspYRQA",
    [string]$ChatId = "939543801",  # @Dlowbands
    [int]$PollIntervalSeconds = 5
)

$LastPosition = 0
$TranscriptBuffer = @()

# Telegram API helper
function Send-TelegramMessage {
    param([string]$Message)
    
    $Uri = "https://api.telegram.org/bot$BotToken/sendMessage"
    $Body = @{
        chat_id = $ChatId
        text = $Message
        parse_mode = "Markdown"
    } | ConvertTo-Json
    
    try {
        Invoke-RestMethod -Uri $Uri -Method Post -Body $Body -ContentType "application/json" | Out-Null
        Write-Host "✅ Sent to Telegram: $($Message.Substring(0, [Math]::Min(50, $Message.Length)))..."
    } catch {
        Write-Host "❌ Failed to send: $_"
    }
}

# Extract transcript from log line
function Parse-Transcript {
    param([string]$Line)
    
    # Look for "transcribe and respond to" pattern
    if ($Line -match "transcribe and respond to '([^']+)'") {
        return @{
            Type = "User"
            Text = $Matches[1]
            Timestamp = Get-Date -Format "HH:mm:ss"
        }
    }
    
    # Look for assistant responses (simplified)
    if ($Line -match "\[assistant\]" -or $Line -match "💰") {
        # Extract meaningful response content
        if ($Line -match "text: (.+)$") {
            return @{
                Type = "Assistant"
                Text = $Matches[1]
                Timestamp = Get-Date -Format "HH:mm:ss"
            }
        }
    }
    
    return $null
}

Write-Host "🎤 Telegram Transcript Forwarder Started"
Write-Host "📝 Monitoring: $LogPath"
Write-Host "📱 Forwarding to: @Dlowbands ($ChatId)"
Write-Host "⏱️  Poll interval: ${PollIntervalSeconds}s"
Write-Host ""

# Main monitoring loop
while ($true) {
    try {
        if (Test-Path $LogPath) {
            $Content = Get-Content $LogPath -Tail 100
            
            foreach ($Line in $Content) {
                $Transcript = Parse-Transcript -Line $Line
                
                if ($Transcript) {
                    # Add to buffer
                    $TranscriptBuffer += $Transcript
                    
                    # If we have a complete exchange (User + Assistant), send it
                    if ($TranscriptBuffer.Count -ge 2 -and 
                        $TranscriptBuffer[-2].Type -eq "User" -and 
                        $TranscriptBuffer[-1].Type -eq "Assistant") {
                        
                        $User = $TranscriptBuffer[-2]
                        $Assistant = $TranscriptBuffer[-1]
                        
                        $Message = @"
🎤 *Voice Transcript* - $($User.Timestamp)

👤 User: $($User.Text)

💰 Bottom Bitch: $($Assistant.Text)

---
"@
                        
                        Send-TelegramMessage -Message $Message
                        
                        # Clear buffer
                        $TranscriptBuffer = @()
                    }
                }
            }
        }
    } catch {
        Write-Host "⚠️  Error: $_"
    }
    
    Start-Sleep -Seconds $PollIntervalSeconds
}
