#!/usr/bin/env python3
"""
gen_regression_cases.py
-----------------------
sim_errors_v2 테이블의 fix_worked=1 상위 20건을 읽어
회귀 테스트 케이스 파일 쌍을 생성합니다.

  case_{id:03d}_input.md     -- 사용자 질문 형식의 자연어 텍스트
  case_{id:03d}_expected.yaml -- 정답 검색 ID / 기준

Usage:
    python3 tests/kb_regression/gen_regression_cases.py
"""

import sqlite3, json, textwrap, re
from pathlib import Path

# ── 경로 설정 ─────────────────────────────────────────────────────────────
HERE    = Path(__file__).parent                   # tests/kb_regression/
DB_PATH = Path(__file__).parents[2] / "db" / "knowledge.db"

# ── 자연어 질문 생성 함수 ─────────────────────────────────────────────────

def _clean(text: str) -> str:
    """None / 빈 문자열 처리 + JSON 배열 / 딕셔너리 제거."""
    if not text:
        return ""
    text = str(text).strip()
    # JSON list/dict 패턴이면 첫 번째 'pattern' 값만 추출 시도
    if text.startswith("[{") or text.startswith("{"):
        try:
            obj = json.loads(text)
            if isinstance(obj, list) and obj:
                first = obj[0]
                return first.get("pattern") or first.get("cause") or str(first)[:200]
            if isinstance(obj, dict):
                return obj.get("pattern") or obj.get("cause") or str(obj)[:200]
        except Exception:
            pass
        # JSON 파싱 실패 → 처음 200자
        return text[:200]
    return text


def _build_input_md(row: dict) -> str:
    """
    사용자가 실제로 할 법한 에러 호소 텍스트를 생성합니다.
    error_type / error_message / symptom_* 필드를 조합합니다.
    """
    etype   = _clean(row["error_type"])
    emsg    = _clean(row["error_message"])
    sym     = _clean(row["symptom"])
    sym_num = _clean(row["symptom_numerical"])
    sym_beh = _clean(row["symptom_behavioral"])
    sym_pat = _clean(row["symptom_error_pattern"])

    lines = []

    # 제목 줄
    if etype and etype.lower() not in ("unknown", "numericalerror", ""):
        lines.append(f"# MEEP 시뮬레이션 오류: {etype}")
    else:
        lines.append("# MEEP 시뮬레이션 문제 문의")

    lines.append("")

    # 에러 메시지 블록
    if emsg:
        lines.append("아래 오류가 발생했습니다:")
        lines.append("")
        lines.append("```")
        lines.append(emsg[:500])
        lines.append("```")
        lines.append("")

    # 증상 서술
    if sym:
        lines.append(f"증상: {sym}")
        lines.append("")

    if sym_num:
        lines.append(f"수치적 증상: {sym_num}")
        lines.append("")

    if sym_beh:
        lines.append(f"동작 증상: {sym_beh}")
        lines.append("")

    if sym_pat:
        lines.append("오류 패턴:")
        lines.append("```")
        lines.append(sym_pat[:300])
        lines.append("```")
        lines.append("")

    # 아무 증상도 없으면 기본 문구
    if not any([emsg, sym, sym_num, sym_beh, sym_pat]):
        lines.append("MEEP 시뮬레이션을 실행하다가 예상치 못한 오류가 발생했습니다.")
        lines.append("어떻게 해결할 수 있을까요?")
        lines.append("")

    # 맺음말
    lines.append("이 문제의 원인과 해결 방법을 알려주세요.")

    return "\n".join(lines)


def _build_expected_yaml(row: dict) -> str:
    """case_{id:03d}_expected.yaml 내용을 생성합니다."""
    rid = row["id"]

    # verification_criteria JSON 파싱
    vc_raw = row["verification_criteria"] or ""
    try:
        vc_obj = json.loads(vc_raw) if vc_raw.strip().startswith("{") else {}
    except Exception:
        vc_obj = {}

    # YAML 직렬화 (pyyaml 없이 수동 작성)
    def _yaml_str(v):
        if v is None:
            return "null"
        s = str(v).replace('"', '\\"')
        return f'"{s}"'

    vc_lines = []
    for k, v in vc_obj.items():
        vc_lines.append(f"  {k}: {_yaml_str(v)}")
    vc_block = "\n".join(vc_lines) if vc_lines else "  # (검증 기준 없음)"

    emsg_safe = _clean(row["error_message"])[:120].replace('"', '\\"')
    etype_safe = _clean(row["error_type"]).replace('"', '\\"')

    content = f"""\
# 회귀 테스트 정답 파일 — sim_errors_v2 id={rid}
# 자동 생성: gen_regression_cases.py

# 검색 결과에 반드시 포함되어야 할 KB 항목 ID
expected_retrieved_ids:
  - "sim_v2_{rid}"

# 검색 결과에 절대 나와서는 안 될 항목 (현재 비어있음)
must_not_retrieve: []

# 위 ID 외에 나와도 괜찮은 관련 항목 (추가 허용)
acceptable_also: []

# 히트 판정에 사용할 키워드 (error_message / error_type 에서 추출)
hit_keywords:
  - "{etype_safe}"
  - "{emsg_safe}"

# DB에서 복사한 검증 기준 (verification_criteria)
verification_criteria:
{vc_block}
"""
    return content


# ── 메인 ──────────────────────────────────────────────────────────────────

def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB를 찾을 수 없습니다: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT id, error_type, error_message, symptom,
               symptom_numerical, symptom_behavioral, symptom_error_pattern,
               verification_criteria
        FROM sim_errors_v2
        WHERE fix_worked = 1
        ORDER BY id
        LIMIT 20
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    print(f"추출된 케이스 수: {len(rows)}")

    generated = []
    for row in rows:
        rid = row["id"]
        prefix = f"case_{rid:03d}"

        input_path    = HERE / f"{prefix}_input.md"
        expected_path = HERE / f"{prefix}_expected.yaml"

        input_md    = _build_input_md(row)
        expected_yaml = _build_expected_yaml(row)

        input_path.write_text(input_md,    encoding="utf-8")
        expected_path.write_text(expected_yaml, encoding="utf-8")
        generated.append(rid)
        print(f"  [OK] {prefix}_input.md  +  {prefix}_expected.yaml")

    # README 작성
    _write_readme(generated)
    print(f"\n총 {len(generated)}개 케이스 생성 완료.")
    print(f"위치: {HERE}")


def _write_readme(ids: list):
    id_list = "\n".join(f"- case_{i:03d}_input.md / case_{i:03d}_expected.yaml" for i in ids)
    readme = f"""\
# KB Regression Test Cases

## 개요

`gen_regression_cases.py`가 `sim_errors_v2` 테이블(fix_worked=1, 상위 20건)에서
자동 생성한 회귀 테스트 케이스 파일들입니다.

## 파일 구조

각 케이스는 두 파일로 구성됩니다:

| 파일 | 설명 |
|------|------|
| `case_NNN_input.md`    | 사용자가 실제로 할 법한 에러 호소 텍스트 (검색 쿼리로 사용) |
| `case_NNN_expected.yaml` | 예상 검색 결과 ID, 금지 ID, 허용 추가 ID, 검증 기준 |

## 생성된 케이스 목록

{id_list}

## 회귀 테스트 실행

```bash
python3 tests/kb_regression/run_regression.py
python3 tests/kb_regression/run_regression.py --verbose
```

## 결과 해석

- **top-1 hit rate**: 검색 결과 1위가 정답인 비율
- **top-3 hit rate**: 상위 3개 결과 안에 정답이 포함된 비율

hit 판정 조건:
1. 결과 title에 `sim_v2_{{id}}` 패턴이 포함되거나
2. 결과 title/category에 `hit_keywords` 키워드가 매칭될 때

## 파일 재생성

```bash
python3 tests/kb_regression/gen_regression_cases.py
```

DB 변경 후 재실행하면 케이스 파일들이 갱신됩니다.
"""
    readme_path = HERE / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    print(f"  [OK] README.md 작성 완료")


if __name__ == "__main__":
    main()
