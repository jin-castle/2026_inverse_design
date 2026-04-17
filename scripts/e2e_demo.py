#!/usr/bin/env python3
"""
E2E 검증 데모: MEEP 오류 → KB 검색 → 자동 수정 흐름
3가지 시나리오:
  1. hard-error  : DiffractedPlanewave unexpected keyword argument
  2. silent-bug  : gradient ratio ~2배 어긋남 (numerical symptom)
  3. convergence : T+R > 1.0 에너지 보존 위반 (behavioral symptom)

API: http://localhost:8765
"""

import json, os, sys, urllib.request, urllib.parse, time
from pathlib import Path

KB_API = os.environ.get("MEEP_KB_URL", "http://localhost:8765")
INGEST_KEY = ""

# .env에서 키 로드
env_path = Path("/mnt/c/Users/user/projects/meep-kb/.env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("INGEST_API_KEY") and "=" in line:
            INGEST_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")

# ── HTTP 헬퍼 ─────────────────────────────────────────────────────────────────
def api_post(path: str, payload: dict, headers: dict = None, retries: int = 2) -> dict:
    url  = f"{KB_API}{path}"
    data = json.dumps(payload).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req  = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if attempt < retries - 1:
                print(f"  [retry {attempt+1}] {str(e)[:50]}", flush=True)
                time.sleep(2)
            else:
                return {"error": str(e)}

def sep(title=""):
    print(f"\n{'='*60}")
    if title:
        print(f"  {title}")
        print(f"{'='*60}")

# ── 시나리오 실행기 ────────────────────────────────────────────────────────────
def run_scenario(num: int, title: str, error_msg: str, search_query: str,
                 expected_keyword: str, fix_description: str):
    sep(f"시나리오 {num}: {title}")

    # 1) 에러 발생 시뮬레이션
    print(f"\n[1] 에러 발생:")
    print(f"  {error_msg[:120]}")

    # 2) KB 검색
    print(f"\n[2] KB 검색: '{search_query[:60]}'")
    t0 = time.time()
    result = api_post("/api/search", {"query": search_query, "n": 5})
    elapsed = time.time() - t0

    if "error" in result:
        print(f"  KB 검색 실패: {result['error']}")
        return False

    results = result.get("results", [])
    print(f"  검색 완료 ({elapsed:.1f}s) | 결과 {len(results)}건 | 모드: {result.get('mode','?')}")

    # 3) 결과 분석
    print(f"\n[3] 검색 결과 TOP-3:")
    hit_top1 = False
    hit_top3 = False
    for i, r in enumerate(results[:3], 1):
        title_str = r.get("title", "")[:60]
        score     = r.get("score", 0)
        source    = r.get("source", "")
        verif     = r.get("verification_criteria", "")
        diag      = r.get("diagnostic_snippet", "")

        # hit 판정: expected_keyword가 title/cause/solution에 포함
        cause_txt = (r.get("cause", "") + r.get("solution", "")).lower()
        is_hit = (expected_keyword.lower() in title_str.lower() or
                  expected_keyword.lower() in cause_txt)

        hit_marker = " ✓ HIT" if is_hit else ""
        print(f"  [{i}] score={score:.3f} src={source:8s} | {title_str}{hit_marker}")
        if verif:
            try:
                v = json.loads(verif)
                print(f"      verification: {v.get('description','')[:70]}")
            except:
                pass
        if diag and i == 1:
            print(f"      diagnostic_snippet: {diag[:60].strip()}...")

        if i == 1 and is_hit:
            hit_top1 = True
        if is_hit:
            hit_top3 = True

    # 4) LLM 생성 답변 (있을 경우)
    answer = result.get("answer", "")
    if answer:
        print(f"\n[4] KB 생성 답변 (요약):")
        # 첫 300자만 출력
        lines = answer.strip().split("\n")
        for line in lines[:8]:
            if line.strip():
                print(f"  {line[:100]}")

    # 5) 수정 적용 시뮬레이션
    print(f"\n[5] 수정 적용: {fix_description}")

    # 6) MARL→KB 자동 ingest (수정 성공 케이스)
    print(f"\n[6] 수정 결과 KB ingest:")
    fix_item = {
        "error_type": title.split(":")[0].strip(),
        "error_message": error_msg,
        "original_code": f"# 오류 코드 (시나리오 {num})",
        "fixed_code": f"# 수정된 코드 (시나리오 {num})\n# fix: {fix_description}",
        "fix_description": fix_description,
        "kb_suggestion": results[0].get("cause", "") if results else "",
        "fix_worked": 1,
    }
    ingest_result = api_post(
        "/api/ingest/sim_error",
        {
            "error_type": fix_item["error_type"],
            "error_message": fix_item["error_message"][:500],
            "original_code": fix_item["original_code"],
            "fixed_code": fix_item["fixed_code"],
            "fix_description": fix_item["fix_description"],
            "root_cause": fix_item["kb_suggestion"][:200],
            "source": "e2e_demo",
            "fix_worked": 1,
            "project_id": f"E2E-DEMO-{num:02d}",
        },
        headers={"X-Ingest-Key": INGEST_KEY} if INGEST_KEY else {}
    )

    if ingest_result.get("ok"):
        print(f"  ingest 성공: id={ingest_result.get('id')} chroma={ingest_result.get('chroma_ok')}")
    else:
        print(f"  ingest 결과: {ingest_result}")

    # 7) 결과 요약
    status = "✓ PASS" if hit_top3 else "✗ MISS"
    top1_str = "top-1 HIT" if hit_top1 else ("top-3 HIT" if hit_top3 else "MISS")
    print(f"\n[결과] {status} | {top1_str} | 검색 {elapsed:.1f}s")
    return hit_top3

# ── 메인 ─────────────────────────────────────────────────────────────────────
def main():
    print("MEEP-KB E2E 검증 데모")
    print(f"API: {KB_API}")

    # API 상태 확인
    try:
        r = urllib.request.urlopen(f"{KB_API}/api/status", timeout=5)
        status = json.loads(r.read())
        print(f"KB 상태: errors={status['db_errors']} examples={status['db_examples']} ready={status['server_ready']}")
    except Exception as e:
        print(f"KB 연결 실패: {e}")
        sys.exit(1)

    results = []

    # ── 시나리오 1: hard-error ────────────────────────────────────────────────
    ok = run_scenario(
        num=1,
        title="hard-error: DiffractedPlanewave unexpected keyword",
        error_msg="TypeError: Source.__init__() got an unexpected keyword argument 'amp_func' ... DiffractedPlanewave passed as src=",
        search_query="DiffractedPlanewave amp_func oblique plane wave k_point Bloch MEEP Source",
        expected_keyword="plane_wave",
        fix_description="DiffractedPlanewave를 src= 대신 amp_func= 파라미터로 이동",
    )
    results.append(("hard-error", ok))

    # ── 시나리오 2: silent-bug (numerical) ───────────────────────────────────
    ok = run_scenario(
        num=2,
        title="silent-bug: adjoint gradient ratio ~2배 어긋남",
        error_msg="gradient check 통과하지만 ratio=1.98: adj_grad=-0.0234 fd_grad=-0.0118 (모든 idx에서 ~2배 차이)",
        search_query="adjoint gradient ratio 2배 finite difference EigenModeCoefficient |c|^2",
        expected_keyword="gradient",
        fix_description="objective에서 |c| → |c|^2 로 수정 (chain-rule 2배 인자 누락 수정)",
    )
    results.append(("silent-bug", ok))

    # ── 시나리오 3: convergence (behavioral) ─────────────────────────────────
    ok = run_scenario(
        num=3,
        title="convergence: T+R > 1.0 에너지 보존 위반",
        error_msg="simulation완료, T=1.23 R=0.05 → T+R=1.28 (에너지 보존 위반, NaN 없음)",
        search_query="T greater than 1 transmission 100% flux normalization incident power MEEP",
        expected_keyword="normalization",
        fix_description="normalization flux 계산 오류: 입사파 flux 측정 위치를 소스 앞으로 이동",
    )
    results.append(("convergence", ok))

    # ── 최종 요약 ──────────────────────────────────────────────────────────────
    sep("최종 결과 요약")
    passed = sum(1 for _, ok in results if ok)
    print(f"\n{'시나리오':30s} {'결과':10s}")
    print("-" * 42)
    for name, ok in results:
        mark = "✓ PASS" if ok else "✗ MISS"
        print(f"  {name:28s} {mark}")
    print("-" * 42)
    print(f"  성공률: {passed}/{len(results)} ({passed/len(results)*100:.0f}%)")

    # 회귀 테스트도 실행
    sep("회귀 테스트 세트 (20케이스)")
    reg_path = Path("/mnt/c/Users/user/projects/meep-kb/tests/kb_regression")
    if not reg_path.exists():
        print("  회귀 테스트 디렉토리 없음")
        return

    cases = sorted(reg_path.glob("case_*_input.md"))
    print(f"  케이스 수: {len(cases)}")
    reg_hit1 = reg_hit3 = 0
    for case_path in cases[:20]:
        query = case_path.read_text()[:500].strip()
        exp_path = case_path.with_name(case_path.name.replace("_input.md", "_expected.yaml"))
        if not exp_path.exists():
            continue

        # expected id 파싱
        exp_text = exp_path.read_text()
        exp_id = ""
        for line in exp_text.splitlines():
            if "sim_v2_" in line:
                import re
                m = re.search(r"sim_v2_(\d+)", line)
                if m:
                    exp_id = m.group(1)
                    break

        res = api_post("/api/search", {"query": query[:300], "n": 5})
        if "error" in res:
            continue

        titles = " ".join(r.get("title","") + r.get("cause","") for r in res.get("results",[][:3]))
        hit1 = exp_id and exp_id in " ".join(r.get("title","") for r in res.get("results",[])[:1])
        hit3 = exp_id and exp_id in titles

        if hit1: reg_hit1 += 1
        if hit3: reg_hit3 += 1
        mark = "✓" if hit3 else "·"
        print(f"  {mark} {case_path.stem} (exp=sim_v2_{exp_id})", flush=True)
        time.sleep(0.2)

    n_actual = min(len(cases), 20)
    print(f"\n  회귀 테스트 top-1 hitrate: {reg_hit1}/{n_actual} ({reg_hit1/max(n_actual,1)*100:.0f}%)")
    print(f"  회귀 테스트 top-3 hitrate: {reg_hit3}/{n_actual} ({reg_hit3/max(n_actual,1)*100:.0f}%)")

if __name__ == "__main__":
    main()
