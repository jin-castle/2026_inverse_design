import sqlite3
conn = sqlite3.connect('db/knowledge.db')
conn.row_factory = sqlite3.Row

# Check fix_worked=1 records
rows = conn.execute(
    "SELECT id, error_class, error_type, error_message, fix_type, fix_description FROM sim_errors_v2 WHERE fix_worked=1"
).fetchall()
print(f"fix_worked=1 records: {len(rows)}")
for r in rows:
    print(f"  id={r['id']}: {r['error_class']} | {r['error_type']} | {str(r['error_message'])[:60]}")
    print(f"    fix_type={r['fix_type']}")

# Now test the search query
print("\n--- Testing v2 search query with 'AttributeError' ---")
primary_type = "AttributeError"
result = conn.execute("""
    SELECT error_class, error_type, error_message, symptom,
           physics_cause, code_cause, root_cause_chain,
           fix_type, fix_description, code_diff, fix_worked, source
    FROM sim_errors_v2
    WHERE (error_type = ? OR error_message LIKE ? OR physics_cause LIKE ?)
      AND fix_worked = 1
    ORDER BY fix_worked DESC LIMIT 3
""", (primary_type, f"%{primary_type}%", f"%{primary_type}%")).fetchall()
print(f"Results: {len(result)}")
for r in result:
    print(f"  {r['error_type']} | fix_worked={r['fix_worked']}")

print("\n--- Testing v2 search without fix_worked filter ---")
result2 = conn.execute("""
    SELECT error_class, error_type, error_message, fix_worked
    FROM sim_errors_v2
    WHERE fix_worked = 1
    LIMIT 10
""").fetchall()
print(f"All fix_worked=1: {len(result2)}")
for r in result2:
    print(f"  {r['error_type']} | {str(r['error_message'])[:60]}")

conn.close()
