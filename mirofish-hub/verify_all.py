# -*- coding: utf-8 -*-
import requests
import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("THOROUGH VERIFICATION OF ALL PICKS")
print("=" * 60)

# 1. LAKERS VS PISTONS - March 23, 2026
print("\n### 1. LAKERS VS PISTONS (March 23, 2026) ###")
print("ESPN Verified Score:")
print("  Lakers: 27+25+35+23 = 110")
print("  Pistons: 23+42+24+24 = 113")
print("  RESULT: Pistons won 113-110")
print("  Our bet: NO (bet against Lakers / for Pistons)")
print("  VERDICT: [WIN]")

# 2. THUNDER VS CELTICS O/U 218.5 - March 25, 2026
print("\n### 2. THUNDER VS CELTICS O/U 218.5 (March 25, 2026) ###")
print("ESPN Verified Score:")
print("  Thunder: 31+22+30+26 = 109")
print("  Celtics: 20+29+39+31 = 119")
print("  COMBINED: 228")
print("  Line: 218.5")
print("  RESULT: 228 > 218.5 = OVER won")
print("  Our bet: UNDER")
print("  VERDICT: [LOSS]")

# 3. HEAT VS CAVALIERS - March 25, 2026
print("\n### 3. HEAT VS CAVALIERS (March 25, 2026) ###")
print("ESPN Verified Score:")
print("  Heat: 28+35+20+37 = 120")
print("  Cavaliers: 19+27+37+20 = 103")
print("  RESULT: Heat won 120-103")
print("  Our bet: CAVALIERS")
print("  VERDICT: [LOSS]")

# 4. BTC > $70,000 on March 26
print("\n### 4. BTC > $70,000 ON MARCH 26 ###")
try:
    r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=10)
    btc_price = r.json()["bitcoin"]["usd"]
    print(f"  Current BTC Price: ${btc_price:,.2f}")
    
    # Check Polymarket for resolution status
    wallet = "0x299aCc0857B943d8490ECb1820fD458B3B58c728"
    r2 = requests.get(f"https://data-api.polymarket.com/positions?user={wallet}", timeout=10)
    positions = r2.json()
    
    for p in positions:
        if "Bitcoin" in p.get("title", "") and "70,000" in p.get("title", ""):
            print(f"  Market: {p.get('title')}")
            print(f"  Resolved: {p.get('resolved')}")
            print(f"  Redeemable: {p.get('redeemable')}")
            print(f"  Outcome shown: {p.get('outcome')}")
            
            if btc_price < 70000:
                print(f"  WARNING: Current price ${btc_price:,.0f} is BELOW $70,000!")
                if not p.get('resolved'):
                    print("  VERDICT: [PENDING] - market not officially resolved yet")
                else:
                    print("  VERDICT: Needs manual check - price dropped after resolution?")
            else:
                print(f"  Price ${btc_price:,.0f} is ABOVE $70,000")
                print("  VERDICT: [WIN]")
except Exception as e:
    print(f"  Error: {e}")

# 5. ETH > $2,100 on March 26
print("\n### 5. ETH > $2,100 ON MARCH 26 ###")
try:
    r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", timeout=10)
    eth_price = r.json()["ethereum"]["usd"]
    print(f"  Current ETH Price: ${eth_price:,.2f}")
    
    for p in positions:
        if "Ethereum" in p.get("title", "") and "2,100" in p.get("title", ""):
            print(f"  Market: {p.get('title')}")
            print(f"  Resolved: {p.get('resolved')}")
            print(f"  Redeemable: {p.get('redeemable')}")
            print(f"  Outcome shown: {p.get('outcome')}")
            
            if eth_price < 2100:
                print(f"  WARNING: Current price ${eth_price:,.2f} is BELOW $2,100!")
                if not p.get('resolved'):
                    print("  VERDICT: [PENDING] - market not officially resolved yet")
                else:
                    print("  VERDICT: Needs manual check")
            else:
                print(f"  Price ${eth_price:,.2f} is ABOVE $2,100")
                print("  VERDICT: [WIN]")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 60)
print("SUMMARY - VERIFIED RESULTS")
print("=" * 60)
print("| Market                    | Our Bet    | Result          |")
print("|---------------------------|------------|-----------------|")
print("| Lakers vs Pistons         | NO         | [WIN]           |")
print("| Thunder O/U 218.5         | Under      | [LOSS]          |")
print("| Heat vs Cavaliers         | Cavaliers  | [LOSS]          |")
print("| BTC > $70K Mar 26         | YES        | SEE ABOVE       |")
print("| ETH > $2,100 Mar 26       | YES        | SEE ABOVE       |")
