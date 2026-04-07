import sqlite3
from py_clob_client.client import ClobClient
from dotenv import load_dotenv
import os

load_dotenv()

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Get top consensus picks with token IDs
cur.execute('''
SELECT DISTINCT market_title, token_id, side, condition_id
FROM whale_positions 
WHERE market_title LIKE '%Korda%Landaluce%'
   OR market_title LIKE '%Dodig%Kopp%'
   OR market_title LIKE '%Harris%Cecchinato%'
   OR market_title LIKE '%Ferreira%Gueymard%'
ORDER BY market_title
''')

tokens_to_check = []
for row in cur.fetchall():
    market, token_id, side, cond = row
    tokens_to_check.append((market, token_id, side, cond))
    
conn.close()

# Initialize CLOB client
client = ClobClient(
    host='https://clob.polymarket.com',
    key=os.getenv('POLYMARKET_PRIVATE_KEY'),
    chain_id=137
)

print("=== LIQUIDITY CHECK ===\n")

checked_markets = set()
for market, token_id, side, cond in tokens_to_check:
    if market in checked_markets:
        continue
    checked_markets.add(market)
    
    try:
        book = client.get_order_book(token_id)
        best_ask = book.asks[0].price if book.asks else None
        best_bid = book.bids[0].price if book.bids else None
        
        spread = (float(best_ask) - float(best_bid)) if (best_ask and best_bid) else 999
        
        if spread < 0.10:  # Less than 10 cent spread = liquid
            status = "LIQUID"
        elif spread < 0.30:
            status = "OK"
        else:
            status = "ILLIQUID"
            
        print(f"{market[:45]}...")
        print(f"  {side} side: Bid ${best_bid} / Ask ${best_ask} | Spread: ${spread:.2f} | {status}")
        print()
    except Exception as e:
        print(f"{market[:45]}... ERROR: {e}")
        print()
