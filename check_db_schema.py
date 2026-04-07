import sqlite3

db_path = r'C:\Users\User\Desktop\mirofish-secure\backend\uploads\simulations\sim_891828f7abb1\twitter_simulation.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get post table schema
cursor.execute("PRAGMA table_info(post)")
columns = cursor.fetchall()
print("=== POST table columns ===")
for col in columns:
    print(f"  {col[1]}: {col[2]}")

# Get user table schema
cursor.execute("PRAGMA table_info(user)")
columns = cursor.fetchall()
print("\n=== USER table columns ===")
for col in columns:
    print(f"  {col[1]}: {col[2]}")

# Get a sample post
cursor.execute("SELECT * FROM post LIMIT 1")
row = cursor.fetchone()
print(f"\n=== Sample post ===")
print(row)

conn.close()
