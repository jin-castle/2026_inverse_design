#!/usr/bin/env python3
"""
E2E + 회귀 테스트 (Docker 컨테이너 내부 직접 실행)
네트워크 없이 DB + search_executor 직접 호출
"""
import sys, sqlite3, json, re, time
from pathlib import Path

sys.path.insert(0, '/app/agent')
sys.path.insert(0, '/app/query')

DB_PATH  = '/app/db/knowledge.db'
REG_PATH = Path('/app/tests/kb_regression')

# ── search_executor 로드 ───────────────────────────────────────────────────────
from search_executor import sim_errors_v2_search, keyword_search, vector_search, merge_results

def search_all(query: str, n: int = 5) -> list:
    """키워드 + 벡터 + sim_v2 통합 검색"""
    items = []
    try:
        items += keyword_search(query, ['errors','examples','docs'], n)
    except: pass
    try:
        items += vector_search(query, query.split(), ['errors','examples','docs'], n)
    except: pass
    try:
        items += sim_errors_v2_search(query, n)
    except: pass
    return merge_results(items, n)

def sep(title=''):
    print(f"\n{'='*60}")
    if title:
        print(f"  {title}")
        print('='*60)

# ── E2E 시나리오 3개 ──────────────────────────────────────────────────────────
SCENARIOS = [
    {
        "num": 1,
        "title": "hard-error: DiffractedPlanewave unexpected keyword",
        "error_msg": "TypeError: Source.__init__() got an unexpected keyword argument — DiffractedPlanewave was passed to src= instead of amp_func=",
        "query": "DiffractedPlanewave amp_func oblique plane wave k_point Bloch MEEP Source TypeError",
        "expect_keywords": ["diffractedplanewave", "plane_wave", "oblique", "amp_func"],
        "fix": "DiffractedPlanewave를 src= 대신 amp_func= 파라미터로 이동",
    },
    {
        "num": 2,
        "title": "silent-bug: adjoint gradient ratio ~2배 어긋남",
        "error_msg": "gradient ratio=1.98 모든 idx에서 adj_grad≈2×fd_grad, EigenModeCoefficient |c| vs |c|^2 chain-rule 누락",
        "query": "adjoint gradient ratio 2.0 EigenModeCoefficient finite difference mismatch chain-rule",
        "expect_keywords": ["gradient", "adjoint", "wrongadjointsource", "eigenmodecoefficient"],
        "fix": "objective |c| → |c|^2 수정 (chain-rule 2배 인자 누락)",
    },
    {
        "num": 3,
        "title": "convergence: T+R > 1.0 에너지 보존 위반",
        "error_msg": "T=1.23 R=0.05 T+R=1.28 에너지 보존 위반, NaN 없음, flux normalization 오류",
        "query": "T greater than 1.0 transmission 100% flux normalization incident energy conservation MEEP",
        "expect_keywords": ["t > 100%", "normalization", "flux", "reflectionfluxsign"],
        "fix": "normalization flux 측정 위치를 소스 앞으로 이동, add_flux 순서 수정",
    },
]

def run_e2e():
    sep("E2E 검증 데모 (Docker 내부 직접)")
    results = []
    for s in SCENARIOS:
        sep(f"시나리오 {s['num']}: {s['title']}")
        print(f"\n[1] 에러: {s['error_msg'][:100]}")
        print(f"[2] KB 검색: '{s['query'][:60]}'")

        t0 = time.time()
        hits = search_all(s['query'], n=5)
        elapsed = time.time() - t0
        print(f"    완료 {elapsed:.1f}s | 결과 {len(hits)}건")

        print(f"\n[3] TOP-3:")
        hit1 = hit3 = False
        for i, r in enumerate(hits[:3], 1):
            title = r.get('title','')[:55]
            score = r.get('score', 0)
            src   = r.get('source','')
            verif = r.get('verification_criteria','')
            # hit 판정
            combined = (title + ' ' + r.get('cause','') + ' ' + r.get('solution','')).lower()
            is_hit = any(kw.lower() in combined for kw in s['expect_keywords'])
            mark = ' ✓ HIT' if is_hit else ''
            print(f"  [{i}] {score:.3f} {src:8s} | {title}{mark}")
            if verif:
                try:
                    v = json.loads(verif)
                    print(f"       verification: {v.get('description','')[:65]}")
                except: pass
            diag = r.get('diagnostic_snippet','')
            if diag and i == 1:
                print(f"       diagnostic: {diag[:55].strip()}...")
            if i == 1 and is_hit: hit1 = True
            if is_hit: hit3 = True

        status = 'PASS' if hit3 else 'MISS'
        top_str = 'top-1' if hit1 else ('top-3' if hit3 else 'miss')
        print(f"\n[수정] {s['fix']}")
        print(f"[결과] {'✓' if hit3 else '✗'} {status} | {top_str} | {elapsed:.1f}s")
        results.append((s['title'], hit1, hit3))

    sep("E2E 최종 요약")
    p1 = sum(1 for _,h1,_ in results if h1)
    p3 = sum(1 for _,_,h3 in results if h3)
    for title, h1, h3 in results:
        mark = '✓' if h3 else '✗'
        top  = 'top-1' if h1 else ('top-3' if h3 else 'miss')
        print(f"  {mark} {title[:45]} ({top})")
    print(f"\n  top-1 PASS: {p1}/3  top-3 PASS: {p3}/3  성공률: {p3/3*100:.0f}%")
    return p3

# ── 회귀 테스트 ───────────────────────────────────────────────────────────────
def run_regression():
    sep("회귀 테스트 세트")
    if not REG_PATH.exists():
        print("  회귀 테스트 디렉토리 없음")
        return 0, 0, 0

    cases = sorted(REG_PATH.glob('case_*_input.md'))[:20]
    print(f"  케이스: {len(cases)}건\n")
    hit1 = hit3 = total = 0

    for case_path in cases:
        text = case_path.read_text()
        # input.md에서 에러 메시지 핵심 부분만 추출 (코드블록 안 내용 우선)
        code_blocks = re.findall(r'```(?:\w*\n)?(.*?)```', text, re.DOTALL)
        if code_blocks:
            # 첫 번째 코드블록 = 실제 에러 메시지
            query = ' '.join(b.strip() for b in code_blocks[:2])[:300]
        else:
            # 코드블록 없으면 첫 5줄
            query = ' '.join(l.strip() for l in text.splitlines()[:5] if l.strip())[:300]

        exp_path = case_path.with_name(case_path.name.replace('_input.md','_expected.yaml'))
        exp_id = ''
        if exp_path.exists():
            for line in exp_path.read_text().splitlines():
                m = re.search(r'sim_v2_(\d+)', line)
                if m:
                    exp_id = m.group(1); break

        # hit_keywords 블록 파싱 (- "keyword" 형식)
        hit_kws = []
        if exp_path.exists():
            in_block = False
            for line in exp_path.read_text().splitlines():
                if 'hit_keywords:' in line:
                    in_block = True; continue
                if in_block:
                    if line.strip().startswith('-'):
                        m2 = re.search(r'["\'](.+?)["\']', line)
                        if m2: hit_kws.append(m2.group(1))
                    elif line.strip() and not line.strip().startswith('#'):
                        if not line.startswith(' ') and not line.startswith('\t'):
                            break  # 다음 키로 넘어감

        hits = search_all(query, n=5)
        all_text = ' '.join(
            (r.get('title','') + ' ' + r.get('cause','') + ' ' + r.get('solution','')).lower()
            for r in hits[:5]
        )
        top1_text = (hits[0].get('title','') + ' ' + hits[0].get('cause','')).lower() if hits else ''

        # hit 판정: hit_keywords 키워드 매칭 (unified 이후 id 직접 매칭 불가)
        def is_match(text):
            if hit_kws and any(kw.lower() in text for kw in hit_kws): return True
            return False

        h1 = is_match(top1_text)
        h3 = is_match(all_text)
        if h1: hit1 += 1
        if h3: hit3 += 1
        total += 1

        mark = '✓' if h3 else '·'
        top_src = hits[0].get('source','?') if hits else '-'
        top_score = hits[0].get('score',0) if hits else 0
        print(f"  {mark} {case_path.stem} | exp=sim_v2_{exp_id} | "
              f"top={top_src}:{top_score:.2f} | {'HIT' if h3 else 'miss'}")

    sep("회귀 테스트 결과")
    print(f"  처리: {total}건")
    print(f"  top-1 hitrate: {hit1}/{total} ({hit1/max(total,1)*100:.0f}%)")
    print(f"  top-3 hitrate: {hit3}/{total} ({hit3/max(total,1)*100:.0f}%)")
    return hit1, hit3, total

# ── 채움률 ────────────────────────────────────────────────────────────────────
def print_fill_rate():
    sep("DB 채움률 현황")
    conn = sqlite3.connect(DB_PATH, timeout=5)
    for t in ['sim_errors_v2','sim_errors','errors']:
        total = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        n_num = conn.execute(f"SELECT COUNT(*) FROM {t} WHERE symptom_numerical IS NOT NULL AND symptom_numerical != 'null'").fetchone()[0]
        n_beh = conn.execute(f"SELECT COUNT(*) FROM {t} WHERE symptom_behavioral IS NOT NULL AND symptom_behavioral != 'null'").fetchone()[0]
        n_err = conn.execute(f"SELECT COUNT(*) FROM {t} WHERE symptom_error_pattern IS NOT NULL AND symptom_error_pattern != 'null'").fetchone()[0]
        print(f"  {t}:")
        print(f"    numerical={n_num}/{total}({n_num/total*100:.0f}%)  "
              f"behavioral={n_beh}/{total}({n_beh/total*100:.0f}%)  "
              f"error_pattern={n_err}/{total}({n_err/total*100:.0f}%)")

    v = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE verification_criteria IS NOT NULL").fetchone()[0]
    d = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE diagnostic_snippet IS NOT NULL").fetchone()[0]
    f = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=1").fetchone()[0]
    print(f"\n  [sim_errors_v2] fix_worked=1: {f}건")
    print(f"    verification_criteria: {v}/{f} ({v/max(f,1)*100:.0f}%)")
    print(f"    diagnostic_snippet:    {d}/{f} ({d/max(f,1)*100:.0f}%)")
    conn.close()

if __name__ == '__main__':
    print_fill_rate()
    e2e_score = run_e2e()
    h1, h3, total = run_regression()
    sep("전체 검증 완료")
    print(f"  E2E 성공률:        {e2e_score}/3 ({e2e_score/3*100:.0f}%)")
    print(f"  회귀 top-1:        {h1}/{total} ({h1/max(total,1)*100:.0f}%)")
    print(f"  회귀 top-3:        {h3}/{total} ({h3/max(total,1)*100:.0f}%)")
    ok = e2e_score >= 2 and h3/max(total,1) >= 0.30
    print(f"\n  최종 판정: {'✓ PASS' if ok else '△ PARTIAL'}")
