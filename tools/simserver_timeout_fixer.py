# -*- coding: utf-8 -*-
"""
simserver_timeout_fixer.py
Timeout 건들을 LLM으로 fix 생성 후 SimServer(166.104.35.108)에서 mpirun -np 128로 실행.
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

# ─────────────────────────────────────────────
BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"
SIMSERVER = "user@166.104.35.108"
SSH_KEY = str(Path.home() / ".ssh" / "id_ed25519")
MPI_NP = 128
TIMEOUT_SEC = 600  # 10 minutes per job on SimServer

# ─────────────────────────────────────────────
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
    """fix_worked=0 AND error_type='Timeout' 레코드 조회"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT id, error_type, resolution, mpi_np, error_message,
                        original_code, original_code_raw, fix_type, fix_description,
                        fixed_code, run_mode, device_type, error_class, symptom,
                        pml_thickness, wavelength_um, dim, physics_cause, code_cause,
                        root_cause_chain, traceback_full
                 FROM sim_errors_v2
                 WHERE fix_worked=0 AND error_type='Timeout'
                 ORDER BY id""")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def call_llm_fix(record: dict) -> dict:
    """LLM에게 Timeout 수정 요청 (resolution 감소 + MPI 최적화)"""
    original_code = record.get("original_code") or record.get("original_code_raw") or ""
    if not original_code:
        return {"fix_type": "code_only", "fix_description": "no original_code", "fixed_code": ""}

    resolution = record.get("resolution") or "?"
    error_msg = record.get("error_message") or ""
    device_type = record.get("device_type") or "general"
    run_mode = record.get("run_mode") or "forward"
    physics_cause = record.get("physics_cause") or ""
    code_cause = record.get("code_cause") or ""

    prompt = f"""당신은 MEEP FDTD 전문가입니다.

## 문제
다음 MEEP 시뮬레이션 코드가 Timeout (실행 시간 초과)으로 실패했습니다.
- error_type: Timeout
- error_message: {error_msg}
- resolution: {resolution}
- device_type: {device_type}
- run_mode: {run_mode}
- physics_cause: {physics_cause}
- code_cause: {code_cause}

## 원본 코드
```python
{original_code[:4000]}
```

## 수정 지침
1. Timeout의 원인을 파악하고 수정하세요.
2. **핵심**: MPI 128코어로 실행됩니다. MPI 환경에서 안전하게 실행되도록 수정하세요.
3. matplotlib를 사용하면 반드시 `import matplotlib; matplotlib.use('Agg')` 추가
4. 파일 저장 코드(plt.savefig 등)는 제거하거나 /tmp 경로로 변경
5. 시뮬레이션이 합리적인 시간(5분 이내)에 완료되도록:
   - resolution이 50 이상이면 25-40으로 낮추기
   - 시뮬레이션 도메인이 크면 축소
   - until_after_sources 값이 크면 줄이기
   - nperiods가 크면 줄이기
6. 결과는 반드시 stdout에 출력: T값, R값 또는 주요 결과
7. MPI rank 0에서만 출력하도록: `if mp.am_master():`
8. 코드가 완전하고 실행 가능해야 함

응답 형식:
FIX_TYPE: <code_only|parameter_tune|structural>
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
            response_text = data["content"][0]["text"]
    except Exception as e:
        return {"fix_type": "code_only", "fix_description": f"LLM call failed: {e}", "fixed_code": ""}

    return parse_llm_response(response_text)


def parse_llm_response(response: str) -> dict:
    result = {"fix_type": "code_only", "fix_description": "", "fixed_code": ""}

    m = re.search(r'FIX_TYPE:\s*(\S+)', response)
    if m:
        ft = m.group(1).strip().lower()
        valid = {"code_only", "physics_understanding", "parameter_tune", "structural"}
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


def run_on_simserver(code: str, record_id: int, mpi_np: int = MPI_NP) -> dict:
    """코드를 SimServer에 SCP 후 mpirun -np <n>으로 실행. grid가 작으면 자동으로 np 줄임."""
    remote_path = f"/tmp/meep_fix_{record_id}.py"
    local_tmp = Path(tempfile.gettempdir()) / f"meep_fix_{record_id}.py"
    local_tmp.write_text(code, encoding="utf-8")

    try:
        # SCP 업로드
        scp_cmd = ["scp", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
                   str(local_tmp), f"{SIMSERVER}:{remote_path}"]
        r = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return {"status": "error", "message": f"SCP failed: {r.stderr}", "run_time_sec": 0}

        # 적응형 MPI: 128 → 64 → 32 → 16 → 8 → 4 → 1
        mpi_candidates = [np for np in [128, 64, 32, 16, 8, 4, 1] if np <= mpi_np]
        last_result = None

        for np_try in mpi_candidates:
            run_cmd = (
                f"source ~/anaconda3/etc/profile.d/conda.sh && conda activate pmp && "
                f"mpirun -np {np_try} python {remote_path}"
            )
            ssh_cmd = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
                       SIMSERVER, f"bash -c \"{run_cmd}\""]

            start = time.time()
            try:
                proc = subprocess.run(
                    ssh_cmd,
                    capture_output=True, text=True,
                    timeout=TIMEOUT_SEC
                )
                elapsed = time.time() - start

                # grid 분할 에러 감지
                split_error = "Cannot split" in proc.stderr and "grid points" in proc.stderr
                if split_error and np_try > 1:
                    print(f"    mpirun -np {np_try}: grid 분할 불가, {np_try//2}으로 재시도...")
                    continue

                if proc.returncode == 0:
                    return {
                        "status": "success",
                        "stdout": proc.stdout[:2000],
                        "stderr": proc.stderr[:500],
                        "run_time_sec": elapsed,
                        "mpi_np_used": np_try,
                        "message": f"SimServer 실행 성공 (mpirun -np {np_try})"
                    }
                else:
                    last_result = {
                        "status": "error",
                        "stdout": proc.stdout[:1000],
                        "stderr": proc.stderr[:1000],
                        "run_time_sec": elapsed,
                        "mpi_np_used": np_try,
                        "message": f"SimServer 실행 실패 (rc={proc.returncode}, np={np_try})"
                    }
                    break  # 다른 에러면 재시도 무의미

            except subprocess.TimeoutExpired:
                return {"status": "timeout", "message": f"SimServer에서도 {TIMEOUT_SEC}s 초과 (np={np_try})", "run_time_sec": TIMEOUT_SEC, "mpi_np_used": np_try}

        return last_result or {"status": "error", "message": "모든 MPI 설정 실패", "run_time_sec": 0, "mpi_np_used": 1}

    except Exception as e:
        return {"status": "error", "message": str(e), "run_time_sec": 0, "mpi_np_used": 1}
    finally:
        local_tmp.unlink(missing_ok=True)
        try:
            subprocess.run(
                ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
                 SIMSERVER, f"rm -f {remote_path}"],
                capture_output=True, timeout=10
            )
        except Exception:
            pass


def update_db(record_id: int, fix_worked: int, fixed_code: str,
              fix_type: str, fix_description: str, run_time_sec: float, mpi_np: int = MPI_NP):
    """DB 업데이트"""
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
    print("SimServer Timeout Fixer — mpirun -np 128")
    print("=" * 60)

    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    records = get_timeout_records()
    total = len(records)
    print(f"대상 레코드: {total}건 (error_type='Timeout', fix_worked=0)")

    if total == 0:
        print("처리할 레코드가 없습니다.")
        return

    success_ids = []
    fail_ids = []
    fail_reasons = {}

    for i, rec in enumerate(records):
        rid = rec["id"]
        print(f"\n[{i+1}/{total}] ID={rid} | res={rec.get('resolution')} | {rec.get('error_message','')[:50]}")

        original_code = rec.get("original_code") or rec.get("original_code_raw") or ""
        if not original_code:
            print(f"  SKIP: original_code 없음")
            fail_ids.append(rid)
            fail_reasons[rid] = "original_code 없음"
            continue

        # Step 1: LLM fix 생성
        print(f"  LLM fix 생성 중...")
        fix_result = call_llm_fix(rec)
        fixed_code = fix_result.get("fixed_code", "")
        fix_type = fix_result.get("fix_type", "code_only")
        fix_desc = fix_result.get("fix_description", "")

        if not fixed_code:
            print(f"  FAIL: LLM이 fixed_code 생성 실패")
            fail_ids.append(rid)
            fail_reasons[rid] = f"LLM fixed_code 없음: {fix_desc[:100]}"
            # fixed_code 없어도 fix_description은 저장
            update_db(rid, 0, "", fix_type, fix_desc, 0, 1)
            time.sleep(1)
            continue

        print(f"  fix_type={fix_type}, fixed_code len={len(fixed_code)}")

        # Step 2: SimServer 실행
        print(f"  SimServer 실행 중 (mpirun -np {MPI_NP})...")
        run_result = run_on_simserver(fixed_code, rid)
        run_status = run_result.get("status")
        run_time = run_result.get("run_time_sec", 0)
        message = run_result.get("message", "")

        print(f"  결과: status={run_status} | time={run_time:.1f}s | {message[:80]}")
        if run_result.get("stdout"):
            print(f"  stdout: {run_result['stdout'][:200]}")

        mpi_np_used = run_result.get("mpi_np_used", MPI_NP)

        if run_status == "success":
            # fix_worked=1 업데이트
            update_db(rid, 1, fixed_code, fix_type, fix_desc, run_time, mpi_np_used)
            success_ids.append(rid)
            print(f"  ✅ DB 업데이트 완료 (fix_worked=1, mpirun -np {mpi_np_used})")
        else:
            # fix_worked=0 유지, fixed_code와 fix_description은 저장
            reason = f"{run_status}: {message}"
            if run_result.get("stderr"):
                reason += f" | stderr: {run_result['stderr'][:100]}"
            update_db(rid, 0, fixed_code, fix_type, fix_desc, run_time, mpi_np_used)
            fail_ids.append(rid)
            fail_reasons[rid] = reason
            print(f"  ❌ 실패: {reason[:120]}")

        # Rate limiting
        time.sleep(2)

    # 최종 결과
    print("\n" + "=" * 60)
    print(f"완료: 총 {total}건 / 성공 {len(success_ids)}건 / 실패 {len(fail_ids)}건")
    print(f"성공 IDs: {success_ids}")
    print(f"실패 IDs: {fail_ids}")
    for fid, reason in fail_reasons.items():
        print(f"  ID={fid}: {reason[:150]}")
    print("=" * 60)

    return success_ids, fail_ids, fail_reasons


if __name__ == "__main__":
    main()
