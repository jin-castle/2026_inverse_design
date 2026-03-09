import subprocess

diag_code = (
    "# -*- coding: utf-8 -*-\n"
    "import sqlite3, os, glob\n"
    "path = '/app/db/knowledge.db'\n"
    "print('exists:', os.path.exists(path))\n"
    "print('rw:', os.access(path, os.R_OK|os.W_OK))\n"
    "try:\n"
    "    db = sqlite3.connect(path, timeout=3)\n"
    "    n = db.execute('SELECT COUNT(*) FROM errors').fetchone()[0]\n"
    "    print('errors count:', n)\n"
    "    db.close()\n"
    "    print('DB OK')\n"
    "except Exception as e:\n"
    "    print('DB ERR:', e)\n"
    "    print('WAL:', glob.glob('/app/db/*-wal') + glob.glob('/app/db/*.wal'))\n"
    "    print('SHM:', glob.glob('/app/db/*-shm') + glob.glob('/app/db/*.shm'))\n"
)

with open("C:/tmp/diag_docker.py", "w", encoding="ascii") as f:
    f.write(diag_code)

r = subprocess.run(["docker", "cp", "C:/tmp/diag_docker.py", "meep-kb-meep-kb-1:/tmp/diag.py"],
                   capture_output=True, text=True)
print("cp:", r.returncode, r.stderr)
r2 = subprocess.run(["docker", "exec", "meep-kb-meep-kb-1", "python3", "/tmp/diag.py"],
                    capture_output=True, text=True)
print(r2.stdout)
if r2.returncode != 0: print("STDERR:", r2.stderr[:300])
