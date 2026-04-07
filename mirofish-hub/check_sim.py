#!/usr/bin/env python3
from mirofish_client import MiroFishClient
client = MiroFishClient()
sim_id = 'sim_f4b9b8bae234'
status = client.get_simulation(sim_id)
data = status.get('data', {})
print(f"Status: {data.get('status')}")
print(f"Profiles: {data.get('profiles_count')}")
print(f"Round: {data.get('current_round')}")
print(f"Twitter: {data.get('twitter_status')}")
print(f"Reddit: {data.get('reddit_status')}")
