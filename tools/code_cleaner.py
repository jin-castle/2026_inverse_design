# -*- coding: utf-8 -*-
"""
code_cleaner.py — 마크다운/주피터 혼재 MEEP 코드 정제 도구

마크다운 텍스트가 혼재된 코드에서 실행 가능한 MEEP 코드를 추출하고
DB를 업데이트한다.

사용법:
  python -X utf8 tools/code_cleaner.py [--dry-run] [--id <id>]
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"


def clean_meep_code(raw_code: str) -> str | None:
    """
    마크다운/주피터 노트북 텍스트에서 실행 가능한 MEEP 코드 추출.

    처리 순서:
    1. ```python ... ``` 블록 추출 (있으면 우선)
    2. # [MD] 섹션 제거 (# [MD] 로 시작하는 블록 전체 제거)
    3. In [N]: ... 패턴 제거
    4. ## 헤더, ** bold ** 제거
    5. 빈 줄 정리
    6. import meep 포함 여부 확인 → 없으면 None 반환
    7. mp.Simulation 또는 meep.Simulation 포함 여부 확인
    """
    if not raw_code:
        return None

    code = raw_code

    # Step 1: ```python ... ``` 블록 추출 (있으면 우선)
    python_blocks = re.findall(r'```python\n(.*?)```', code, re.DOTALL)
    if python_blocks:
        # 여러 블록이 있으면 합치기
        combined = "\n\n".join(b.strip() for b in python_blocks)
        # 이 블록에 import meep이 있으면 반환
        if "import meep" in combined or "import mp" in combined:
            return combined.strip()

    # Step 2: # [MD] 섹션 제거
    # # [MD] 이후 # [MD] 전까지의 텍스트를 모두 제거
    # 패턴: # [MD]\n텍스트...\n\n (다음 # [MD] 또는 Python 코드 시작 전까지)
    # 먼저 # [MD]로 시작하는 코드를 처리
    if "# [MD]" in code:
        lines = code.split("\n")
        result_lines = []
        skip_mode = False
        i = 0
        while i < len(lines):
            line = lines[i]
            # # [MD] 태그 발견 → 마크다운 섹션 시작
            if line.strip() == "# [MD]":
                skip_mode = True
                i += 1
                continue
            # skip_mode 중이면
            if skip_mode:
                # 빈 줄 건너뜀
                if not line.strip():
                    i += 1
                    continue
                # Python 코드처럼 보이는 줄이면 skip 종료
                stripped = line.strip()
                is_python = (
                    stripped.startswith("import ") or
                    stripped.startswith("from ") or
                    stripped.startswith("def ") or
                    stripped.startswith("class ") or
                    stripped.startswith("#") or
                    stripped.startswith("if ") or
                    stripped.startswith("for ") or
                    stripped.startswith("with ") or
                    stripped.startswith("mp.") or
                    stripped.startswith("meep.") or
                    "=" in stripped and not stripped.startswith("-") and not stripped.startswith("*")
                )
                # 영문 산문 텍스트처럼 보이면 계속 스킵
                is_prose = (
                    len(stripped) > 20 and
                    not any(stripped.startswith(kw) for kw in [
                        "import", "from", "def", "class", "#", "if", "for",
                        "with", "mp.", "meep.", "plt.", "np."
                    ]) and
                    " " in stripped  # 단어 여러 개
                )
                if is_prose:
                    i += 1
                    continue
                else:
                    skip_mode = False
                    result_lines.append(line)
            else:
                result_lines.append(line)
            i += 1
        code = "\n".join(result_lines)

    # Step 3: Jupyter In [N]: 패턴 제거
    code = re.sub(r'^In \[\d+\]: ', '', code, flags=re.MULTILINE)
    code = re.sub(r'^\s*\.\.\.: ', '', code, flags=re.MULTILINE)
    # Out [N]: 출력 결과 제거
    code = re.sub(r'^Out\[\d+\]:.*$', '', code, flags=re.MULTILINE)

    # Step 4: 마크다운 헤더(## # 등), **bold** 제거
    # 헤더가 코드 주석처럼 들어온 경우 (# 으로 시작하는 마크다운)
    # 일반 ## 헤더 제거 (Python 주석 아닌 것)
    code = re.sub(r'^##+ .+$', '', code, flags=re.MULTILINE)
    # **bold** 제거
    code = re.sub(r'\*\*(.+?)\*\*', r'\1', code)
    # --- 구분선 제거
    code = re.sub(r'^---+$', '', code, flags=re.MULTILINE)

    # Step 5: 빈 줄 정리 (3개 이상 연속 빈 줄 → 2개로)
    code = re.sub(r'\n{3,}', '\n\n', code)
    code = code.strip()

    # Step 6: import meep 포함 여부 확인
    if "import meep" not in code and "import mp" not in code:
        return None

    # Step 7: mp.Simulation 또는 meep.Simulation 포함 여부 확인 (선택적)
    # 없더라도 meep 코드일 수 있으므로 None 반환하지 않음

    # 최소 길이 확인 (너무 짧으면 무의미)
    if len(code.strip()) < 50:
        return None

    return code


def ensure_raw_column(conn: sqlite3.Connection):
    """original_code_raw 컬럼이 없으면 추가"""
    cols = conn.execute("PRAGMA table_info(sim_errors_v2)").fetchall()
    col_names = [c[1] for c in cols]
    if "original_code_raw" not in col_names:
        conn.execute("ALTER TABLE sim_errors_v2 ADD COLUMN original_code_raw TEXT")
        conn.commit()
        print("  [DB] original_code_raw 컬럼 추가 완료")


def clean_and_update_db(dry_run: bool = False, target_id: int = None):
    """DB의 마크다운 혼재 코드를 정제하여 업데이트"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # 컬럼 확보
    if not dry_run:
        ensure_raw_column(conn)

    # 처리 대상: # [MD] 혼재 코드 (fix_worked=0)
    if target_id:
        rows = conn.execute(
            "SELECT id, original_code FROM sim_errors_v2 WHERE id=? AND fix_worked=0",
            (target_id,)
        ).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, original_code FROM sim_errors_v2
            WHERE fix_worked=0
              AND original_code IS NOT NULL
              AND original_code != ''
              AND (
                original_code LIKE '# [MD]%'
                OR original_code LIKE '%```python%'
                OR original_code LIKE '%In [%]%'
              )
            ORDER BY id
        """).fetchall()

    print(f"\n[code_cleaner] 정제 대상: {len(rows)}건")

    success_ids = []
    failed_ids = []

    for row in rows:
        vid = row["id"]
        raw_code = row["original_code"]
        cleaned = clean_meep_code(raw_code)

        if cleaned and cleaned != raw_code:
            print(f"  id={vid}: 정제 성공 ({len(raw_code)} → {len(cleaned)} chars)")
            if not dry_run:
                conn.execute(
                    "UPDATE sim_errors_v2 SET original_code_raw=?, original_code=? WHERE id=?",
                    (raw_code, cleaned, vid)
                )
            success_ids.append(vid)
        elif cleaned == raw_code:
            print(f"  id={vid}: 변경 없음 (이미 정제됨)")
            success_ids.append(vid)  # 이미 정제된 경우도 실행 가능
        else:
            print(f"  id={vid}: 정제 실패 (import meep 없거나 코드 없음)")
            failed_ids.append(vid)

    if not dry_run:
        conn.commit()
        print(f"\n  DB 업데이트 완료: {len(success_ids)}건")

    conn.close()

    print(f"\n[code_cleaner] 결과:")
    print(f"  성공: {len(success_ids)}건 {success_ids}")
    print(f"  실패: {len(failed_ids)}건 {failed_ids}")

    return success_ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="DB 수정 없이 테스트")
    parser.add_argument("--id", type=int, help="특정 ID만 처리")
    args = parser.parse_args()

    print(f"[code_cleaner] {'DRY RUN' if args.dry_run else '실행'} 모드")
    success_ids = clean_and_update_db(dry_run=args.dry_run, target_id=args.id)
    print(f"\n정제 성공 IDs (verified_fix_v2 재실행 대상): {success_ids}")
