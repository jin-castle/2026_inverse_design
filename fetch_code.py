import sqlite3, json
IDS = [333,341,353,375,378,381,389,400,505,513,526,528,539,548,554,559,562,573,575,592]
conn = sqlite3.connect("/app/db/knowledge.db")
results = {}
for eid in IDS:
    row = conn.execute("SELECT id, title, code FROM examples WHERE id=?", (eid,)).fetchone()
    if row:
        results[row[0]] = {"title": row[1], "code": row[2]}
conn.close()
with open("/tmp/typec_codes.json","w") as f:
    json.dump(results, f)
print(f"saved {len(results)} examples")
for eid in IDS:
    if eid not in results:
        print(f"MISSING: {eid}")
