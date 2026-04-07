import sys
sys.path.insert(0, r'C:\Users\User\Desktop\mirofish-secure\backend')

from app.services.simulation_data_reader import SimulationDataReader, get_simulation_context_for_report

# Test reading simulation data
simulation_id = "sim_891828f7abb1"
graph_id = "no_zep_proj_38d3952ab359"

print(f"Testing SimulationDataReader for {simulation_id}...")

reader = SimulationDataReader(simulation_id)

# Test get_simulation_stats
print("\n=== Simulation Stats ===")
stats = reader.get_simulation_stats()
print(f"Status: {stats.get('status')}")
print(f"Total Rounds: {stats.get('total_rounds')}")
print(f"Total Actions: {stats.get('total_actions')}")
print(f"Agent Count: {stats.get('agent_count')}")
print(f"Post Count: {stats.get('post_count')}")

# Test get_agents
print("\n=== Agents (first 3) ===")
agents = reader.get_agents()
for i, agent in enumerate(agents[:3]):
    print(f"  {i+1}. {agent.get('name', 'Unknown')} - {agent.get('type', 'Unknown')}")

# Test get_all_posts
print("\n=== Posts (first 3) ===")
posts = reader.get_all_posts(limit=10)
for i, post in enumerate(posts[:3]):
    content = (post.get('content') or '')[:50]
    print(f"  {i+1}. [{post.get('platform')}] {post.get('author')}: {content}...")

# Test search
print("\n=== Search Test ===")
result = reader.search("AI regulation", limit=5)
print(f"Found {result.total_count} facts")
for i, fact in enumerate(result.facts[:3]):
    print(f"  {i+1}. {fact[:80]}...")

# Test full context
print("\n=== Full Context ===")
context = get_simulation_context_for_report(simulation_id, graph_id)
print(f"Source: {context.get('source')}")
print(f"Total Facts: {len(context.get('facts', []))}")
print(f"Total Agents: {len(context.get('agents', []))}")

reader.close()
print("\nDone!")
