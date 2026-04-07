#!/usr/bin/env python3
"""
Telegram Transcript Forwarder
Automatically forwards conversation transcripts to Rusty's Telegram.

Usage:
    python transcript_forwarder.py --send "User: Hello\\nBB: Hey there"
    python transcript_forwarder.py --file transcript.txt
    python transcript_forwarder.py --monitor (continuous monitoring mode)
"""

import sys
import json
import requests
import time
from datetime import datetime
from pathlib import Path

# Configuration
TELEGRAM_BOT_TOKEN = "7897398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU"  # From TOOLS.md
RUSTY_CHAT_ID = 939543801  # @Dlowbands

GATEWAY_URL = "http://localhost:18789"

def send_telegram_message(text, chat_id=RUSTY_CHAT_ID):
    """
    Send message to Telegram using Clawdbot message tool.
    
    Args:
        text: Message text
        chat_id: Telegram chat ID (default: Rusty)
    
    Returns:
        True if sent successfully
    """
    try:
        # Use Telegram API directly
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print(json.dumps({
                "success": True,
                "sent_to": chat_id,
                "message_length": len(text)
            }))
            return True
        else:
            print(json.dumps({
                "error": f"Send failed: {response.status_code}",
                "details": response.text[:200]
            }))
            return False
            
    except Exception as e:
        print(json.dumps({
            "error": f"Failed to send: {str(e)}"
        }))
        return False

def format_transcript(user_input, bot_response):
    """
    Format conversation transcript for Telegram.
    
    Args:
        user_input: User's message/transcription
        bot_response: Bot's response
    
    Returns:
        Formatted string
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Truncate if too long (Telegram limit: 4096 chars)
    max_len = 3800
    if len(user_input) > 1000:
        user_input = user_input[:1000] + "..."
    if len(bot_response) > 2500:
        bot_response = bot_response[:2500] + "..."
    
    transcript = f"""📝 *VOICE TRANSCRIPT*
⏰ {timestamp}

👤 *User:*
{user_input}

💰 *Bottom Bitch:*
{bot_response}

---"""
    
    return transcript

def send_transcript(user_input, bot_response):
    """
    Send formatted transcript to Telegram.
    
    Args:
        user_input: User's message
        bot_response: Bot's response
    
    Returns:
        True if sent successfully
    """
    transcript = format_transcript(user_input, bot_response)
    return send_telegram_message(transcript)

def monitor_transcripts(interval=300):
    """
    Continuously monitor for new transcripts and forward.
    NOT IMPLEMENTED - requires integration with voice system.
    
    Args:
        interval: Check interval in seconds (default: 5 minutes)
    """
    print(json.dumps({
        "info": "Monitor mode not implemented yet",
        "reason": "Requires integration with voice transcription system",
        "use_instead": "Call send_transcript() after each conversation"
    }))

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: python transcript_forwarder.py --send 'user text' 'bot text'"
        }))
        sys.exit(1)
    
    if sys.argv[1] == "--send":
        if len(sys.argv) < 4:
            print(json.dumps({"error": "Need user and bot text"}))
            sys.exit(1)
        user_input = sys.argv[2]
        bot_response = sys.argv[3]
        send_transcript(user_input, bot_response)
    
    elif sys.argv[1] == "--test":
        # Send test message
        test_msg = f"🔧 *TEST MESSAGE*\n\nTranscript forwarding system is operational.\n\nTimestamp: {datetime.now()}"
        send_telegram_message(test_msg)
    
    elif sys.argv[1] == "--monitor":
        monitor_transcripts()
    
    else:
        print(json.dumps({"error": "Unknown command. Use --send, --test, or --monitor"}))
        sys.exit(1)

if __name__ == "__main__":
    main()
