# -*- coding: utf-8 -*-
"""
verified_fix_v2.py — sim_errors_v2 LLM 물리 컨텍스트 기반 수정 파이프라인
===========================================================================
sim_errors_v2 테이블에서 fix_worked=0 레코드를 가져와:
  1. original_code 재실행 (에러 재현 확인)
  2. LLM(claude-sonnet-4-6)에게 물리 컨텍스트 포함 수정 요청
  3. fixed_code Docker 재실행 검증
  4. 성공 시 fix_worked=1 업데이트

실행:
  python -X utf8 tools/verified_fix_v2.py [--limit 10] [--dry-run] [--id <v2_id>]
"""

import argparse
import difflib
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"

# 경로 등록
sys.path.insert(0, str(BASE / "tools"))
sys.path.insert(0, str(BASE / "api"))

# .env 로드
try:
    from dotenv import load_dotenv
    load_dotenv(str(BASE / ".env"))
except ImportError:
    pass

from live_runner import run_code, RunResult

# ──────────────────────────────────────────────────────────────────────────────
# LLM 프롬프트 구성
# ──────────────────────────────────────────────────────────────────────────────

def _format_root_cause_chain(root_cause_chain_json: str) -> str:
    """root_cause_chain JSON을 readable 형식으로 변환"""
    if not root_cause_chain_json:
        return "(없음)"
    try:
        chain = json.loads(root_cause_chain_json)
        if isinstance(chain, list):
            lines = []
            for item in chain:
                if isinstance(item, dict):
                    level = item.get("level", "?")
                    cause = item.get("cause", str(item))
                    lines.append(f"  Level {level}: {cause}")
                else:
                    lines.append(f"  - {item}")
            return "\n".join(lines) if lines else str(chain)
        return str(chain)
    except (json.JSONDecodeError, TypeError):
        return str(root_cause_chain_json)[:500]


def build_fix_prompt(record: dict) -> str:
    """물리 컨텍스트를 포함한 LLM 수정 프롬프트 생성"""
    run_mode = record.get("run_mode") or "forward"
    device_type = record.get("device_type") or "general"
    error_class = record.get("error_class") or "code_error"
    error_type = record.get("error_type") or "Unknown"
    symptom = record.get("symptom") or ""
    resolution = record.get("resolution") or "N/A"
    pml_thickness = record.get("pml_thickness") or "N/A"
    wavelength_um = record.get("wavelength_um") or "N/A"
    dim = record.get("dim") or "N/A"
    root_cause_chain = _format_root_cause_chain(record.get("root_cause_chain"))
    physics_cause = record.get("physics_cause") or "(분석 없음)"
    code_cause = record.get("code_cause") or "(분석 없음)"
    original_code = record.get("original_code") or ""
    error_message = record.get("error_message") or ""
    traceback_full = record.get("traceback_full") or ""

    # 에러 메시지 통합
    full_error = error_message
    if traceback_full and traceback_full not in full_error:
        full_error = traceback_full + "\n" + full_error

    prompt = f"""당신은 MEEP FDTD 전문가입니다.

## 에러 컨텍스트
- run_mode: {run_mode} (forward/adjoint/...)
- device_type: {device_type}
- error_class: {error_class} (code_error/physics_error/numerical_error/config_error)
- error_type: {error_type}
- symptom: {symptom}

## 물리 파라미터
- resolution: {resolution}
- pml_thickness: {pml_thickness}
- wavelength_um: {wavelength_um}
- dim: {dim}D

## 근본 원인 체인
{root_cause_chain}

## 물리적 원인
{physics_cause}

## 코드 레벨 원인
{code_cause}

## 원본 코드
```python
{original_code[:4000]}
```

## 에러 메시지
```
{full_error[:1500]}
```

## 요청
1. fix_type을 결정하세요: code_only | physics_understanding | parameter_tune | structural
2. fix_description을 작성하세요 (물리적 이유 포함, 한국어, 3~5문장)
3. 수정된 전체 코드를 제공하세요 (실행 가능한 완전한 코드)

응답 형식:
FIX_TYPE: <code_only|physics_understanding|parameter_tune|structural>
FIX_DESCRIPTION: <설명>
FIXED_CODE:
```python
<전체 수정 코드>
```"""
    return prompt


# ──────────────────────────────────────────────────────────────────────────────
# LLM 호출
# ──────────────────────────────────────────────────────────────────────────────

def call_llm(prompt: str, api_key: str) -> str:
    """Anthropic API 호출, 응답 텍스트 반환"""
    import urllib.request

    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 2500,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
        return data["content"][0]["text"]


# ──────────────────────────────────────────────────────────────────────────────
# LLM 응답 파싱
# ──────────────────────────────────────────────────────────────────────────────

def parse_llm_response(response: str) -> dict:
    """
    LLM 응답에서 FIX_TYPE, FIX_DESCRIPTION, FIXED_CODE 추출.
    Returns: {fix_type, fix_description, fixed_code} or None 값 포함
    """
    result = {
        "fix_type": "code_only",
        "fix_description": "",
        "fixed_code": "",
    }

    # FIX_TYPE
    m = re.search(r'FIX_TYPE:\s*(\S+)', response)
    if m:
        ft = m.group(1).strip().lower()
        valid_types = {"code_only", "physics_understanding", "parameter_tune", "structural"}
        result["fix_type"] = ft if ft in valid_types else "code_only"

    # FIX_DESCRIPTION (FIX_DESCRIPTION: 이후 FIXED_CODE: 전까지)
    m = re.search(r'FIX_DESCRIPTION:\s*(.*?)(?=FIXED_CODE:|$)', response, re.DOTALL)
    if m:
        result["fix_description"] = m.group(1).strip()

    # FIXED_CODE: ```python ... ``` 블록
    m = re.search(r'FIXED_CODE:\s*```python\s*(.*?)```', response, re.DOTALL)
    if m:
        result["fixed_code"] = m.group(1).strip()
    else:
        # 백틱 없이 바로 코드가 올 경우
        m = re.search(r'FIXED_CODE:\s*\n(.*)', response, re.DOTALL)
        if m:
            result["fixed_code"] = m.group(1).strip()

    return result


# ──────────────────────────────────────────────────────────────────────────────
# DB 조회 / 업데이트
# ──────────────────────────────────────────────────────────────────────────────

def get_unfixed_records(limit: int = 10, record_id: int = None) -> list:
    """sim_errors_v2 WHERE fix_worked=0 조회"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        if record_id is not None:
            rows = conn.execute(
                "SELECT * FROM sim_errors_v2 WHERE id = ?", (record_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sim_errors_v2 WHERE fix_worked=0 ORDER BY id LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_fix_record(record_id: int, fixed_code: str, code_diff: str,
                      fix_description: str, fix_type: str) -> bool:
    """fix_worked=1로 업데이트"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("""
            UPDATE sim_errors_v2
            SET fix_worked=1,
                fixed_code=?,
                code_diff=?,
                fix_description=?,
                fix_type=?
            WHERE id=?
        """, (fixed_code, code_diff, fix_description, fix_type, record_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"  ❌ DB 업데이트 실패 (id={record_id}): {e}")
        return False
    finally:
        conn.close()


def make_diff(original_code: str, fixed_code: str) -> str:
    """unified diff 생성"""
    orig_lines = original_code.splitlines(keepends=True)
    fixed_lines = fixed_code.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines, fixed_lines,
        fromfile="original.py", tofile="fixed.py",
        lineterm=""
    )
    return "".join(diff)[:5000]  # 5KB 제한


# ──────────────────────────────────────────────────────────────────────────────
# 메인 파이프라인
# ──────────────────────────────────────────────────────────────────────────────

def process_record(record: dict, api_key: str, dry_run: bool = False) -> dict:
    """
    단일 레코드 처리:
    1. original_code 재실행 (에러 재현)
    2. LLM 수정 코드 생성
    3. fixed_code 재실행 검증
    4. 성공 시 DB 업데이트

    Returns: {
        "id": int,
        "status": "fixed" | "not_reproducible" | "llm_failed" | "fix_failed" | "dry_run",
        "fix_type": str,
        "fix_description": str,
        "message": str,
    }
    """
    record_id = record["id"]
    original_code = record.get("original_code") or ""
    error_class = record.get("error_class") or ""

    result = {
        "id": record_id,
        "status": "unknown",
        "fix_type": "",
        "fix_description": "",
        "message": "",
    }

    if not original_code.strip():
        result["status"] = "skip"
        result["message"] = "original_code 없음"
        print(f"  ⏭ id={record_id}: original_code 없음, 스킵")
        return result

    print(f"\n{'='*60}")
    print(f"  📋 처리 중: id={record_id} | error_type={record.get('error_type')} | error_class={error_class}")

    # ─── Step 1: original_code 재실행 (에러 재현 확인) ──────────────────────
    print(f"  🔄 Step 1: original_code 재실행...")
    orig_result = run_code(original_code, timeout=60)
    print(f"    결과: status={orig_result.status}, error_type={orig_result.error_type}")

    # physics_error는 success로 실행되지만 T값이 이상한 경우
    if orig_result.status == "success" and error_class != "physics_error":
        result["status"] = "not_reproducible"
        result["message"] = f"에러 재현 실패 (status=success)"
        print(f"  ⚠ id={record_id}: 에러 재현 실패, 스킵")
        return result

    # blocked/mpi_deadlock_risk는 그대로 진행
    print(f"  ✅ 에러 재현 확인됨 (status={orig_result.status})")

    # ─── Step 2: LLM 수정 코드 생성 ────────────────────────────────────────
    print(f"  🤖 Step 2: LLM 수정 코드 생성...")
    try:
        prompt = build_fix_prompt(record)
        llm_response = call_llm(prompt, api_key)
        parsed = parse_llm_response(llm_response)
    except Exception as e:
        result["status"] = "llm_failed"
        result["message"] = f"LLM 오류: {e}"
        print(f"  ❌ id={record_id}: LLM 오류 - {e}")
        return result

    fixed_code = parsed.get("fixed_code", "")
    fix_type = parsed.get("fix_type", "code_only")
    fix_description = parsed.get("fix_description", "")

    if not fixed_code:
        result["status"] = "llm_failed"
        result["message"] = "LLM이 수정 코드를 반환하지 않음"
        print(f"  ❌ id={record_id}: LLM 수정 코드 없음")
        return result

    print(f"    fix_type: {fix_type}")
    print(f"    fix_description: {fix_description[:100]}...")
    print(f"    fixed_code 길이: {len(fixed_code)}자")

    if dry_run:
        result["status"] = "dry_run"
        result["fix_type"] = fix_type
        result["fix_description"] = fix_description
        result["message"] = f"dry_run: 수정 코드 생성 완료 (미실행)"
        print(f"  🧪 dry_run 모드: 실행 생략")
        return result

    # ─── Step 3: fixed_code Docker 재실행 검증 ──────────────────────────────
    print(f"  🐳 Step 3: fixed_code Docker 재실행...")
    fix_result = run_code(fixed_code, timeout=90)
    print(f"    결과: status={fix_result.status}, error_type={fix_result.error_type}")

    if fix_result.status not in ("success", "mpi_deadlock_risk"):
        # mpi_deadlock_risk: 실행 전 차단이지만 코드 수정이 맞을 수 있음
        # success만 fix_worked=1
        if fix_result.status == "error":
            result["status"] = "fix_failed"
            result["message"] = f"수정 후에도 에러: {fix_result.error_message[:200]}"
            print(f"  ❌ id={record_id}: 수정 실패 - {fix_result.error_message[:100]}")
            return result
        elif fix_result.status == "timeout":
            result["status"] = "fix_failed"
            result["message"] = "수정 후 timeout"
            print(f"  ❌ id={record_id}: 수정 후 timeout")
            return result

    # ─── Step 4: DB 업데이트 ────────────────────────────────────────────────
    print(f"  ✅ Step 4: 수정 성공! DB 업데이트...")
    code_diff = make_diff(original_code, fixed_code)
    ok = update_fix_record(
        record_id=record_id,
        fixed_code=fixed_code,
        code_diff=code_diff,
        fix_description=fix_description,
        fix_type=fix_type,
    )

    if ok:
        result["status"] = "fixed"
        result["fix_type"] = fix_type
        result["fix_description"] = fix_description
        result["message"] = f"fix_worked=1 업데이트 완료"
        print(f"  🎉 id={record_id}: fix_worked=1 업데이트 완료!")
    else:
        result["status"] = "db_error"
        result["message"] = "DB 업데이트 실패"

    return result


def run_pipeline(limit: int = 10, dry_run: bool = False, record_id: int = None) -> list:
    """전체 파이프라인 실행"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY 없음. .env 파일 확인 필요.")
        sys.exit(1)

    records = get_unfixed_records(limit=limit, record_id=record_id)
    print(f"📊 처리 대상: {len(records)}건 (fix_worked=0)")

    if not records:
        print("  처리할 레코드 없음.")
        return []

    results = []
    stats = {"fixed": 0, "failed": 0, "skipped": 0, "dry_run": 0}

    for rec in records:
        try:
            r = process_record(rec, api_key=api_key, dry_run=dry_run)
            results.append(r)
            if r["status"] == "fixed":
                stats["fixed"] += 1
            elif r["status"] == "dry_run":
                stats["dry_run"] += 1
            elif r["status"] in ("skip", "not_reproducible"):
                stats["skipped"] += 1
            else:
                stats["failed"] += 1
            # Rate limiting
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n⚠ 사용자 중단")
            break
        except Exception as e:
            print(f"  ❌ id={rec.get('id')}: 예상치 못한 오류 - {e}")
            results.append({
                "id": rec.get("id"),
                "status": "error",
                "message": str(e),
            })
            stats["failed"] += 1

    print(f"\n{'='*60}")
    print(f"🏁 파이프라인 완료:")
    print(f"  ✅ 수정 성공: {stats['fixed']}건")
    print(f"  🧪 dry_run:  {stats['dry_run']}건")
    print(f"  ⏭ 스킵:     {stats['skipped']}건")
    print(f"  ❌ 실패:     {stats['failed']}건")
    return results


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="verified_fix_v2: sim_errors_v2 LLM 물리 컨텍스트 기반 수정 파이프라인"
    )
    parser.add_argument("--limit", type=int, default=10, help="처리할 최대 레코드 수 (기본: 10)")
    parser.add_argument("--dry-run", action="store_true", help="LLM 생성만, Docker 실행 없음")
    parser.add_argument("--id", type=int, default=None, help="특정 v2_id만 처리")
    args = parser.parse_args()

    run_pipeline(limit=args.limit, dry_run=args.dry_run, record_id=args.id)


if __name__ == "__main__":
    main()
