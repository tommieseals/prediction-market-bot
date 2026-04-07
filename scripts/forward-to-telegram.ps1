# Quick Telegram Forwarder
# Usage: .\forward-to-telegram.ps1 "Your message here"

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Message,
    
    [string]$ChatId = "939543801",  # @Dlowbands
    [string]$BotToken = "7897105421:AAGq-5f3m-H_so4XUUa4X0EiVvsacspYRQA"
)

$Uri = "https://api.telegram.org/bot$BotToken/sendMessage"

$Body = @{
    chat_id = $ChatId
    text = $Message
    parse_mode = "Markdown"
} | ConvertTo-Json -Compress

try {
    $Response = Invoke-RestMethod -Uri $Uri -Method Post -Body $Body -ContentType "application/json"
    Write-Host "✅ Sent to Telegram successfully!" -ForegroundColor Green
    Write-Host "Message ID: $($Response.result.message_id)"
} catch {
    Write-Host "❌ Failed to send: $_" -ForegroundColor Red
}
