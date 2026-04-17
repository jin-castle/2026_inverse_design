# -*- coding: utf-8 -*-
"""
Retry for failed Timeout records with more aggressive optimization.
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
TIMEOUT_SEC = 240  # 4 minutes

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

TARGET_IDS = [32, 34, 39, 63, 64, 69, 73, 74, 78, 81, 84, 85, 86, 87, 94, 97, 103, 104, 105, 108]


def get_record(rid: int) -> dict:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT v2.id, v2.resolution, v2.error_message, v2.original_code,
                        v2.code_hash, v2.device_type, v2.run_mode, v2.physics_cause,
                        ex.code as full_code, lr.source_ref
                 FROM sim_errors_v2 v2
                 LEFT JOIN live_runs lr ON lr.code_hash = v2.code_hash
                 LEFT JOIN examples ex ON ex.id = CAST(substr(lr.source_ref,4) AS INTEGER)
                 WHERE v2.id=?""", (rid,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {}


def get_best_code(rec: dict) -> str:
    full = rec.get("full_code") or ""
    orig = rec.get("original_code") or ""
    return full if len(full) > len(orig) else orig


def call_llm_ultra_reduce(rec: dict, code: str, prev_error: str = "") -> dict:
    """초강력 최소화 프롬프트"""
    resolution = rec.get("resolution") or "?"
    prompt = f"""당신은 MEEP FDTD 전문가입니다.

## 상황
이전 시도에서 실패: {prev_error[:200] if prev_error else '타임아웃/실행오류'}

## 원본 코드 (resolution={resolution})
```python
{code[:5000]}
```

## 매우 강력한 최소화 지침
1. resolution → **반드시 4로 고정** (협상 불가)
2. 도메인 크기 → 파장의 4-5배만 유지 (나머지 삭제)
3. nperiods/반복 → **1로 고정**
4. until_after_sources → **50으로 고정**  
5. 스위프 포인트 → **1개만** (파장/주파수 단일 포인트)
6. 최적화 루프 → **완전 제거** (단일 forward 계산만)
7. 결과 저장/플롯 → **모두 제거** (print만 남김)
8. `import matplotlib; matplotlib.use('Agg')` 최상단
9. 모든 결과 print는 `if mp.am_master():` 안에

**이전 오류 분석:**
{prev_error[:300] if prev_error else '없음'}

응답:
FIX_TYPE: structural
FIX_DESCRIPTION: <설명>
FIXED_CODE:
```python
<전체 코드>
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
            return parse_response(text)
    except Exception as e:
        return {"fix_type": "structural", "fix_description": f"LLM 오류: {e}", "fixed_code": ""}


def parse_response(text: str) -> dict:
    result = {"fix_type": "structural", "fix_description": "", "fixed_code": ""}
    m = re.search(r'FIX_TYPE:\s*(\S+)', text)
    if m:
        result["fix_type"] = m.group(1).strip().lower()
    m = re.search(r'FIX_DESCRIPTION:\s*(.*?)(?=FIXED_CODE:|$)', text, re.DOTALL)
    if m:
        result["fix_description"] = m.group(1).strip()
    m = re.search(r'FIXED_CODE:\s*```python\s*(.*?)```', text, re.DOTALL)
    if m:
        result["fixed_code"] = m.group(1).strip()
    return result


def check_syntax(code: str) -> tuple:
    try:
        compile(code, "<string>", "exec")
        return True, ""
    except SyntaxError as e:
        return False, str(e)


def ssh_run(cmd: str, timeout: int = TIMEOUT_SEC) -> tuple:
    ssh_cmd = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
               "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", SIMSERVER, cmd]
    try:
        proc = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout"
    except Exception as e:
        return -2, "", str(e)


def scp_upload(local_path: str, remote_path: str) -> bool:
    cmd = ["scp", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
           local_path, f"{SIMSERVER}:{remote_path}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.returncode == 0


def run_adaptive(remote_path: str) -> dict:
    for np in [128, 64, 32, 16, 8, 4, 1]:
        cmd = (f"source ~/anaconda3/etc/profile.d/conda.sh && conda activate pmp && "
               f"mpirun -np {np} python {remote_path} 2>&1")
        start = time.time()
        rc, stdout, stderr = ssh_run(cmd, timeout=TIMEOUT_SEC)
        elapsed = time.time() - start
        combined = stdout + stderr

        if "Cannot split" in combined and "grid points" in combined and np > 1:
            print(f"    np={np}: grid 분할 불가 → np={np//2}")
            continue

        if rc == 0:
            return {"status": "success", "stdout": stdout[:2000], "stderr": stderr[:300],
                    "run_time_sec": elapsed, "mpi_np_used": np}
        elif rc == -1:
            return {"status": "timeout", "run_time_sec": elapsed, "mpi_np_used": np,
                    "message": f"timeout np={np}"}
        else:
            return {"status": "error", "stdout": stdout[:1000], "stderr": stderr[:500],
                    "run_time_sec": elapsed, "mpi_np_used": np,
                    "message": f"rc={rc} np={np}: {combined[:200]}"}

    return {"status": "error", "message": "모든 NP 실패", "run_time_sec": 0, "mpi_np_used": 1}


def update_db(rid: int, fix_worked: int, fixed_code: str, fix_type: str,
              fix_desc: str, run_time: float, mpi_np: int):
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""UPDATE sim_errors_v2 SET fix_worked=?, fixed_code=?, fix_type=?,
                 fix_description=?, run_time_sec=?, mpi_np=? WHERE id=?""",
              (fix_worked, fixed_code, fix_type, fix_desc, run_time, mpi_np, rid))
    conn.commit()
    conn.close()


def get_prev_error(rid: int) -> str:
    """이전 실행의 fix_description에서 에러 정보 추출"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT fix_description FROM sim_errors_v2 WHERE id=?", (rid,))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else ""


def main():
    print("=" * 60)
    print(f"Retry Batch — {len(TARGET_IDS)}건")
    print("=" * 60)

    success_ids = []
    fail_ids = []
    fail_reasons = {}

    for i, rid in enumerate(TARGET_IDS):
        print(f"\n[{i+1}/{len(TARGET_IDS)}] ID={rid}")
        rec = get_record(rid)
        if not rec:
            print(f"  레코드 없음")
            fail_ids.append(rid)
            fail_reasons[rid] = "DB 없음"
            continue

        code = get_best_code(rec)
        if not code:
            print(f"  코드 없음")
            fail_ids.append(rid)
            fail_reasons[rid] = "코드 없음"
            continue

        prev_err = get_prev_error(rid)
        print(f"  code_len={len(code)}")

        # LLM 최소화
        print(f"  LLM 초강력 축소...")
        fix = call_llm_ultra_reduce(rec, code, prev_err)
        fc = fix.get("fixed_code", "")

        if not fc:
            print(f"  ❌ fixed_code 없음")
            fail_ids.append(rid)
            fail_reasons[rid] = "LLM 응답 없음"
            time.sleep(2)
            continue

        ok, err = check_syntax(fc)
        if not ok:
            # 재시도
            print(f"  ⚠️ 구문 오류 ({err[:50]}) → 재시도")
            fix2 = call_llm_ultra_reduce(rec, code, f"이전 코드에 구문 오류: {err}")
            fc2 = fix2.get("fixed_code", "")
            if fc2:
                ok2, err2 = check_syntax(fc2)
                if ok2:
                    fc = fc2
                    fix = fix2
                    ok = True
                else:
                    print(f"  ❌ 재시도도 구문 오류")
                    fail_ids.append(rid)
                    fail_reasons[rid] = f"SyntaxError: {err2[:60]}"
                    update_db(rid, 0, fc2, fix2.get("fix_type","structural"),
                              f"SyntaxError: {err2}", 0, 1)
                    time.sleep(2)
                    continue
            else:
                fail_ids.append(rid)
                fail_reasons[rid] = "재시도도 fixed_code 없음"
                time.sleep(2)
                continue

        res_m = re.search(r'resolution\s*=\s*(\d+)', fc)
        print(f"  resolution in fixed: {res_m.group(1) if res_m else '?'} | fc_len={len(fc)}")

        # SCP + 실행
        remote = f"/tmp/meep_retry_{rid}.py"
        local_tmp = Path(tempfile.gettempdir()) / f"meep_retry_{rid}.py"
        local_tmp.write_text(fc, encoding="utf-8")

        try:
            if not scp_upload(str(local_tmp), remote):
                fail_ids.append(rid)
                fail_reasons[rid] = "SCP 실패"
                continue

            print(f"  실행 중 (max {TIMEOUT_SEC}s)...")
            result = run_adaptive(remote)
            status = result.get("status")
            np_used = result.get("mpi_np_used", 1)
            rt = result.get("run_time_sec", 0)
            msg = result.get("message", "")

            print(f"  결과: {status} | np={np_used} | {rt:.1f}s")
            if result.get("stdout"):
                print(f"  stdout: {result['stdout'][:200]}")
            if result.get("stderr") and status != "success":
                print(f"  stderr: {result['stderr'][:150]}")

            if status == "success":
                update_db(rid, 1, fc, fix["fix_type"],
                          fix["fix_description"] + f"\nRetry 성공 np={np_used} {rt:.1f}s",
                          rt, np_used)
                success_ids.append(rid)
                print(f"  ✅ fix_worked=1")
            else:
                update_db(rid, 0, fc, fix["fix_type"],
                          fix["fix_description"] + f"\nRetry 실패: {msg[:100]}",
                          rt, np_used)
                fail_ids.append(rid)
                fail_reasons[rid] = msg[:150]
                print(f"  ❌ {msg[:100]}")

        finally:
            local_tmp.unlink(missing_ok=True)
            ssh_run(f"rm -f {remote}", timeout=10)

        time.sleep(2)

    print("\n" + "=" * 60)
    print(f"Retry 완료: 성공 {len(success_ids)} / 실패 {len(fail_ids)}")
    print(f"성공: {success_ids}")
    for fid in fail_ids:
        print(f"  ID={fid}: {fail_reasons.get(fid,'')[:100]}")
    print("=" * 60)
    return success_ids, fail_ids, fail_reasons


if __name__ == "__main__":
    main()
