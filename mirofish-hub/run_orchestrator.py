#!/usr/bin/env python3
"""Run a single orchestrator cycle with whale_hunter"""
import sys
sys.stdout.reconfigure(line_buffering=True)

print("=" * 60, flush=True)
print("ORCHESTRATOR - Running whale_hunter scan", flush=True)
print("=" * 60, flush=True)

from mirofish_client import MiroFishClient
import whale_hunter_connector as whc

print("\n1. Checking MiroFish health...", flush=True)
client = MiroFishClient()
if client.health_check():
    print("   MiroFish: ONLINE", flush=True)
else:
    print("   MiroFish: OFFLINE - aborting", flush=True)
    sys.exit(1)

print("\n2. Running cmd_health...", flush=True)
try:
    whc.cmd_health(client)
except Exception as e:
    print(f"   Health check error: {e}", flush=True)

print("\n3. Running whale scan (top 3)...", flush=True)
print("   This will:", flush=True)
print("   - Score top 50 whales from Polymarket", flush=True)
print("   - Detect new positions from elite traders", flush=True)
print("   - Run MiroFish sims on top 3 positions", flush=True)
print("   - Generate signals if edge >= 8%", flush=True)
print("   - Send Telegram alerts on signals", flush=True)
print("", flush=True)

try:
    result = whc.cmd_scan(client, top_n=3)
    print(f"\nScan complete!", flush=True)
except Exception as e:
    print(f"\nScan error: {e}", flush=True)
    import traceback
    traceback.print_exc()

print("\nOrchestrator cycle done.", flush=True)
