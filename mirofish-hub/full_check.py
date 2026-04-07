import sqlite3
import os

print("=" * 50)
print("FULL SYSTEM CHECK")
print("=" * 50)

# 1. Whale Hunter DB
print("\n--- WHALE HUNTER DB ---")
wh_db = 'data/whale_hunter.db'
if os.path.exists(wh_db):
    conn = sqlite3.connect(wh_db)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM tracked_whales')
    print(f"Tracked Whales: {cur.fetchone()[0]}")
    cur.execute('SELECT COUNT(*) FROM whale_positions')
    print(f"Total Positions: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome='pending'")
    print(f"Pending: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome='won'")
    print(f"Won: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome='lost'")
    print(f"Lost: {cur.fetchone()[0]}")
    conn.close()
else:
    print("whale_hunter.db NOT FOUND")

# 2. Outcomes DB
print("\n--- OUTCOMES DB ---")
outcomes_db = 'outcomes.db'
if os.path.exists(outcomes_db):
    conn = sqlite3.connect(outcomes_db)
    cur = conn.cursor()
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"Tables: {[t[0] for t in tables]}")
    
    for table in tables:
        tname = table[0]
        cur.execute(f"SELECT COUNT(*) FROM {tname}")
        print(f"  {tname}: {cur.fetchone()[0]} rows")
    conn.close()
else:
    print("outcomes.db NOT FOUND")

# 3. Orchestrator DB
print("\n--- ORCHESTRATOR DB ---")
orch_db = 'data/orchestrator.db'
if os.path.exists(orch_db):
    conn = sqlite3.connect(orch_db)
    cur = conn.cursor()
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    for table in tables:
        tname = table[0]
        cur.execute(f"SELECT COUNT(*) FROM {tname}")
        print(f"  {tname}: {cur.fetchone()[0]} rows")
    conn.close()
else:
    print("orchestrator.db NOT FOUND")

# 4. Check Trading Wallet
print("\n--- TRADING WALLET ---")
try:
    from web3 import Web3
    from dotenv import load_dotenv
    load_dotenv()
    
    rpc_url = os.getenv('POLYGON_RPC_URL', 'https://polygon-rpc.com')
    wallet = '0x299aCc0857B943d8490ECb1820fD458B3B58c728'
    
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    # MATIC balance
    matic = w3.eth.get_balance(wallet)
    print(f"MATIC: {w3.from_wei(matic, 'ether'):.4f}")
    
    # USDC.e balance
    usdc_e = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
    abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},{"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}]
    contract = w3.eth.contract(address=w3.to_checksum_address(usdc_e), abi=abi)
    balance = contract.functions.balanceOf(w3.to_checksum_address(wallet)).call()
    decimals = contract.functions.decimals().call()
    print(f"USDC.e: ${balance / (10 ** decimals):.2f}")
except Exception as e:
    print(f"Wallet check failed: {e}")

print("\n--- CHECK COMPLETE ---")
