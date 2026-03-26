import sqlite3
NAMES = ["Block", "PML", "mpi", "taper", "eig_band"]
conn = sqlite3.connect("db/knowledge.db")
for name in NAMES:
    row = conn.execute("SELECT demo_code FROM concepts WHERE name=?", (name,)).fetchone()
    print(f"\n{'='*60}")
    print(f"=== {name} ===")
    print(row[0][:800] if row and row[0] else "(없음)")
conn.close()
