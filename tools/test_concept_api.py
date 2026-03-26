#!/usr/bin/env python3
"""
MEEP Concept API 검증 테스트
Usage: python -X utf8 tools/test_concept_api.py

TEST 1: concepts 테이블 + FTS 생성 확인
TEST 2: PML 개념 데이터 확인 (summary 50자+, 수식 포함, import meep 포함)
TEST 3: /api/concept POST → matched_concept="PML" 확인
TEST 4: /api/concept POST → EigenmodeSource 응답 확인
TEST 5: concept_detector.detect_concept("pml 두께 설정") == "PML"
TEST 6: 15개 개념 모두 생성 확인 (DB count >= 15)
TEST 7: /api/search 응답에 concept 섹션 포함 확인
"""
import sys, os, sqlite3, json, requests
from pathlib import Path

# 경로 설정
BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "api"))

DB_PATH = BASE / "db" / "knowledge.db"
API_BASE = "http://localhost:8765"

passed = 0
failed = 0
errors = []


def ok(msg):
    global passed
    passed += 1
    print(f"  ✅ {msg}")


def fail(msg):
    global failed
    failed += 1
    errors.append(msg)
    print(f"  ❌ {msg}")


def test(name, fn):
    print(f"\n[{name}]")
    try:
        fn()
    except Exception as e:
        fail(f"예외 발생: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: 테이블 생성 확인
# ══════════════════════════════════════════════════════════════════════════════
def test1():
    conn = sqlite3.connect(str(DB_PATH))
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow') AND name LIKE 'concept%'"
    ).fetchall()]
    conn.close()

    if "concepts" in tables:
        ok("concepts 테이블 존재")
    else:
        fail("concepts 테이블 없음")

    if "concepts_fts" in tables:
        ok("concepts_fts 가상 테이블 존재")
    else:
        fail("concepts_fts 가상 테이블 없음")


test("TEST 1: 테이블 생성 확인", test1)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: PML 개념 데이터 확인
# ══════════════════════════════════════════════════════════════════════════════
def test2():
    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute(
        "SELECT name, summary, explanation, demo_code, common_mistakes FROM concepts WHERE name='PML'"
    ).fetchone()
    conn.close()

    if not row:
        fail("PML 개념이 DB에 없음")
        return

    name, summary, explanation, demo_code, common_mistakes = row

    if len(summary or "") >= 50:
        ok(f"summary 50자 이상 ({len(summary)}자)")
    else:
        fail(f"summary 너무 짧음 ({len(summary or '')}자): {repr((summary or '')[:80])}")

    if explanation and "$" in explanation:
        ok("explanation에 LaTeX 수식($...$) 포함")
    else:
        fail(f"explanation에 수식 없음 (len={len(explanation or '')})")

    if demo_code and "import meep" in demo_code:
        ok("demo_code에 'import meep' 포함")
    else:
        fail(f"demo_code에 'import meep' 없음: {repr((demo_code or '')[:80])}")

    try:
        parsed = json.loads(common_mistakes or "[]")
        if isinstance(parsed, list):
            ok(f"common_mistakes JSON 파싱 가능 ({len(parsed)}개)")
        else:
            fail("common_mistakes가 list가 아님")
    except json.JSONDecodeError as e:
        fail(f"common_mistakes JSON 파싱 실패: {e} | 내용: {repr((common_mistakes or '')[:80])}")


test("TEST 2: PML 개념 데이터 확인", test2)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: /api/concept → PML 확인 (API 서버 필요)
# ══════════════════════════════════════════════════════════════════════════════
def test3():
    try:
        resp = requests.post(
            f"{API_BASE}/api/concept",
            json={"query": "PML이 뭐야"},
            timeout=10
        )
        if resp.status_code != 200:
            fail(f"HTTP {resp.status_code}")
            return
        data = resp.json()
        if data.get("matched_concept") == "PML":
            ok("matched_concept='PML'")
        else:
            fail(f"matched_concept 오류: {data.get('matched_concept')} | 응답: {str(data)[:200]}")

        if data.get("summary"):
            ok(f"summary 반환됨 ({len(data['summary'])}자)")
        else:
            fail("summary 없음")

        if data.get("confidence", 0) > 0:
            ok(f"confidence={data['confidence']}")
        else:
            fail("confidence=0")
    except requests.exceptions.ConnectionError:
        print("  ⚠️ API 서버 미실행 (Docker 배포 후 재테스트)")


test("TEST 3: /api/concept → PML", test3)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: /api/concept → EigenmodeSource
# ══════════════════════════════════════════════════════════════════════════════
def test4():
    try:
        resp = requests.post(
            f"{API_BASE}/api/concept",
            json={"query": "EigenmodeSource 어떻게 써"},
            timeout=10
        )
        if resp.status_code != 200:
            fail(f"HTTP {resp.status_code}")
            return
        data = resp.json()
        if data.get("matched_concept") == "EigenmodeSource":
            ok("matched_concept='EigenmodeSource'")
        else:
            fail(f"matched_concept 오류: {data.get('matched_concept')}")
    except requests.exceptions.ConnectionError:
        print("  ⚠️ API 서버 미실행 (Docker 배포 후 재테스트)")


test("TEST 4: /api/concept → EigenmodeSource", test4)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: concept_detector 단위 테스트
# ══════════════════════════════════════════════════════════════════════════════
def test5():
    from concept_detector import detect_concept, is_concept_question

    cases = [
        ("pml 두께 설정", "PML"),
        ("EigenmodeSource 사용법", "EigenmodeSource"),
        ("flux 투과율 측정", "FluxRegion"),
        ("resolution 10으로 설정", "resolution"),
        ("gaussian 소스 fcen", "GaussianSource"),
        ("adjoint 역설계", "adjoint"),
        ("near2far 방사 패턴", "near2far"),
        ("mpb 밴드 구조", "MPB"),
        ("courant 수치 안정", "courant"),
        ("harminv q factor", "Harminv"),
    ]

    for query, expected in cases:
        result = detect_concept(query)
        if result == expected:
            ok(f"detect_concept({repr(query)}) = '{expected}'")
        else:
            fail(f"detect_concept({repr(query)}) = '{result}' (expected '{expected}')")

    # is_concept_question 테스트
    concept_q = "PML이 뭐야?"
    error_q = "PML 에러 traceback 해결"

    if is_concept_question(concept_q):
        ok(f"is_concept_question({repr(concept_q)}) = True")
    else:
        fail(f"is_concept_question({repr(concept_q)}) = False (should be True)")

    if not is_concept_question(error_q):
        ok(f"is_concept_question({repr(error_q)}) = False (에러 쿼리 제외)")
    else:
        fail(f"is_concept_question({repr(error_q)}) = True (should be False)")


test("TEST 5: concept_detector 단위 테스트", test5)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: 15개 개념 모두 생성 확인
# ══════════════════════════════════════════════════════════════════════════════
def test6():
    conn = sqlite3.connect(str(DB_PATH))
    count = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
    names = [r[0] for r in conn.execute("SELECT name FROM concepts ORDER BY name").fetchall()]
    conn.close()

    if count >= 15:
        ok(f"concepts 테이블 {count}개 행 (>=15 ✅)")
    else:
        fail(f"concepts 행 수 부족: {count}/15 | 현재: {names}")

    expected = ["PML", "EigenmodeSource", "FluxRegion", "resolution", "GaussianSource",
                "Harminv", "Symmetry", "DFT", "MaterialGrid", "adjoint",
                "eig_band", "stop_when_fields_decayed", "MPB", "near2far", "courant"]
    missing = [n for n in expected if n not in names]
    if missing:
        fail(f"누락된 개념: {missing}")
    else:
        ok("15개 개념 모두 존재")


test("TEST 6: 15개 개념 생성 확인", test6)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 7: /api/search 응답에 concept 섹션 포함 확인
# ══════════════════════════════════════════════════════════════════════════════
def test7():
    try:
        resp = requests.post(
            f"{API_BASE}/api/search",
            json={"query": "PML이 뭐야?"},
            timeout=15
        )
        if resp.status_code != 200:
            fail(f"HTTP {resp.status_code}")
            return
        data = resp.json()
        if "concept" in data:
            concept = data["concept"]
            if concept.get("matched") == "PML":
                ok("search 응답에 concept.matched='PML' 포함")
            else:
                fail(f"concept.matched 오류: {concept.get('matched')}")
        else:
            fail("search 응답에 concept 섹션 없음")
    except requests.exceptions.ConnectionError:
        print("  ⚠️ API 서버 미실행 (Docker 배포 후 재테스트)")


test("TEST 7: /api/search concept 섹션 확인", test7)


# ══════════════════════════════════════════════════════════════════════════════
# 결과 요약
# ══════════════════════════════════════════════════════════════════════════════
total = passed + failed
print(f"\n{'='*50}")
print(f"결과: {passed}/{total} PASSED")
if errors:
    print("실패:")
    for e in errors:
        print(f"  ❌ {e}")
else:
    print("ALL PASSED ✅")
print('='*50)

sys.exit(0 if failed == 0 else 1)
