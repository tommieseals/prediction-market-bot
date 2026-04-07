#!/usr/bin/env python3
"""Run whale simulation and send Telegram alert on signal"""
import os
import sys
import json
import requests
from mirofish_client import MiroFishClient

TELEGRAM_BOT_TOKEN = "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU"
TELEGRAM_CHAT_ID = "939543801"  # Rusty's ID

def send_telegram(message):
    """Send alert to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, data=data, timeout=10)
        return resp.ok
    except Exception:
        return False

def main():
    client = MiroFishClient()
    sim_id = 'sim_f4b9b8bae234'
    
    print("Starting simulation...")
    
    # Start the simulation
    try:
        client.start_simulation(sim_id)
        print("Simulation started!")
    except Exception as e:
        print(f"Start error (may already be running): {e}")
    
    # Wait for completion
    import time
    for i in range(60):  # Up to 5 minutes
        time.sleep(5)
        status = client.get_simulation(sim_id)
        data = status.get('data', {})
        sim_status = data.get('status', 'unknown')
        rounds = data.get('current_round', 0)
        print(f"  Round {rounds}... ({sim_status})")
        
        if sim_status == 'completed':
            print("Simulation complete!")
            break
        if sim_status == 'error':
            print(f"Error: {data.get('error')}")
            return
    
    # Generate report
    print("Generating report...")
    try:
        report = client.generate_report(sim_id)
        report_id = report.get('id') or report.get('data', {}).get('report_id')
        print(f"Report: {report_id}")
    except Exception as e:
        print(f"Report error: {e}")
        report_id = None
    
    # Build alert message
    alert = """
<b>WHALE HUNTER SIGNAL</b>

<b>Whale:</b> beachboy4 (#1, $808K PnL)
<b>Market:</b> Raptors vs Nuggets
<b>Position:</b> YES @ $0.30 (103K shares)

<b>Simulation:</b> {sim_id}
<b>Report:</b> {report_id}
<b>Status:</b> Complete

MiroFish swarm analyzed the whale trade.
Check mirofish-hub for full report.
""".format(sim_id=sim_id, report_id=report_id or "pending")
    
    print("\nSending Telegram alert...")
    if send_telegram(alert):
        print("Alert sent!")
    else:
        print("Alert failed")

if __name__ == "__main__":
    main()
