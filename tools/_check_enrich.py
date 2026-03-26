import sqlite3
conn = sqlite3.connect("db/knowledge.db")
null_physics = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE physics_cause IS NULL OR physics_cause=''").fetchone()[0]
print(f"physics_cause 비어있음: {null_physics}건")
# live_runs 중 sim_errors_v2에 없는 것 (enrich 대상 후보)
pending_enrich = conn.execute("""
    SELECT COUNT(*) FROM sim_errors_v2 
    WHERE (physics_cause IS NULL OR physics_cause='') 
    AND (error_class IS NOT NULL)
""").fetchone()[0]
print(f"enrich 대상: {pending_enrich}건")
conn.close()
