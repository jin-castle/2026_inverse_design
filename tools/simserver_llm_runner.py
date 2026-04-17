# -*- coding: utf-8 -*-
"""
simserver_llm_runner.py
Timeout 건들을 LLM으로 최적화 후 SimServer mpirun -np 128 실행.
full code를 examples에서 가져와 LLM에게 최적화 요청.
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"
SIMSERVER = "user@166.104.35.108"
SSH_KEY = str(Path.home() / ".ssh" / "id_ed25519")
MPI_MAX = 128
TIMEOUT_SEC = 120  # 2 minutes per job (resolution=5~8 이면 충분)

# Load .env
try:
    env_path = BASE / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
except Exception:
    pass

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def get_timeout_records():
    """Timeout + fix_worked=0 레코드, examples에서 full code 포함"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT v2.id, v2.resolution, v2.error_message, v2.original_code,
                        v2.code_hash, v2.error_class, v2.physics_cause, v2.code_cause,
                        v2.device_type, v2.run_mode, v2.dim, v2.pml_thickness, v2.wavelength_um,
                        ex.code as full_code, lr.source_ref
                 FROM sim_errors_v2 v2
                 LEFT JOIN live_runs lr ON lr.code_hash = v2.code_hash
                 LEFT JOIN examples ex ON ex.id = CAST(substr(lr.source_ref,4) AS INTEGER)
                 WHERE v2.fix_worked=0 AND v2.error_type='Timeout'
                 ORDER BY v2.id""")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_best_code(rec: dict) -> str:
    full = rec.get("full_code") or ""
    orig = rec.get("original_code") or ""
    return full if len(full) > len(orig) else orig


def call_llm_optimize(rec: dict, code: str) -> dict:
    """LLM에게 코드 최적화 요청 - Timeout 해결"""
    resolution = rec.get("resolution") or "?"
    error_msg = rec.get("error_message") or ""
    device_type = rec.get("device_type") or "general"
    physics_cause = rec.get("physics_cause") or ""

    prompt = f"""당신은 MEEP FDTD 전문가입니다.

## 문제
다음 MEEP 시뮬레이션이 Timeout(실행 시간 초과)으로 실패했습니다.
- error_message: {error_msg}
- resolution: {resolution}
- device_type: {device_type}
- physics_cause: {physics_cause}

## 원본 코드
```python
{code}
```

## 수정 지침 (필수 — 반드시 따르세요)
### A. 계산량 극단적 감소 (1분 내 완료 목표)
- resolution → **반드시 5-8로 설정** (현재 값에 관계없이)
- nperiods, num_periods, 주기 반복 → **1-2로 설정**
- until_after_sources → **100-200으로 설정**
- stop_when_fields_decayed → pt 수, tol 완화 (1e-5 → 1e-3)
- 시뮬레이션 도메인 크기 → **원래의 50% 이하로 축소**
- 파장 스위프 횟수 → **1-3개만 사용**
- 최적화 이터레이션 → **1-2번만**

### B. MPI 128코어 안전 (필수)
- 파일 최상단에: `import matplotlib; matplotlib.use('Agg')`
- `plt.show()` → 제거
- `plt.savefig(...)` → 주석 처리
- 결과 출력: `if mp.am_master(): print(...)` 사용

### C. 코드 품질
- 전체 실행 가능한 완전한 코드 제공 (import부터 끝까지)
- 코드에 한국어 주석으로 변경된 파라미터 표시

응답 형식:
FIX_TYPE: parameter_tune
FIX_DESCRIPTION: <수정 이유 설명 (한국어, 3-5문장)>
FIXED_CODE:
```python
<전체 수정된 코드>
```"""

    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 8000,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read())
            text = data["content"][0]["text"]
            return parse_llm_response(text)
    except Exception as e:
        return {"fix_type": "code_only", "fix_description": f"LLM 오류: {e}", "fixed_code": ""}


def parse_llm_response(response: str) -> dict:
    result = {"fix_type": "parameter_tune", "fix_description": "", "fixed_code": ""}
    m = re.search(r'FIX_TYPE:\s*(\S+)', response)
    if m:
        ft = m.group(1).strip().lower()
        result["fix_type"] = ft if ft in {"code_only", "physics_understanding", "parameter_tune", "structural"} else "parameter_tune"
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


def check_syntax(code: str) -> bool:
    try:
        compile(code, "<string>", "exec")
        return True
    except SyntaxError:
        return False


def ssh_run(cmd: str, timeout: int = TIMEOUT_SEC) -> tuple:
    ssh_cmd = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
               "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
               SIMSERVER, cmd]
    try:
        proc = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout after {timeout}s"
    except Exception as e:
        return -2, "", str(e)


def scp_upload(local_path: str, remote_path: str) -> bool:
    scp_cmd = ["scp", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
               local_path, f"{SIMSERVER}:{remote_path}"]
    r = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=30)
    return r.returncode == 0


def run_with_adaptive_mpi(remote_path: str, record_id: int) -> dict:
    """Adaptive MPI: 128 → 64 → 32 → 16 → 8 → 4 → 1"""
    for np in [128, 64, 32, 16, 8, 4, 1]:
        run_cmd = (
            f"source ~/anaconda3/etc/profile.d/conda.sh && conda activate pmp && "
            f"mpirun -np {np} python {remote_path} 2>&1"
        )
        start = time.time()
        rc, stdout, stderr = ssh_run(run_cmd, timeout=TIMEOUT_SEC)
        elapsed = time.time() - start
        combined = stdout + stderr

        if "Cannot split" in combined and "grid points" in combined and np > 1:
            print(f"    np={np}: grid 분할 불가 → np={np//2}")
            continue

        if "SyntaxError" in combined:
            return {
                "status": "syntax_error",
                "stdout": stdout[:1000],
                "stderr": stderr[:300],
                "run_time_sec": elapsed,
                "mpi_np_used": np,
                "message": f"SyntaxError: {combined[:200]}"
            }

        if rc == 0:
            return {
                "status": "success",
                "stdout": stdout[:3000],
                "stderr": stderr[:300],
                "run_time_sec": elapsed,
                "mpi_np_used": np,
                "message": f"성공 mpirun -np {np} ({elapsed:.1f}s)"
            }
        elif rc == -1:
            return {"status": "timeout", "message": f"timeout np={np}", "run_time_sec": elapsed, "mpi_np_used": np}
        else:
            return {
                "status": "error",
                "stdout": stdout[:1000],
                "stderr": stderr[:500],
                "run_time_sec": elapsed,
                "mpi_np_used": np,
                "message": f"rc={rc} np={np}: {combined[:200]}"
            }

    return {"status": "error", "message": "모든 MPI 설정 실패", "run_time_sec": 0, "mpi_np_used": 1}


def update_db(record_id: int, fix_worked: int, fixed_code: str,
              fix_type: str, fix_description: str, run_time_sec: float, mpi_np: int):
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""UPDATE sim_errors_v2
                 SET fix_worked=?, fixed_code=?, fix_type=?, fix_description=?,
                     run_time_sec=?, mpi_np=?
                 WHERE id=?""",
              (fix_worked, fixed_code, fix_type, fix_description, run_time_sec, mpi_np, record_id))
    conn.commit()
    conn.close()


def main():
    print("=" * 60)
    print("SimServer LLM Runner — Timeout 최적화 후 실행")
    print("=" * 60)

    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY 없음")
        sys.exit(1)

    records = get_timeout_records()
    total = len(records)
    print(f"대상: {total}건")

    if total == 0:
        print("없음")
        return [], [], {}

    success_ids = []
    fail_ids = []
    fail_reasons = {}

    for i, rec in enumerate(records):
        rid = rec["id"]
        res = rec.get("resolution")
        src_ref = rec.get("source_ref") or "N/A"
        print(f"\n[{i+1}/{total}] ID={rid} | res={res} | src={src_ref}")

        code = get_best_code(rec)
        if not code:
            print(f"  SKIP: code 없음")
            fail_ids.append(rid)
            fail_reasons[rid] = "code 없음"
            continue

        code_len = len(code)
        has_full = bool(rec.get("full_code")) and len(rec.get("full_code","")) >= code_len
        print(f"  code_len={code_len} (full={'Yes' if has_full else 'No/truncated'})")

        # LLM 최적화
        print(f"  LLM 최적화 중...")
        fix_result = call_llm_optimize(rec, code)
        fixed_code = fix_result.get("fixed_code", "")
        fix_type = fix_result.get("fix_type", "parameter_tune")
        fix_desc = fix_result.get("fix_description", "")

        if not fixed_code:
            print(f"  ❌ LLM fixed_code 없음: {fix_desc[:80]}")
            fail_ids.append(rid)
            fail_reasons[rid] = f"LLM 응답 없음: {fix_desc[:80]}"
            update_db(rid, 0, "", fix_type, fix_desc, 0, 1)
            time.sleep(2)
            continue

        print(f"  fix_type={fix_type} | fixed_code_len={len(fixed_code)}")

        if not check_syntax(fixed_code):
            print(f"  ⚠️ 구문 오류 → 재시도...")
            # 구문 오류 정보를 LLM에 피드백
            try:
                compile(fixed_code, "<string>", "exec")
            except SyntaxError as se:
                syntax_err = str(se)
            else:
                syntax_err = "unknown"
            # 재시도 (간단 버전)
            fix2 = call_llm_optimize(rec, code)
            fixed_code2 = fix2.get("fixed_code", "")
            if fixed_code2 and check_syntax(fixed_code2):
                fixed_code = fixed_code2
                fix_type = fix2.get("fix_type", fix_type)
                fix_desc = fix2.get("fix_description", fix_desc)
                print(f"  재시도 성공 | fixed_code_len={len(fixed_code)}")
            else:
                print(f"  ❌ 재시도도 구문 오류: {syntax_err[:80]}")
                fail_ids.append(rid)
                fail_reasons[rid] = f"SyntaxError: {syntax_err[:80]}"
                update_db(rid, 0, fixed_code, fix_type, fix_desc, 0, 1)
                time.sleep(2)
                continue

        # SimServer 실행
        remote_path = f"/tmp/meep_fix_{rid}.py"
        local_tmp = Path(tempfile.gettempdir()) / f"meep_fix_{rid}.py"
        local_tmp.write_text(fixed_code, encoding="utf-8")

        try:
            if not scp_upload(str(local_tmp), remote_path):
                print(f"  SCP 실패")
                fail_ids.append(rid)
                fail_reasons[rid] = "SCP failed"
                update_db(rid, 0, fixed_code, fix_type, fix_desc, 0, 1)
                continue

            print(f"  실행 중 (adaptive MPI, max {TIMEOUT_SEC}s)...")
            run_result = run_with_adaptive_mpi(remote_path, rid)
            run_status = run_result["status"]
            run_time = run_result.get("run_time_sec", 0)
            np_used = run_result.get("mpi_np_used", 1)
            msg = run_result.get("message", "")

            print(f"  결과: {run_status} | np={np_used} | {run_time:.1f}s")
            if run_result.get("stdout"):
                print(f"  stdout: {run_result['stdout'][:200]}")
            if run_result.get("stderr") and run_status != "success":
                print(f"  stderr: {run_result['stderr'][:150]}")

            if run_status == "success":
                update_db(rid, 1, fixed_code, fix_type,
                          fix_desc + f"\nSimServer mpirun -np {np_used} {run_time:.1f}s 성공",
                          run_time, np_used)
                success_ids.append(rid)
                print(f"  ✅ fix_worked=1")
            else:
                update_db(rid, 0, fixed_code, fix_type,
                          fix_desc + f"\n실패: {msg[:150]}", run_time, np_used)
                fail_ids.append(rid)
                fail_reasons[rid] = msg[:200]
                print(f"  ❌ 실패: {msg[:100]}")

        finally:
            local_tmp.unlink(missing_ok=True)
            ssh_run(f"rm -f {remote_path}", timeout=10)

        time.sleep(2)  # rate limit

    print("\n" + "=" * 60)
    print(f"[완료] 총 {total} / 성공 {len(success_ids)} / 실패 {len(fail_ids)}")
    print(f"성공 IDs: {success_ids}")
    for fid in fail_ids:
        print(f"  ID={fid}: {fail_reasons.get(fid,'')[:120]}")
    print("=" * 60)
    return success_ids, fail_ids, fail_reasons


if __name__ == "__main__":
    main()
