#!/usr/bin/env python3
"""Test fast scan with full error output"""
import sys
import traceback

print("=" * 60)
print("TEST FAST SCAN")
print("=" * 60)

try:
    from whale_hunter_connector import cmd_scan_fast
    from mirofish_client import MiroFishClient
    
    print("\nRunning fast scan...")
    result = cmd_scan_fast(top_n=10)
    print(f"\nResult: {result}")
    
except Exception as e:
    print(f"\n!!! EXCEPTION: {type(e).__name__}: {e}")
    traceback.print_exc()
    
print("\n" + "=" * 60)
print("DONE")
