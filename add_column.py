import sqlite3
c = sqlite3.connect('/app/db/knowledge.db')
cols = [x[1] for x in c.execute("PRAGMA table_info(examples)").fetchall()]
if 'description_ko' not in cols:
    c.execute("ALTER TABLE examples ADD COLUMN description_ko TEXT")
    c.commit()
    print("Column added: description_ko")
else:
    print("Column already exists: description_ko")
c.close()
