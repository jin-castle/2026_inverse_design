import sqlite3
import sys

conn = sqlite3.connect('db/knowledge.db')
c = conn.cursor()

names = sys.argv[1:]
if not names:
    names = ['OptimizationProblem', 'bend', 'MPB', 'FluxRegion', 'Prism', 'Simulation', 'Block']

for name in names:
    c.execute("SELECT name, demo_code FROM concepts WHERE name=?", (name,))
    row = c.fetchone()
    if row:
        print(f"=== {row[0]} ===")
        print(row[1][:500] if row[1] else "(None)")
        print()

conn.close()
