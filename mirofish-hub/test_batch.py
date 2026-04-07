import time
import requests

# Get swisstony's positions
start = time.time()
r = requests.get('https://data-api.polymarket.com/positions?user=0x204f72f35326db932158cba6adff0b9a1da95e14', timeout=30)
positions = r.json()
print(f"Got {len(positions)} positions in {time.time()-start:.1f}s")

# Extract token_ids
token_ids = [p.get("asset", "") for p in positions if p.get("asset")]
print(f"Unique tokens: {len(set(token_ids))}")

# Test batch lookup
start = time.time()
CHUNK_SIZE = 20
for i in range(0, len(token_ids), CHUNK_SIZE):
    chunk = token_ids[i:i + CHUNK_SIZE]
    try:
        resp = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"clob_token_ids": ",".join(chunk)},
            timeout=15,
        )
        print(f"Chunk {i//CHUNK_SIZE + 1}: {resp.status_code}, {len(resp.json())} markets")
    except Exception as e:
        print(f"Chunk {i//CHUNK_SIZE + 1} error: {e}")

print(f"Total batch time: {time.time()-start:.1f}s")
