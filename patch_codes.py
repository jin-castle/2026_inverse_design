#!/usr/bin/env python3
"""
knowledge.db에서 코드 추출 + 공통 패치 적용 → 파일로 저장
로컬 Windows에서 실행
"""
import sqlite3, os, re, json

DB_PATH = r"C:\Users\user\projects\meep-kb\db\knowledge.db"
OUT_DIR = r"C:\Users\user\projects\meep-kb\patched_codes"
os.makedirs(OUT_DIR, exist_ok=True)

# Worker 그룹: 코드 수정 + 재실행 (savefig 경로 등)
WORKER_IDS = [333, 381, 400, 539, 562, 592]
# SimServer 그룹: 오래 걸리는 시뮬레이션
SIMSERVER_IDS = [341, 353, 375, 389, 505, 513, 526, 528, 548, 573]

ALL_IDS = WORKER_IDS + SIMSERVER_IDS

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute(f"SELECT id, title, code FROM examples WHERE id IN ({','.join(map(str, ALL_IDS))}) ORDER BY id")
rows = cur.fetchall()
conn.close()

def patch_code(code, eid):
    """공통 패치 적용"""
    if not code:
        return code

    lines = code.splitlines()
    patched = []
    fig_counter = [0]
    in_plt_section = False

    # 1. numpy 수정
    code = code.replace('np.complex_', 'np.complex128')
    code = code.replace('numpy.complex_', 'numpy.complex128')

    # 2. get_array API 수정 (구버전 → 신버전)
    code = re.sub(r'get_array\(mp\.Volume\(', 'get_array(vol=mp.Volume(', code)
    code = re.sub(r'get_array\(Volume\(', 'get_array(vol=Volume(', code)

    # 3. shading='flat' → 'auto' (333번 전용이지만 전체 적용 무방)
    code = code.replace("shading='flat'", "shading='auto'")
    code = code.replace('shading="flat"', 'shading="auto"')

    # 4. matplotlib Agg 백엔드 추가
    if 'matplotlib' in code and 'matplotlib.use' not in code:
        # import meep 전에 삽입
        if 'import meep' in code:
            code = code.replace('import meep', 'import matplotlib\nmatplotlib.use("Agg")\nimport meep', 1)
        else:
            code = 'import matplotlib\nmatplotlib.use("Agg")\n' + code

    # 5. plt.show() → 저장으로 대체
    results_dir = f'/tmp/kb_results'
    prefix = f'ex_{eid}'

    # plt.show() 패턴을 savefig로 교체
    show_count = code.count('plt.show()')
    if show_count > 0:
        # 각 plt.show()를 순서대로 numbered savefig로 교체
        counter = [0]
        def replace_show(m):
            n = counter[0]
            counter[0] += 1
            return f'plt.savefig("{results_dir}/{prefix}_{n:02d}.png", dpi=100, bbox_inches="tight")\nplt.close()'
        code = re.sub(r'plt\.show\(\)', replace_show, code)

    # 6. plt.savefig 경로가 상대경로인 경우 절대경로로 수정
    def fix_savefig(m):
        path_arg = m.group(1)
        # 이미 절대경로거나 /tmp 포함이면 그대로
        if path_arg.startswith('/') or path_arg.startswith('"/"') or '/tmp/' in path_arg:
            return m.group(0)
        # 상대경로 수정
        basename = os.path.basename(path_arg.strip('"\''))
        if not basename:
            basename = f'{prefix}_fig.png'
        return f'plt.savefig("{results_dir}/{prefix}_{{basename}}"'
    # 단순 패턴만 처리
    code = re.sub(r'plt\.savefig\((["\'][^"\']+["\'])', 
                  lambda m: f'plt.savefig("{results_dir}/{prefix}_{os.path.basename(m.group(1).strip(chr(34)+chr(39)))}"'
                  if not m.group(1).strip('"\'').startswith('/') else m.group(0), code)

    # 7. 결과 디렉토리 생성 코드 추가 (맨 위에)
    mkdir_code = f'import os\nos.makedirs("{results_dir}", exist_ok=True)\n'
    if f'makedirs("{results_dir}"' not in code and f"makedirs('{results_dir}'" not in code:
        # import 섹션 뒤에 삽입
        first_non_import = 0
        for i, line in enumerate(code.splitlines()):
            if line.strip() and not line.startswith('#') and not line.startswith('import') and not line.startswith('from'):
                first_non_import = i
                break
        lines2 = code.splitlines()
        lines2.insert(first_non_import, mkdir_code)
        code = '\n'.join(lines2)

    return code

results = {}
for eid, title, code in rows:
    patched = patch_code(code, eid)
    group = 'worker' if eid in WORKER_IDS else 'simserver'
    fname = f"{group}_ex_{eid}.py"
    fpath = os.path.join(OUT_DIR, fname)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(patched or '')
    print(f"  [{group}] id={eid} → {fname} ({len(patched or '')} chars)")
    results[eid] = {'title': title[:60], 'group': group, 'file': fpath}

# 그룹 목록 저장
with open(os.path.join(OUT_DIR, 'groups.json'), 'w') as f:
    json.dump({'worker': WORKER_IDS, 'simserver': SIMSERVER_IDS}, f, indent=2)

print(f"\n총 {len(results)}개 패치 완료 → {OUT_DIR}")
print(f"Worker 그룹: {WORKER_IDS}")
print(f"SimServer 그룹: {SIMSERVER_IDS}")
