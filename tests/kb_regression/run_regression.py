#!/usr/bin/env python3
"""
run_regression.py
-----------------
tests/kb_regression/ 디렉토리의 회귀 테스트 케이스를 순회하며
KB API에 검색을 요청하고 hit rate를 계산합니다.

Usage:
    python3 tests/kb_regression/run_regression.py
    python3 tests/kb_regression/run_regression.py --verbose
    python3 tests/kb_regression/run_regression.py --top-k 5
"""

import sys
import re
import json
import time
import argparse
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("ERROR: 'requests' 패키지가 필요합니다.  pip install requests")

# ── 설정 ──────────────────────────────────────────────────────────────────
HERE    = Path(__file__).parent           # tests/kb_regression/
KB_URL  = "http://localhost:8765"
SEARCH_ENDPOINT = f"{KB_URL}/api/search"
DEFAULT_TOP_K   = 5   # API에 요청할 최대 결과 수

# ── YAML 최소 파서 (pyyaml 의존성 없이 expected.yaml 읽기) ───────────────

def _parse_simple_yaml(text: str) -> dict:
    """
    expected.yaml의 단순 구조만 파싱합니다.
    지원 형식:
        key: value
        key:
          - item1
          - item2
        key:
          subkey: value
    """
    result: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        # 코멘트 / 빈 줄 건너뜀
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        # 최상위 키: 들여쓰기 없는 "key: value" 또는 "key:"
        if not line.startswith(" "):
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)', line)
            if not m:
                i += 1
                continue
            key   = m.group(1)
            value = m.group(2).strip()

            if not value or value == "|" or value == ">":
                # 다음 줄들이 리스트 또는 서브키인지 확인
                sub_items = []
                sub_dict  = {}
                j = i + 1
                while j < len(lines):
                    sub = lines[j]
                    if not sub.strip() or sub.strip().startswith("#"):
                        j += 1
                        continue
                    # 들여쓰기 있는 줄만 수집
                    if sub.startswith(" ") or sub.startswith("\t"):
                        inner = sub.strip()
                        if inner.startswith("- "):
                            # 리스트 아이템
                            item = inner[2:].strip().strip('"').strip("'")
                            sub_items.append(item)
                        elif ":" in inner:
                            # 서브키: 값
                            km = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)', inner)
                            if km:
                                sv = km.group(2).strip().strip('"').strip("'")
                                sv = None if sv in ("null", "~", "") else sv
                                try:
                                    sv = float(sv) if sv and '.' in sv else sv
                                    sv = int(sv) if isinstance(sv, str) and sv.lstrip('-').isdigit() else sv
                                except (ValueError, TypeError):
                                    pass
                                sub_dict[km.group(1)] = sv
                        j += 1
                    else:
                        break  # 들여쓰기 없는 줄 → 다음 최상위 키
                result[key] = sub_items if sub_items else (sub_dict if sub_dict else [])
                i = j
            else:
                # 인라인 값
                v = value.strip('"').strip("'")
                v = None if v in ("null", "~", "[]") else v
                if v == "[]":
                    v = []
                result[key] = v
                i += 1
        else:
            i += 1

    return result


def load_expected(yaml_path: Path) -> dict:
    """expected.yaml을 읽어 dict로 반환합니다."""
    text = yaml_path.read_text(encoding="utf-8")
    return _parse_simple_yaml(text)


# ── API 호출 ──────────────────────────────────────────────────────────────

def search_kb(query: str, top_k: int = DEFAULT_TOP_K, timeout: float = 15) -> list:
    """
    KB API POST /api/search 호출.
    반환: results 리스트 (각 항목은 dict, 최소 'title' 키 포함)
    """
    payload = {"query": query, "top_k": top_k}
    try:
        resp = requests.post(SEARCH_ENDPOINT, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.ConnectionError:
        print(f"  [ERROR] KB API에 연결할 수 없습니다: {SEARCH_ENDPOINT}")
        return []
    except requests.exceptions.Timeout:
        print(f"  [ERROR] KB API 응답 시간 초과")
        return []
    except Exception as e:
        print(f"  [ERROR] API 호출 실패: {e}")
        return []

    # 응답 구조: {"results": [...]} 또는 직접 리스트
    if isinstance(data, list):
        return data
    return data.get("results", [])


# ── 히트 판정 ─────────────────────────────────────────────────────────────

_SIM_V2_PATTERN = re.compile(r'sim_v2_(\d+)', re.IGNORECASE)
_SIMV2_ALT      = re.compile(r'sim_errors_v2.*?id[=_]?(\d+)', re.IGNORECASE)

def _result_text(result: dict) -> str:
    """결과 dict에서 매칭에 사용할 텍스트를 합성합니다."""
    parts = [
        result.get("title", ""),
        result.get("category", ""),
        result.get("cause", ""),
        result.get("solution", ""),
    ]
    return " ".join(str(p) for p in parts if p)


def is_hit(result: dict, expected: dict) -> bool:
    """
    단일 검색 결과가 expected 조건을 만족하는지 판정합니다.

    판정 기준 (OR):
      1. result title/text 에 expected_retrieved_ids 의 'sim_v2_NNN' 패턴이 포함
      2. hit_keywords 키워드 중 1개 이상이 result 텍스트에 포함
    """
    rtext = _result_text(result).lower()

    # 기준 1: expected_retrieved_ids 매칭
    expected_ids = expected.get("expected_retrieved_ids") or []
    if isinstance(expected_ids, str):
        expected_ids = [expected_ids]

    for eid in expected_ids:
        eid_lower = str(eid).lower()
        if eid_lower in rtext:
            return True
        # sim_v2_NNN 에서 숫자만 추출해 title 안에 있는지도 확인
        m = re.search(r'sim_v2_(\d+)', eid_lower)
        if m:
            num = m.group(1)
            # title이 숫자만으로 된 ID를 포함하는 패턴도 허용
            if re.search(rf'\bsim.*?{num}\b', rtext):
                return True

    # 기준 2: hit_keywords 매칭
    keywords = expected.get("hit_keywords") or []
    if isinstance(keywords, str):
        keywords = [keywords]

    for kw in keywords:
        kw = str(kw).strip().lower()
        if len(kw) < 3:
            continue
        if kw in rtext:
            return True

    return False


# ── 케이스 수집 ───────────────────────────────────────────────────────────

def collect_cases() -> list:
    """
    tests/kb_regression/case_*_input.md 파일을 수집하고
    대응하는 expected.yaml과 쌍을 맺어 반환합니다.
    """
    cases = []
    for input_path in sorted(HERE.glob("case_*_input.md")):
        stem = input_path.stem  # case_001_input
        base = stem.replace("_input", "")  # case_001
        expected_path = HERE / f"{base}_expected.yaml"
        if not expected_path.exists():
            print(f"  [WARN] expected 파일 없음: {expected_path.name} — 건너뜀")
            continue
        cases.append((input_path, expected_path))
    return cases


# ── 메인 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="KB 회귀 테스트 실행기")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="각 케이스의 상세 결과 출력")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K,
                        help=f"API 요청 top_k (기본값: {DEFAULT_TOP_K})")
    parser.add_argument("--delay", type=float, default=0.1,
                        help="케이스 간 요청 딜레이(초), 기본 0.1")
    parser.add_argument("--timeout", type=float, default=15,
                        help="API 요청 타임아웃(초), 기본 15")
    args = parser.parse_args()

    # ── 빠른 연결 확인 ────────────────────────────────────────────────────
    _api_reachable = False
    for _probe_url in [f"{KB_URL}/", f"{KB_URL}/api/health"]:
        try:
            _r = requests.get(_probe_url, timeout=3)
            print(f"KB 서버 연결 확인: {KB_URL}  (status {_r.status_code})")
            _api_reachable = True
            break
        except Exception:
            pass
    if not _api_reachable:
        print(f"[WARN] KB 서버({KB_URL})에 연결할 수 없습니다.")
        print(f"       서버가 실행 중인지 확인하세요.")
        print()

    cases = collect_cases()
    if not cases:
        print(f"케이스 파일이 없습니다. 먼저 gen_regression_cases.py를 실행하세요.")
        print(f"  python3 {HERE}/gen_regression_cases.py")
        sys.exit(1)

    print(f"KB 회귀 테스트 시작 — 총 {len(cases)}개 케이스  (top_k={args.top_k})")
    print(f"API 엔드포인트: {SEARCH_ENDPOINT}")
    print("=" * 60)

    top1_hits = 0
    top3_hits = 0
    total     = 0
    failed    = 0  # API 호출 실패

    results_log = []

    for input_path, expected_path in cases:
        total += 1
        case_name = input_path.stem.replace("_input", "")

        query   = input_path.read_text(encoding="utf-8")
        expected = load_expected(expected_path)

        if args.verbose:
            print(f"\n[{total}/{len(cases)}] {case_name}")
            print(f"  쿼리 길이: {len(query)}자")

        results = search_kb(query, top_k=args.top_k, timeout=args.timeout)

        if not results:
            failed += 1
            status = "FAIL(no results)"
            if args.verbose:
                print(f"  결과 없음 → {status}")
            results_log.append({
                "case": case_name,
                "top1_hit": False,
                "top3_hit": False,
                "status": status,
                "results": [],
            })
            if args.delay > 0:
                time.sleep(args.delay)
            continue

        # top-1 판정
        hit1 = is_hit(results[0], expected)
        # top-3 판정
        hit3 = any(is_hit(r, expected) for r in results[:3])

        if hit1:
            top1_hits += 1
        if hit3:
            top3_hits += 1

        status = ("TOP1-HIT" if hit1 else ("TOP3-HIT" if hit3 else "MISS"))

        if args.verbose:
            print(f"  상태: {status}")
            for idx, r in enumerate(results[:3]):
                marker = " ✓" if is_hit(r, expected) else ""
                print(f"  [{idx+1}] score={r.get('score','?'):.3f}  title={r.get('title','')[:60]}{marker}")

        elif total % 5 == 0 or total == len(cases):
            pct1 = top1_hits / total * 100
            pct3 = top3_hits / total * 100
            print(f"  진행: {total}/{len(cases)} | top-1: {pct1:.0f}%  top-3: {pct3:.0f}%")

        results_log.append({
            "case": case_name,
            "top1_hit": hit1,
            "top3_hit": hit3,
            "status": status,
            "results": [{"title": r.get("title",""), "score": r.get("score",0)} for r in results[:3]],
        })

        if args.delay > 0:
            time.sleep(args.delay)

    # ── 최종 요약 ────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("회귀 테스트 결과 요약")
    print("=" * 60)
    print(f"  총 케이스:   {total}")
    print(f"  API 실패:    {failed}")
    evaluated = total - failed
    if evaluated > 0:
        pct1 = top1_hits / evaluated * 100
        pct3 = top3_hits / evaluated * 100
        print(f"  top-1 hits:  {top1_hits}/{evaluated}  ({pct1:.1f}%)")
        print(f"  top-3 hits:  {top3_hits}/{evaluated}  ({pct3:.1f}%)")
        print()
        # 실패 케이스 목록
        misses = [r for r in results_log if r["status"] == "MISS"]
        if misses:
            print(f"  MISS 케이스 ({len(misses)}건):")
            for m in misses:
                print(f"    - {m['case']}")
    else:
        print("  평가 가능한 케이스 없음 (API 연결 실패?)")

    print("=" * 60)

    # JSON 로그 저장
    log_path = HERE / "regression_result_latest.json"
    log_data = {
        "total": total,
        "evaluated": evaluated,
        "failed_api": failed,
        "top1_hits": top1_hits,
        "top3_hits": top3_hits,
        "top1_hitrate": round(top1_hits / evaluated, 4) if evaluated else 0,
        "top3_hitrate": round(top3_hits / evaluated, 4) if evaluated else 0,
        "cases": results_log,
    }
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  결과 저장: {log_path}")

    # 성공 기준: top-3 hitrate >= 50%
    if evaluated > 0 and (top3_hits / evaluated) < 0.5:
        sys.exit(2)


if __name__ == "__main__":
    main()
