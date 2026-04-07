# -*- coding: utf-8 -*-
"""Fix security issues - replace hardcoded keys with env vars"""
import os
import re

files_to_fix = [
    'approve_all.py', 'check_balance.py', 'check_liquidity.py',
    'deposit_and_trade.py', 'find_proxy.py', 'fix_allowance.py',
    'fix_allowance2.py', 'fix_balance.py', 'place_bets.py',
    'place_crypto_bets.py', 'place_hawks_bet.py', 'polymarket_trader.py',
    'quick_balance.py', 'redeem_position.py', 'set_allowance.py',
    'show_portfolio.py', 'swap_1inch.py', 'swap_final.py',
    'swap_paraswap.py', 'swap_usdc.py', 'test_trade.py', 'trade_final.py'
]

# Pattern to find hardcoded private keys
key_pattern = re.compile(r'(PRIVATE_KEY|private_key)\s*=\s*["\']([a-fA-F0-9]{64})["\']')

fixed_count = 0
for filename in files_to_fix:
    if not os.path.exists(filename):
        continue
    
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Check if already using os.getenv
    if 'os.getenv' in content and 'POLY_PRIVATE_KEY' in content:
        print(f'[SKIP] {filename} - already using env vars')
        continue
    
    # Find and replace hardcoded keys
    matches = key_pattern.findall(content)
    if matches:
        # Add import if needed
        if 'import os' not in content:
            content = 'import os\n' + content
        
        # Replace hardcoded key with env var
        new_content = key_pattern.sub(
            r'\1 = os.getenv("POLY_PRIVATE_KEY", "")', 
            content
        )
        
        if new_content != content:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f'[FIXED] {filename} - replaced {len(matches)} hardcoded key(s)')
            fixed_count += 1
        else:
            print(f'[SKIP] {filename} - no changes needed')
    else:
        print(f'[SKIP] {filename} - no hardcoded keys found')

print(f'\nFixed {fixed_count} files')
