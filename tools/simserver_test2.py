# -*- coding: utf-8 -*-
"""Test direct runner on single record"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from simserver_direct_runner import (
    get_timeout_records, patch_code_for_mpi, run_with_adaptive_mpi, update_db, scp_upload, ssh_run
)
import tempfile
from pathlib import Path

records = get_timeout_records()
rec = records[0]  # ID=21
rid = rec["id"]
print(f"Testing ID={rid}, res={rec.get('resolution')}")

original_code = rec.get("original_code") or ""
print(f"original_code len={len(original_code)}")
print("First 300 chars of patched code:")
patched = patch_code_for_mpi(original_code)
print(patched[:300])

remote_path = f"/tmp/meep_timeout_{rid}.py"
local_tmp = Path(tempfile.gettempdir()) / f"meep_timeout_{rid}.py"
local_tmp.write_text(patched, encoding="utf-8")

print("\nUploading to SimServer...")
if scp_upload(str(local_tmp), remote_path):
    print("SCP OK")
    print("Running (adaptive MPI)...")
    result = run_with_adaptive_mpi(remote_path, rid)
    print(f"status={result['status']}")
    print(f"mpi_np_used={result.get('mpi_np_used')}")
    print(f"run_time={result.get('run_time_sec', 0):.1f}s")
    print(f"message={result.get('message', '')[:200]}")
    if result.get('stdout'):
        print(f"stdout:\n{result['stdout'][:400]}")
    if result.get('stderr') and result['status'] != 'success':
        print(f"stderr:\n{result['stderr'][:300]}")
    
    if result['status'] == 'success':
        update_db(rid, 1, patched, "simserver_mpi", 
                  f"SimServer mpirun -np {result['mpi_np_used']} 성공",
                  result['run_time_sec'], result['mpi_np_used'])
        print("✅ DB updated fix_worked=1")
    else:
        update_db(rid, 0, patched, "simserver_mpi",
                  f"실패: {result.get('message','')[:200]}",
                  result.get('run_time_sec', 0), result.get('mpi_np_used', 1))
        print("❌ DB updated fix_worked=0 (patched code saved)")
    
    ssh_run(f"rm -f {remote_path}", timeout=10)
else:
    print("SCP FAILED")

local_tmp.unlink(missing_ok=True)
