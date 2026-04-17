# -*- coding: utf-8 -*-
"""Single record test for simserver_timeout_fixer"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from simserver_timeout_fixer import (
    get_timeout_records, call_llm_fix, run_on_simserver, update_db, ANTHROPIC_API_KEY
)

records = get_timeout_records()
rec = records[0]  # ID=21
print(f"Testing ID={rec['id']}, res={rec.get('resolution')}")
print(f"original_code len={len(rec.get('original_code') or '')}")
print(f"ANTHROPIC_API_KEY set: {bool(ANTHROPIC_API_KEY)}")

# LLM fix
print("\nCalling LLM...")
fix_result = call_llm_fix(rec)
print(f"fix_type={fix_result['fix_type']}")
print(f"fix_desc={fix_result['fix_description'][:100]}")
print(f"fixed_code len={len(fix_result['fixed_code'])}")

if fix_result['fixed_code']:
    print("\nRunning on SimServer (adaptive mpirun)...")
    run_result = run_on_simserver(fix_result['fixed_code'], rec['id'])
    print(f"status={run_result['status']}")
    print(f"mpi_np_used={run_result.get('mpi_np_used', '?')}")
    print(f"run_time={run_result.get('run_time_sec', 0):.1f}s")
    print(f"message={run_result.get('message','')}")
    if run_result.get('stdout'):
        print(f"stdout={run_result['stdout'][:300]}")
    if run_result.get('stderr'):
        print(f"stderr={run_result['stderr'][:200]}")
    
    if run_result['status'] == 'success':
        update_db(rec['id'], 1, fix_result['fixed_code'], 
                  fix_result['fix_type'], fix_result['fix_description'],
                  run_result.get('run_time_sec', 0), run_result.get('mpi_np_used', 1))
        print("\n✅ DB updated: fix_worked=1")
    else:
        update_db(rec['id'], 0, fix_result['fixed_code'],
                  fix_result['fix_type'], fix_result['fix_description'],
                  run_result.get('run_time_sec', 0), run_result.get('mpi_np_used', 1))
        print("\n❌ DB updated: fix_worked=0 (fixed_code saved)")
else:
    print("No fixed_code generated")
