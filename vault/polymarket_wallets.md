# POLYMARKET WALLETS - VAULT
**Created:** 2026-03-21
**Status:** ACTIVE ✅

## Trading Wallet (Polymarket Bot)
- **Address:** `0x299aCc0857B943d8490ECb1820fD458B3B58c728`
- **Private Key:** `39f1a59fe9c2c006ac51e1edad69be0a0133df21c053e91f34387ba9cc9f30ae`
- **Network:** Polygon
- **USDC Balance:** $77.36 (as of 2026-03-22 00:05)
- **MATIC Balance:** 0.5 (for gas, ~50 trades)
- **Status:** ✅ FULLY OPERATIONAL

## Personal Wallet (Rusty's)
- **Address:** `0xA85b285c265F7748e10DdB30f7643dCA3aa08D4b`
- **Private Key:** `ddacdb3d5c7751e8a974a87c5bc704850f3fcb68b95e8bba29fe85d435709784`
- **Network:** Polygon
- **Note:** Used for bridging/funding

## API Credentials
- Derived from trading wallet private key
- API Key: `3a4ac263-a95a-99b2-7...` (auto-derived)
- No need to store - regenerated each session

## Setup Files
- Trader script: `C:\Users\USER\clawd\mirofish-hub\polymarket_trader.py`
- Config: `C:\Users\USER\clawd\mirofish-hub\.env`
- Balance checker: `C:\Users\USER\clawd\mirofish-hub\check_polygon_balance.py`

## Quick Commands
```bash
# Check balance
python polymarket_trader.py --balance

# Search markets
python polymarket_trader.py --markets "search term"

# Buy shares
python polymarket_trader.py --buy TOKEN_ID PRICE AMOUNT
```

## Transaction History
| Date | Action | Amount | TX |
|------|--------|--------|-----|
| 2026-03-21 | Fund trading wallet | $77.36 USDC | [polygonscan](https://polygonscan.com/tx/e8a83aac23d695b483f41aa68da46aa9d2fcdb58e88e83c0370d89b627d0158e) |
| 2026-03-22 | Add gas | 0.5 MATIC | [polygonscan](https://polygonscan.com/tx/7d81ab6b5715ec8a82325af47582211eb5ecc7eb6b940407ff6723d9ecd2d5fc) |
