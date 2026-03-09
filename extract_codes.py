import sqlite3, json, os

conn = sqlite3.connect('/app/db/knowledge.db')
cur = conn.cursor()

# fix-paths 그룹: 381, 539, 562, 592, 333
# simserver 그룹: 341, 353, 526, 573, 389, 400, 505, 513, 528, 548, 562 (나머지 timeout)
target_ids = [333, 341, 353, 375, 381, 389, 400, 505, 513, 526, 528, 539, 548, 562, 573, 592]

cur.execute(f"SELECT id, title, code, tags, result_status FROM examples WHERE id IN ({','.join(map(str, target_ids))}) ORDER BY id")
rows = cur.fetchall()

os.makedirs('/tmp/fix_codes', exist_ok=True)
summary = []
for row in rows:
    eid, title, code, tags, status = row
    fname = f'/tmp/fix_codes/ex_{eid}.py'
    with open(fname, 'w') as f:
        f.write(code or '')
    code_len = len(code) if code else 0
    has_plt = 'import matplotlib' in (code or '') or 'plt.' in (code or '') or 'import pymeep' in (code or '')
    has_mpi = 'mpirun' in (code or '') or 'MPI' in (code or '') or 'from mpi4py' in (code or '')
    has_meep = 'import meep' in (code or '') or 'import pymeep' in (code or '')
    summary.append({'id': eid, 'title': title[:60], 'status': status, 'code_len': code_len, 'has_plt': has_plt, 'has_mpi': has_mpi, 'has_meep': has_meep})
    print(f'id={eid} [{status}] len={code_len} plt={has_plt} mpi={has_mpi} meep={has_meep} | {title[:50]}')

conn.close()
print(f'\n총 {len(summary)}개 추출 완료 → /tmp/fix_codes/')
