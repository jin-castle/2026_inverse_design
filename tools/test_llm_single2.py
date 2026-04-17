# -*- coding: utf-8 -*-
"""Test ID=21 with aggressive LLM optimization"""
import sys, tempfile
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from simserver_llm_runner import (
    get_timeout_records, get_best_code, call_llm_optimize, check_syntax,
    run_with_adaptive_mpi, update_db, scp_upload, ssh_run
)
from pathlib import Path

records = get_timeout_records()
rec = next((r for r in records if r['id'] == 21), records[0])
rid = rec['id']
code = get_best_code(rec)
print(f"ID={rid} | code_len={len(code)}")

print("LLM optimize (aggressive)...")
fix = call_llm_optimize(rec, code)
fc = fix.get('fixed_code','')
print(f"fixed_code_len={len(fc)}")
print(f"desc={fix['fix_description'][:200]}")
if fc:
    print(f"syntax OK: {check_syntax(fc)}")
    # Check resolution value in fixed code
    import re
    res_m = re.search(r'resolution\s*=\s*(\d+)', fc)
    print(f"resolution in fixed: {res_m.group(1) if res_m else 'not found'}")
    
    remote = f"/tmp/meep_fix2_{rid}.py"
    local_tmp = Path(tempfile.gettempdir()) / f"meep_fix2_{rid}.py"
    local_tmp.write_text(fc, encoding='utf-8')
    
    if scp_upload(str(local_tmp), remote):
        print("Running (max 120s)...")
        result = run_with_adaptive_mpi(remote, rid)
        print(f"status={result['status']} | np={result.get('mpi_np_used')} | time={result.get('run_time_sec',0):.1f}s")
        if result.get('stdout'):
            print(f"stdout:\n{result['stdout'][:500]}")
        if result.get('stderr') and result['status'] != 'success':
            print(f"stderr:\n{result['stderr'][:200]}")
        if result['status'] == 'success':
            update_db(rid, 1, fc, fix['fix_type'], fix['fix_description'],
                      result['run_time_sec'], result['mpi_np_used'])
            print("✅ fix_worked=1")
        else:
            update_db(rid, 0, fc, fix['fix_type'], fix['fix_description'],
                      result.get('run_time_sec',0), result.get('mpi_np_used',1))
            print("❌ fix_worked=0")
        ssh_run(f"rm -f {remote}", timeout=10)
    local_tmp.unlink(missing_ok=True)
