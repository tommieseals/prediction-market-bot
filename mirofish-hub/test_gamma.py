#!/usr/bin/env python3
import requests
import sqlite3

# Get a condition_id from our database
conn = sqlite3.connect('C:/Users/USER/clawd/mirofish-hub/data/whale_hunter.db')
cur = conn.cursor()
cur.execute('SELECT condition_id, market_title FROM whale_positions LIMIT 3')

for row in cur.fetchall():
    print(f'\nTesting: {row[1][:50]}...')
    print(f'Condition ID: {row[0][:30]}...')
    
    # Try Gamma API - need to use the slug/id not condition_id
    # Gamma uses slug, not condition_id for the markets endpoint
    resp = requests.get(
        'https://gamma-api.polymarket.com/markets',
        params={'condition_id': row[0]},
        timeout=15
    )
    print(f'Status: {resp.status_code}')
    if resp.ok:
        data = resp.json()
        if data:
            market = data[0] if isinstance(data, list) else data
            print(f'Closed: {market.get("closed")}')
            print(f'End Date: {market.get("endDate")}')
            print(f'Prices: {market.get("outcomePrices")}')
        else:
            print('No data returned')
    else:
        print(f'Error: {resp.text[:200]}')
