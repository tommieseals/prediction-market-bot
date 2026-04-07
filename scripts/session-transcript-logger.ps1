# Session Transcript Logger - Simple Version
# Logs voice transcripts to file and forwards to Telegram

param(
    [string]$BotToken = "7897105421:AAGq-5f3m-H_so4XUUa4X0EiVvsacspYRQA",
    [string]$ChatId = "939543801",  # @Dlowbands
    [string]$TranscriptFile = "C:\Users\USER\clawd\memory\voice-transcripts-$(Get-Date -Format 'yyyy-MM-dd').md"
)

# Helper function to send to Telegram
function Send-Transcript {
    param(
        [string]$UserText,
        [string]$AssistantText
    )
    
    $Timestamp = Get-Date -Format "HH:mm:ss"
    
    # Format message
    $Message = @"
🎤 *Voice Chat* - $Timestamp

👤 *User:*
$UserText

💰 *Assistant:*
$AssistantText

━━━━━━━━━━━━━━━
"@
    
    # Send to Telegram
    $Uri = "https://api.telegram.org/bot$BotToken/sendMessage"
    $Body = @{
        chat_id = $ChatId
        text = $Message
        parse_mode = "Markdown"
    } | ConvertTo-Json -Compress
    
    try {
        Invoke-RestMethod -Uri $Uri -Method Post -Body $Body -ContentType "application/json" -ErrorAction Stop | Out-Null
        Write-Host "✅ Forwarded to Telegram"
        
        # Also save to file
        $FileEntry = @"

## $Timestamp

**User:** $UserText

**Assistant:** $AssistantText

---

"@
        Add-Content -Path $TranscriptFile -Value $FileEntry
        Write-Host "📝 Saved to $TranscriptFile"
        
    } catch {
        Write-Host "❌ Failed: $_"
    }
}

# Make function available globally
Export-ModuleMember -Function Send-Transcript

Write-Host "✅ Transcript logger loaded"
Write-Host "📱 Forwarding to: @Dlowbands"
Write-Host ""
Write-Host "Usage: Send-Transcript -UserText 'user said' -AssistantText 'I replied'"
