import requests

# Check known whales for current open positions
whales = [
    ('swisstony', '0x9bad4efb6ef620206318b54f0c0ef4be22a6c0c6'),
    ('anoin123', '0x83a80e40e9a8dbb9c7e79e3fab0700a3d7eb8a50'),
]

print("=== CHECKING WHALE OPEN POSITIONS ===")
for name, addr in whales:
    try:
        url = f'https://data-api.polymarket.com/positions?user={addr}&sizeThreshold=0'
        r = requests.get(url, timeout=30)
        data = r.json()
        count = len(data) if data else 0
        print(f"\n{name} ({addr[:10]}...): {count} open positions")
        if data and count > 0:
            for p in data[:3]:
                title = p.get('title', p.get('question', '?'))[:40]
                outcome = p.get('outcome', '?')
                size = p.get('size', 0)
                print(f"  - {title}... ({outcome}, size={size})")
    except Exception as e:
        print(f"{name}: ERROR - {e}")

print("\n=== DONE ===")
