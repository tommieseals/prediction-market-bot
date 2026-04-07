from polymarket_api import PolymarketAPI
api = PolymarketAPI()

# Search for Arkansas markets
markets = api.search_markets('Arkansas')
for m in markets[:5]:
    cid = m.get('condition_id', 'N/A')
    if cid and len(cid) > 20:
        cid = cid[:20] + '...'
    print(f"ID: {cid}")
    title = m.get('question') or m.get('title') or 'N/A'
    print(f"Title: {title}")
    print(f"Slug: {m.get('slug', 'N/A')}")
    tokens = m.get('tokens', [])
    for t in tokens:
        print(f"  Token: {t.get('outcome')} @ ${t.get('price', 'N/A')} - ID: {t.get('token_id', 'N/A')[:30]}...")
    print('---')
