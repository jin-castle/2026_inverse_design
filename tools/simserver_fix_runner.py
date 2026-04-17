# -*- coding: utf-8 -*-
"""
simserver_fix_runner.py — SimServer MPI 기반 Timeout fix 처리기
================================================================
Timeout fix_worked=0 레코드 중 5000자 미만(완전한 코드)에 대해:
  1. LLM(claude-sonnet-4-6)으로 수정 코드 생성
  2. SimServer에 전송: mpirun -np 128 python /tmp/fix_N.py (timeout 1200s)
  3. 성공 시 DB 업데이트 fix_worked=1
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import difflib
import tempfile
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"

# .env 로드
try:
    from dotenv import load_dotenv
    load_dotenv(str(BASE / ".env"))
except ImportError:
    pass

SIMSERVER_HOST = "user@166.104.35.108"
SIMSERVER_SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")
MPI_NP = 128
TIMEOUT_SEC = 1200  # 20분

# 처리 대상 IDs (code_len < 5000, 완전한 코드)
TARGET_IDS = [32, 56, 63, 73, 84, 85, 90, 104, 105]


def call_llm(prompt: str, api_key: str) -> str:
    import urllib.request
    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 8000,
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
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
        return data["content"][0]["text"]


def build_fix_prompt(record: dict) -> str:
    original_code = record.get("original_code") or ""
    error_message = record.get("error_message") or ""
    traceback_full = record.get("traceback_full") or ""
    error_type = record.get("error_type") or "Timeout"
    physics_cause = record.get("physics_cause") or "(없음)"
    code_cause = record.get("code_cause") or "(없음)"
    resolution = record.get("resolution") or "N/A"
    pml_thickness = record.get("pml_thickness") or "N/A"
    wavelength_um = record.get("wavelength_um") or "N/A"
    dim = record.get("dim") or "N/A"
    device_type = record.get("device_type") or "unknown"

    full_error = traceback_full + "\n" + error_message if traceback_full else error_message

    return f"""You are a MEEP FDTD simulation expert.

## Problem: Simulation Timeout
The following MEEP simulation code timed out during execution.
It needs to be fixed to run within a reasonable time limit.

## Simulation Parameters
- device_type: {device_type}
- resolution: {resolution}
- pml_thickness: {pml_thickness}
- wavelength_um: {wavelength_um}
- dimension: {dim}D
- error_type: {error_type}

## Physics Cause Analysis
{physics_cause}

## Code Cause Analysis
{code_cause}

## Error Message
```
{full_error[:1000]}
```

## Original Code
```python
{original_code}
```

## Task
Fix the code to prevent timeout. Common strategies:
1. Reduce `resolution` (e.g., from 50 to 20-30)
2. Reduce simulation time (until parameter) or add early stopping
3. Reduce cell size / domain
4. Remove unnecessary flux monitors or output steps
5. Fix infinite loops or very large arrays

The fixed code must:
- Be complete and runnable with: mpirun -np 128 python fix.py
- Not use matplotlib.show() or interactive displays
- Complete within 20 minutes
- Be a valid Python file (no markdown, no explanations inside the code)

FIX_TYPE: <code_only|parameter_tune|structural>
FIX_DESCRIPTION: <Korean description, 3-5 sentences explaining what was changed and why>
FIXED_CODE:
```python
<complete fixed Python code>
```"""


def parse_llm_response(response: str) -> dict:
    result = {"fix_type": "code_only", "fix_description": "", "fixed_code": ""}
    
    m = re.search(r'FIX_TYPE:\s*(\S+)', response)
    if m:
        ft = m.group(1).strip().lower()
        valid = {"code_only", "parameter_tune", "structural"}
        result["fix_type"] = ft if ft in valid else "code_only"
    
    m = re.search(r'FIX_DESCRIPTION:\s*(.*?)(?=FIXED_CODE:|$)', response, re.DOTALL)
    if m:
        result["fix_description"] = m.group(1).strip()
    
    m = re.search(r'FIXED_CODE:\s*```python\s*(.*?)```', response, re.DOTALL)
    if m:
        result["fixed_code"] = m.group(1).strip()
    else:
        m = re.search(r'FIXED_CODE:\s*\n(.*)', response, re.DOTALL)
        if m:
            result["fixed_code"] = m.group(1).strip()
    
    return result


def send_and_run_on_simserver(fixed_code: str, record_id: int) -> dict:
    """SimServer에 코드 전송 후 mpirun -np 128으로 실행"""
    remote_path = f"/tmp/fix_{record_id}.py"
    
    # 1. SCP로 코드 전송
    local_tmp = Path(tempfile.mktemp(suffix=".py"))
    local_tmp.write_text(fixed_code, encoding="utf-8")
    
    scp_result = subprocess.run(
        ["scp", "-i", SIMSERVER_SSH_KEY, "-o", "StrictHostKeyChecking=no",
         str(local_tmp), f"{SIMSERVER_HOST}:{remote_path}"],
        capture_output=True, text=True, timeout=30
    )
    local_tmp.unlink(missing_ok=True)
    
    if scp_result.returncode != 0:
        return {
            "status": "scp_failed",
            "message": f"SCP 실패: {scp_result.stderr[:200]}"
        }
    
    print(f"  📤 코드 전송 완료: {remote_path}")
    
    # 2. SSH로 실행
    run_cmd = (
        f"source ~/anaconda3/etc/profile.d/conda.sh && "
        f"conda activate pmp && "
        f"timeout {TIMEOUT_SEC} mpirun -np {MPI_NP} python {remote_path} 2>&1; "
        f"echo EXIT_CODE:$?"
    )
    
    print(f"  🚀 SimServer 실행 시작 (timeout={TIMEOUT_SEC}s)...")
    start_time = time.time()
    
    ssh_result = subprocess.run(
        ["ssh", "-i", SIMSERVER_SSH_KEY, "-o", "StrictHostKeyChecking=no",
         SIMSERVER_HOST, run_cmd],
        capture_output=True, text=True, timeout=TIMEOUT_SEC + 60
    )
    
    elapsed = time.time() - start_time
    output = ssh_result.stdout + ssh_result.stderr
    
    # EXIT_CODE 파싱
    exit_code_match = re.search(r'EXIT_CODE:(\d+)', output)
    exit_code = int(exit_code_match.group(1)) if exit_code_match else ssh_result.returncode
    
    print(f"  ⏱ 실행 시간: {elapsed:.1f}s | exit_code={exit_code}")
    print(f"  📄 출력 (마지막 500자):\n{output[-500:]}")
    
    # 성공 판단
    # exit 15 = MPI BAD TERMINATION (이전 문제)
    # exit 124 = timeout에 의해 종료
    # exit 0 = 정상 종료
    if exit_code == 0:
        return {"status": "success", "elapsed": elapsed, "output": output[-1000:]}
    elif exit_code == 124:
        return {"status": "timeout", "elapsed": elapsed, "output": output[-500:],
                "message": f"timeout ({TIMEOUT_SEC}s 초과)"}
    elif exit_code == 15:
        return {"status": "mpi_exit15", "elapsed": elapsed, "output": output[-500:],
                "message": "MPI BAD TERMINATION exit 15"}
    else:
        # 에러 출력에 'Traceback' 또는 'Error' 있으면 실패
        if "Traceback" in output or "Error" in output or "error" in output.lower():
            return {"status": "error", "elapsed": elapsed, "output": output[-500:],
                    "message": f"실행 오류 (exit={exit_code})"}
        # 출력이 있고 exit code가 0이 아니어도 시뮬레이션 완료로 볼 수 있음
        # MEEP는 종종 non-zero exit를 반환하기도 함
        return {"status": "error", "elapsed": elapsed, "output": output[-500:],
                "message": f"exit_code={exit_code}"}


def make_diff(orig: str, fixed: str) -> str:
    orig_lines = orig.splitlines(keepends=True)
    fixed_lines = fixed.splitlines(keepends=True)
    diff = difflib.unified_diff(orig_lines, fixed_lines,
                                fromfile="original.py", tofile="fixed.py", lineterm="")
    return "".join(diff)[:5000]


def update_db(record_id: int, fixed_code: str, code_diff: str,
              fix_description: str, fix_type: str) -> bool:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("""
            UPDATE sim_errors_v2
            SET fix_worked=1, fixed_code=?, code_diff=?, fix_description=?, fix_type=?
            WHERE id=?
        """, (fixed_code, code_diff, fix_description, fix_type, record_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"  ❌ DB 업데이트 실패: {e}")
        return False
    finally:
        conn.close()


def get_records(ids: list) -> list:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM sim_errors_v2 WHERE id IN ({placeholders}) ORDER BY id",
            ids
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY 없음")
        sys.exit(1)
    
    print(f"🎯 처리 대상 IDs: {TARGET_IDS}")
    records = get_records(TARGET_IDS)
    print(f"📊 DB 조회: {len(records)}건")
    
    stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}
    results = []
    
    for rec in records:
        rid = rec["id"]
        original_code = rec.get("original_code") or ""
        
        # 이미 fix_worked=1인지 확인
        if rec.get("fix_worked") == 1:
            print(f"\n⏭ ID={rid}: 이미 fix_worked=1, 스킵")
            stats["skipped"] += 1
            results.append({"id": rid, "status": "already_fixed"})
            continue
        
        # 코드 잘림 확인 (5000자)
        if len(original_code) >= 5000:
            print(f"\n⏭ ID={rid}: 코드 잘림(len={len(original_code)}), 스킵")
            stats["skipped"] += 1
            results.append({"id": rid, "status": "truncated"})
            continue
        
        stats["total"] += 1
        print(f"\n{'='*60}")
        print(f"🔧 처리 중: ID={rid} | error_type={rec.get('error_type')} | code_len={len(original_code)}")
        
        # Step 1: LLM으로 수정 코드 생성
        print(f"  🤖 LLM 수정 코드 생성...")
        try:
            prompt = build_fix_prompt(rec)
            llm_response = call_llm(prompt, api_key)
            parsed = parse_llm_response(llm_response)
        except Exception as e:
            print(f"  ❌ LLM 오류: {e}")
            stats["failed"] += 1
            results.append({"id": rid, "status": "llm_failed", "message": str(e)})
            continue
        
        fixed_code = parsed.get("fixed_code", "")
        fix_type = parsed.get("fix_type", "code_only")
        fix_description = parsed.get("fix_description", "")
        
        if not fixed_code:
            print(f"  ❌ LLM 수정 코드 없음")
            stats["failed"] += 1
            results.append({"id": rid, "status": "llm_no_code"})
            continue
        
        print(f"  ✅ LLM 수정 완료: fix_type={fix_type}, code_len={len(fixed_code)}")
        
        # Step 2: SimServer 실행
        run_result = send_and_run_on_simserver(fixed_code, rid)
        
        if run_result["status"] == "success":
            print(f"  🎉 성공! elapsed={run_result.get('elapsed', 0):.1f}s")
            code_diff = make_diff(original_code, fixed_code)
            if update_db(rid, fixed_code, code_diff, fix_description, fix_type):
                print(f"  💾 DB 업데이트 완료: fix_worked=1")
            stats["success"] += 1
            results.append({"id": rid, "status": "success", "fix_type": fix_type,
                           "elapsed": run_result.get("elapsed", 0)})
        else:
            print(f"  ❌ 실패: {run_result['status']} - {run_result.get('message', '')}")
            stats["failed"] += 1
            results.append({"id": rid, "status": run_result["status"],
                           "message": run_result.get("message", "")})
        
        # Rate limiting
        time.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"🏁 완료 요약:")
    print(f"  시도: {stats['total']}건")
    print(f"  성공: {stats['success']}건")
    print(f"  실패: {stats['failed']}건")
    print(f"  스킵: {stats['skipped']}건")
    print(f"\n상세 결과:")
    for r in results:
        status = r.get("status")
        rid = r.get("id")
        msg = r.get("message", "")
        elapsed = r.get("elapsed", "")
        et = f" ({elapsed:.1f}s)" if elapsed else ""
        print(f"  ID={rid}: {status}{et} {msg}")
    
    return results


if __name__ == "__main__":
    main()
