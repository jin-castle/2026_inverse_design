import sqlite3
import sys

conn = sqlite3.connect('db/knowledge.db')
c = conn.cursor()

names = sys.argv[1:]
for name in names:
    c.execute("SELECT name, demo_code FROM concepts WHERE name=?", (name,))
    row = c.fetchone()
    if row:
        print(f"=== {row[0]} (len={len(row[1]) if row[1] else 0}) ===")
        if row[1]:
            print(row[1])
        print()

conn.close()
