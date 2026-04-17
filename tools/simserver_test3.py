# -*- coding: utf-8 -*-
"""Test single record with full code from examples"""
import sys, tempfile
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from simserver_direct_runner import (
    get_timeout_records, get_best_code, patch_code_for_mpi, check_syntax,
    run_with_adaptive_mpi, update_db, scp_upload, ssh_run
)
from pathlib import Path

records = get_timeout_records()
# Find ID=21
rec = next((r for r in records if r['id'] == 21), records[0])
rid = rec['id']
print(f"Testing ID={rid} | res={rec.get('resolution')} | source_ref={rec.get('source_ref')}")

code = get_best_code(rec)
print(f"Code len: {len(code)} | Full code: {'Yes' if rec.get('full_code') else 'No'}")
print(f"Syntax OK: {check_syntax(code)}")

patched = patch_code_for_mpi(code)
print(f"Patched syntax OK: {check_syntax(patched)}")
print(f"First 200: {patched[:200]}")

remote_path = f"/tmp/meep_timeout_{rid}.py"
local_tmp = Path(tempfile.gettempdir()) / f"meep_timeout_{rid}.py"
local_tmp.write_text(patched, encoding='utf-8')

print("\nSCP upload...")
if scp_upload(str(local_tmp), remote_path):
    print("Running adaptive MPI...")
    result = run_with_adaptive_mpi(remote_path, rid)
    print(f"status={result['status']} | np={result.get('mpi_np_used')} | time={result.get('run_time_sec',0):.1f}s")
    print(f"message={result.get('message','')[:200]}")
    if result.get('stdout'):
        print(f"stdout:\n{result['stdout'][:500]}")
    
    if result['status'] == 'success':
        update_db(rid, 1, patched, "simserver_mpi",
                  f"SimServer mpirun -np {result['mpi_np_used']} 성공",
                  result['run_time_sec'], result['mpi_np_used'])
        print("✅ DB fix_worked=1")
    else:
        update_db(rid, 0, patched, "simserver_mpi",
                  result.get('message','')[:200],
                  result.get('run_time_sec',0), result.get('mpi_np_used',1))
        print("❌ DB fix_worked=0")
    ssh_run(f"rm -f {remote_path}", timeout=10)
else:
    print("SCP FAILED")

local_tmp.unlink(missing_ok=True)
