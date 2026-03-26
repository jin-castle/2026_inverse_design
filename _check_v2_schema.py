import sqlite3
conn = sqlite3.connect('C:/Users/user/projects/meep-kb/db/knowledge.db')
schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='sim_errors_v2'").fetchone()
print(schema[0] if schema else 'not found')
# check for UNIQUE on code_hash
indexes = conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='sim_errors_v2'").fetchall()
for idx in indexes:
    print(idx[0])
conn.close()
