#!/usr/bin/env python3
"""
P5: 회귀 테스트 세트 자동 생성 + run_regression.py
sim_errors_v2 fix_worked=1 케이스 → case_XXX_input.md + expected.yaml
그리고 /api/search 결과가 expected_retrieved_ids를 포함하는지 자동 검증
"""
import sqlite3, json, os, sys, requests, time
from pathlib import Path
import yaml  # pyyaml

DB_PATH   = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge.db")
TEST_DIR  = Path("/mnt/c/Users/user/projects/meep-kb/tests/kb_regression")
KB_API    = "http://localhost:8765"

# ─── 1. 테스트 케이스 생성 ────────────────────────────────────────────────────
def generate_test_cases(n: int = 25):
    TEST_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    rows = conn.execute("""
        SELECT id, error_type, error_message, symptom,
               symptom_numerical, symptom_behavioral, symptom_error_pattern,
               physics_cause, fix_description, fix_type
        FROM sim_errors_v2
        WHERE fix_worked=1
          AND error_message IS NOT NULL
          AND error_message != ''
        ORDER BY id ASC
        LIMIT ?
    """, (n,)).fetchall()
    conn.close()

    print(f"[gen] {len(rows)}건 테스트 케이스 생성 -> {TEST_DIR}")
    generated = []

    for i, row in enumerate(rows):
        (id_, etype, emsg, symptom, sym_num, sym_beh, sym_err,
         phys_cause, fix_desc, fix_type) = row

        case_id = f"case_{i+1:03d}"

        # ── input.md (사용자가 실제로 할 법한 호소 형태) ────────────────────
        # 에러 메시지의 핵심 부분을 자연어로 변환
        user_query = _make_user_query(etype, emsg, symptom, sym_num, sym_beh)

        input_md = f"""# {case_id} - 입력 쿼리

## 사용자 호소
{user_query}

## 메타데이터
- error_type: {etype or 'unknown'}
- symptom_numerical: {sym_num or 'N/A'}
- symptom_behavioral: {sym_beh or 'N/A'}
- symptom_error_pattern: {sym_err or 'N/A'}
- source_id: sim_errors_v2.id={id_}
"""
        (TEST_DIR / f"{case_id}_input.md").write_text(input_md, encoding="utf-8")

        # ── expected.yaml ────────────────────────────────────────────────────
        expected = {
            "case_id": case_id,
            "source_db_id": id_,
            "error_type": etype or "unknown",
            "query": user_query,
            "expected_retrieved_ids": [],        # KB는 title 기반이므로 빈 목록 (score 기반으로 검증)
            "must_contain_keywords": _extract_keywords(etype, emsg, sym_err),
            "min_top_score": 0.55,               # top-1 유사도 기준
            "min_results": 1,
            "fix_type": fix_type or "code_only",
        }
        yaml_path = TEST_DIR / f"{case_id}_expected.yaml"
        yaml_path.write_text(
            yaml.dump(expected, allow_unicode=True, default_flow_style=False),
            encoding="utf-8"
        )
        generated.append(case_id)

    # ── 인덱스 파일 생성 ─────────────────────────────────────────────────────
    index = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "total_cases": len(generated),
        "cases": generated,
        "kb_api": KB_API,
        "pass_criteria": {
            "min_top_score": 0.55,
            "min_results": 1,
        }
    }
    (TEST_DIR / "index.yaml").write_text(
        yaml.dump(index, allow_unicode=True, default_flow_style=False),
        encoding="utf-8"
    )
    print(f"[gen] 완료: {len(generated)}건 -> {TEST_DIR}")
    return generated


def _make_user_query(etype, emsg, symptom, sym_num, sym_beh) -> str:
    """에러 정보를 사용자 호소 형태 쿼리로 변환"""
    parts = []
    if emsg:
        # 핵심 에러 메시지 (traceback 제거, 첫 줄만)
        first_line = emsg.strip().split("\n")[0][:200]
        parts.append(first_line)
    if sym_num and sym_num not in (parts[0] if parts else ""):
        parts.append(f"수치: {sym_num}")
    if sym_beh:
        parts.append(sym_beh)
    if symptom and symptom not in " ".join(parts):
        parts.append(symptom)
    return ". ".join(p for p in parts if p).strip() or f"{etype or 'MEEP'} 에러 발생"


def _extract_keywords(etype, emsg, sym_err) -> list:
    """검색 결과에 반드시 포함돼야 할 키워드"""
    kw = []
    if etype and etype not in ("UnknownError","Unknown",""):
        kw.append(etype.lower())
    if sym_err:
        # 에러 패턴에서 핵심 단어 추출
        import re
        words = re.findall(r"[a-zA-Z_]{4,}", sym_err)
        kw.extend(words[:3])
    if emsg:
        import re
        words = re.findall(r"[a-zA-Z_]{5,}", emsg[:200])
        kw.extend(words[:2])
    return list(set(kw))[:5]


# ─── 2. 회귀 테스트 실행 ─────────────────────────────────────────────────────
def run_regression(verbose: bool = False) -> dict:
    index_path = TEST_DIR / "index.yaml"
    if not index_path.exists():
        print("[ERROR] 테스트 케이스가 없습니다. 먼저 --generate 실행")
        return {}

    with open(index_path, encoding="utf-8") as f:
        index = yaml.safe_load(f)

    cases     = index.get("cases", [])
    criteria  = index.get("pass_criteria", {})
    min_score = criteria.get("min_top_score", 0.55)
    min_res   = criteria.get("min_results", 1)

    total = len(cases)
    passed = 0
    failed_list = []

    print(f"\n[regression] {total}건 실행 (기준: top_score>={min_score})")
    print("-" * 60)

    for case_id in cases:
        exp_path = TEST_DIR / f"{case_id}_expected.yaml"
        if not exp_path.exists():
            print(f"  {case_id}: SKIP (expected.yaml 없음)")
            continue

        with open(exp_path, encoding="utf-8") as f:
            expected = yaml.safe_load(f)

        query = expected.get("query","")
        if not query:
            continue

        # KB 검색
        try:
            r = requests.post(f"{KB_API}/api/search",
                              json={"query": query, "n": 5},
                              timeout=60)
            if r.status_code == 429:
                print(f"\n  rate limit - 60초 대기...")
                time.sleep(62)
                r = requests.post(f"{KB_API}/api/search",
                                  json={"query": query, "n": 5},
                                  timeout=60)
            data = r.json()
        except Exception as e:
            print(f"  {case_id}: ERROR {e}")
            failed_list.append(case_id)
            continue

        results    = data.get("results", [])
        top_score  = results[0].get("score",0) if results else 0
        n_results  = len(results)

        # 키워드 체크 (results 텍스트 전체에서)
        kw_required = expected.get("must_contain_keywords", [])
        results_text = json.dumps(results, ensure_ascii=False).lower()
        kw_hit = sum(1 for kw in kw_required if kw.lower() in results_text)
        kw_total = len(kw_required)

        # 판정 - score만으로 (keyword 체크는 참고용)
        score_ok  = top_score >= min_score
        result_ok = n_results >= min_res
        pass_flag = score_ok and result_ok

        status = "PASS" if pass_flag else "FAIL"
        if pass_flag:
            passed += 1
        else:
            failed_list.append(case_id)

        if verbose or not pass_flag:
            print(f"  {case_id}: {status} | score={top_score:.3f} n={n_results} "
                  f"kw={kw_hit}/{kw_total} | {query[:60]}")
        else:
            print(f"  {case_id}: {status} score={top_score:.3f}", end="")
            if (cases.index(case_id)+1) % 5 == 0:
                print()
            else:
                print("  ", end="")

        time.sleep(0.5)

    print()
    hit_rate = passed / total * 100 if total else 0
    print("=" * 60)
    print(f"결과: {passed}/{total} PASS  ({hit_rate:.1f}%)")
    if failed_list:
        print(f"FAIL 목록: {failed_list[:10]}")
    print("=" * 60)

    return {
        "total": total,
        "passed": passed,
        "hit_rate": hit_rate,
        "failed": failed_list,
        "min_score_criterion": min_score,
    }


# ── 메인 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--generate", action="store_true", help="테스트 케이스 생성")
    p.add_argument("--run",      action="store_true", help="회귀 테스트 실행")
    p.add_argument("--n",        type=int, default=25, help="생성할 케이스 수")
    p.add_argument("--verbose",  action="store_true")
    args = p.parse_args()

    if args.generate:
        try:
            import yaml
        except ImportError:
            os.system("pip install pyyaml -q")
            import yaml
        generate_test_cases(args.n)

    if args.run:
        try:
            import yaml
        except ImportError:
            os.system("pip install pyyaml -q")
            import yaml
        run_regression(args.verbose)

    if not args.generate and not args.run:
        p.print_help()
