import sys
sys.path.insert(0,'C:/Users/user/projects/meep-kb/cis_repro')
from corrected_codegen import build_corrected_code, fast_check_docker, PAPERS, RESULTS
from corrected_codegen import classify_all, auto_fix_loop
from pathlib import Path

for p in PAPERS:
    pid = p['paper_id']
    out = RESULTS / pid
    out.mkdir(parents=True, exist_ok=True)
    code = build_corrected_code(p, pid)
    issues = classify_all(code, '', {})
    if issues:
        eids = [r.error_id for r in issues]
        code, applied = auto_fix_loop(code)
        print(f'{pid}: 사전수정 {applied}')
    else:
        print(f'{pid}: 이슈없음')
    script = out / f'corrected_{pid}.py'
    script.write_text(code, encoding='utf-8')
    print(f'  {len(code.splitlines())}줄 생성')
    ok, err = fast_check_docker(script)
    result = "PASS" if ok else ("FAIL: " + err[:60])
    print(f'  fast-check: {result}')
    print()
