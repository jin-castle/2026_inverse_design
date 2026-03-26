import sqlite3
conn = sqlite3.connect("db/knowledge.db")

# DFT 사용 개념들
rows = conn.execute(
    "SELECT name FROM concepts WHERE demo_code LIKE '%add_dft_fields%' OR demo_code LIKE '%get_dft_array%' ORDER BY name"
).fetchall()
print("DFT field 사용:", [r[0] for r in rows])

# bend 코드
code = conn.execute("SELECT demo_code FROM concepts WHERE name='bend'").fetchone()[0]
print("\n=== bend 코드 ===")
for i, l in enumerate(code.splitlines(), 1):
    print(f"{i:3}: {l}")

# PML 코드
pml_code = conn.execute("SELECT demo_code FROM concepts WHERE name='PML'").fetchone()[0]
print("\n=== PML 코드 ===")
for i, l in enumerate(pml_code.splitlines(), 1):
    print(f"{i:3}: {l}")

conn.close()
