# -*- coding: utf-8 -*-
"""
simserver_direct_runner.py
Timeout 건들의 코드를 SimServer mpirun -np 128으로 직접 실행.
- examples 테이블에서 full code 우선 사용
- 없으면 original_code (5000자 제한) 사용
- 코드 수정: matplotlib Agg + MPI-safe + plt.show() 제거
"""

import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"
SIMSERVER = "user@166.104.35.108"
SSH_KEY = str(Path.home() / ".ssh" / "id_ed25519")
MPI_MAX = 128
TIMEOUT_SEC = 600


def get_timeout_records():
    """fix_worked=0 AND error_type='Timeout' + full code from examples if available"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # LEFT JOIN으로 examples full code 포함
    c.execute("""SELECT v2.id, v2.resolution, v2.mpi_np, v2.error_message,
                        v2.original_code, v2.original_code_raw, v2.code_hash,
                        v2.fix_type, v2.fix_description, v2.fixed_code,
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
    """Full code 우선, 없으면 original_code"""
    full = rec.get("full_code") or ""
    orig = rec.get("original_code") or rec.get("original_code_raw") or ""

    # full_code가 더 길면 우선 사용
    if full and len(full) > len(orig):
        return full
    return orig


def patch_code_for_mpi(code: str) -> str:
    """MPI 실행 안전 패치:
    1. matplotlib → Agg 백엔드
    2. plt.show() 제거
    3. plt.savefig → 주석처리
    """
    if not code:
        return code

    lines = code.splitlines()
    result = []
    agg_added = False

    for line in lines:
        stripped = line.strip()

        # import matplotlib → Agg 추가
        if not agg_added and re.match(r'^import matplotlib\b', stripped):
            result.append(line)
            result.append("import matplotlib; matplotlib.use('Agg')")
            agg_added = True
            continue

        # from matplotlib / import matplotlib.pyplot → 먼저 Agg 추가
        if not agg_added and re.match(r'^(import matplotlib\.|from matplotlib)', stripped):
            result.append("import matplotlib; matplotlib.use('Agg')")
            agg_added = True
            result.append(line)
            continue

        # plt.show() → 주석
        if re.match(r'^\s*plt\.show\(\)', line):
            result.append(line.replace('plt.show()', '# plt.show()'))
            continue

        # plt.savefig → 주석
        if re.search(r'plt\.savefig\s*\(', line):
            result.append(re.sub(r'plt\.savefig\s*\([^)]+\)', '# plt.savefig disabled', line))
            continue

        result.append(line)

    # matplotlib가 있는데 Agg 추가 안된 경우
    if not agg_added and 'matplotlib' in code:
        result.insert(0, "import matplotlib; matplotlib.use('Agg')")

    return '\n'.join(result)


def check_syntax(code: str) -> bool:
    """Python 구문 체크"""
    try:
        compile(code, "<string>", "exec")
        return True
    except SyntaxError:
        return False


def ssh_run(cmd: str, timeout: int = TIMEOUT_SEC) -> tuple:
    """SSH 원격 명령 실행. (returncode, stdout, stderr)"""
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
    """adaptive MPI: 128 → 64 → 32 → 16 → 8 → 4 → 1"""
    for np in [128, 64, 32, 16, 8, 4, 1]:
        run_cmd = (
            f"source ~/anaconda3/etc/profile.d/conda.sh && conda activate pmp && "
            f"mpirun -np {np} python {remote_path} 2>&1"
        )
        start = time.time()
        rc, stdout, stderr = ssh_run(run_cmd, timeout=TIMEOUT_SEC)
        elapsed = time.time() - start
        combined = stdout + stderr

        # grid 분할 에러 → np 줄이기
        if "Cannot split" in combined and "grid points" in combined and np > 1:
            print(f"    np={np}: grid 분할 불가 → np={np//2} 재시도")
            continue

        # 구문 에러 → 재시도 무의미
        if "SyntaxError" in combined:
            return {
                "status": "syntax_error",
                "stdout": stdout[:1000],
                "stderr": stderr[:500],
                "run_time_sec": elapsed,
                "mpi_np_used": np,
                "message": f"SyntaxError (truncated code): {combined[:200]}"
            }

        if rc == 0:
            return {
                "status": "success",
                "stdout": stdout[:3000],
                "stderr": stderr[:500],
                "run_time_sec": elapsed,
                "mpi_np_used": np,
                "message": f"성공 mpirun -np {np} ({elapsed:.1f}s)"
            }
        elif rc == -1:
            return {"status": "timeout", "message": f"timeout (np={np}, {elapsed:.0f}s)", "run_time_sec": elapsed, "mpi_np_used": np}
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
    print("SimServer Direct Runner — Timeout 건 처리")
    print("=" * 60)

    records = get_timeout_records()
    total = len(records)
    print(f"대상: {total}건 (error_type='Timeout', fix_worked=0)")

    if total == 0:
        print("처리할 레코드 없음.")
        return [], [], {}

    success_ids = []
    fail_ids = []
    fail_reasons = {}

    for i, rec in enumerate(records):
        rid = rec["id"]
        res = rec.get("resolution")
        src_ref = rec.get("source_ref") or "N/A"
        errmsg = (rec.get("error_message") or "")[:50]
        print(f"\n[{i+1}/{total}] ID={rid} | res={res} | src={src_ref} | {errmsg}")

        # 코드 선택
        code = get_best_code(rec)
        if not code:
            print(f"  SKIP: code 없음")
            fail_ids.append(rid)
            fail_reasons[rid] = "코드 없음"
            continue

        print(f"  code_len={len(code)} | full_code={'Yes' if rec.get('full_code') else 'No (truncated)'}")

        # 구문 체크 먼저
        if not check_syntax(code):
            print(f"  구문 오류 → patch 전 syntax error (코드 잘림 가능)")
            # MPI patch 없이도 에러면 skip
            fail_ids.append(rid)
            fail_reasons[rid] = "SyntaxError (original_code truncated)"
            update_db(rid, 0, code, "simserver_mpi", "구문 오류 (코드 잘림)", 0, 1)
            continue

        # MPI-safe 패치
        patched = patch_code_for_mpi(code)

        # 패치 후 구문 체크
        if not check_syntax(patched):
            print(f"  패치 후 구문 오류")
            fail_ids.append(rid)
            fail_reasons[rid] = "SyntaxError after patch"
            update_db(rid, 0, patched, "simserver_mpi", "패치 후 구문 오류", 0, 1)
            continue

        # SCP 업로드
        remote_path = f"/tmp/meep_timeout_{rid}.py"
        local_tmp = Path(tempfile.gettempdir()) / f"meep_timeout_{rid}.py"
        local_tmp.write_text(patched, encoding="utf-8")

        try:
            if not scp_upload(str(local_tmp), remote_path):
                print(f"  SCP 실패")
                fail_ids.append(rid)
                fail_reasons[rid] = "SCP failed"
                continue

            print(f"  SCP OK → 실행 중...")
            run_result = run_with_adaptive_mpi(remote_path, rid)
            run_status = run_result["status"]
            run_time = run_result.get("run_time_sec", 0)
            np_used = run_result.get("mpi_np_used", 1)
            message = run_result.get("message", "")

            print(f"  결과: {run_status} | np={np_used} | {run_time:.1f}s")
            if run_result.get("stdout"):
                print(f"  stdout: {run_result['stdout'][:200]}")
            if run_result.get("stderr") and run_status != "success":
                print(f"  stderr: {run_result['stderr'][:150]}")

            if run_status == "success":
                update_db(rid, 1, patched, "simserver_mpi",
                          f"SimServer mpirun -np {np_used} 성공 ({run_time:.1f}s)", run_time, np_used)
                success_ids.append(rid)
                print(f"  ✅ fix_worked=1 저장")
            else:
                update_db(rid, 0, patched, "simserver_mpi",
                          f"실패: {message[:200]}", run_time, np_used)
                fail_ids.append(rid)
                fail_reasons[rid] = message[:200]
                print(f"  ❌ 실패: {message[:100]}")

        finally:
            local_tmp.unlink(missing_ok=True)
            ssh_run(f"rm -f {remote_path}", timeout=10)

    # 결과 출력
    print("\n" + "=" * 60)
    print(f"[완료] 총 {total}건 / 성공 {len(success_ids)}건 / 실패 {len(fail_ids)}건")
    print(f"성공 IDs: {success_ids}")
    for fid in fail_ids:
        print(f"  실패 ID={fid}: {fail_reasons.get(fid, '?')[:120]}")
    print("=" * 60)
    return success_ids, fail_ids, fail_reasons


if __name__ == "__main__":
    main()
