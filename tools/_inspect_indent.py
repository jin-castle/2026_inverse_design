import sqlite3
conn = sqlite3.connect("db/knowledge.db")

for name in ["PML", "Symmetry"]:
    code = conn.execute("SELECT demo_code FROM concepts WHERE name=?", (name,)).fetchone()[0]
    print(f"\n=== {name} 문제 구간 ===")
    lines = code.splitlines()
    for i, line in enumerate(lines, 1):
        if any(k in line for k in ["for xy", "sym = [mp", "IndentationError", "unexpected"]):
            start = max(0, i-4)
            for j in range(start, min(len(lines), i+3)):
                marker = ">>> " if j == i-1 else "    "
                print(f"  {marker}L{j+1}: {repr(lines[j])}")
conn.close()
