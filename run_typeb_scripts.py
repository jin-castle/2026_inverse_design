# -*- coding: utf-8 -*-
"""Run TypeB_truncated fixed scripts"""
import subprocess
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

WORKDIR = r"C:\Users\user\projects\meep-kb"
WORKER = "meep-pilot-worker"
PYTHON = "/opt/conda/envs/mp/bin/python3"
TIMEOUT = 300  # 5 min

# Built TypeB IDs
TYPEB_IDS = [412, 428, 569, 597, 598]

results = {"success": [], "failed": [], "timeout": [], "skipped": [269]}

def log(msg):
    print(msg, flush=True)

def run_one(eid):
    src = os.path.join(WORKDIR, f"typeb_fixed_{eid}.py")
    dst = f"/tmp/typeb_{eid}.py"
    
    cp_result = subprocess.run(
        ["docker", "cp", src, f"{WORKER}:{dst}"],
        capture_output=True, text=True, timeout=30
    )
    if cp_result.returncode != 0:
        return eid, "cp_failed", cp_result.stderr
    
    try:
        run_result = subprocess.run(
            ["docker", "exec", WORKER, PYTHON, dst],
            capture_output=True, text=True, timeout=TIMEOUT
        )
        output = run_result.stdout + run_result.stderr
        return eid, run_result.returncode, output
    except subprocess.TimeoutExpired:
        return eid, "timeout", f"Timed out after {TIMEOUT}s"


log(f"Running TypeB_truncated IDs: {TYPEB_IDS}")
log(f"Skipping ID 269 (library file)")

# Run 2 at a time (to not overwhelm the worker)
batch_size = 2
for i in range(0, len(TYPEB_IDS), batch_size):
    batch = TYPEB_IDS[i:i+batch_size]
    log(f"\nBatch {i//batch_size + 1}: {batch}")
    
    with ThreadPoolExecutor(max_workers=batch_size) as executor:
        futures = {executor.submit(run_one, eid): eid for eid in batch}
        for future in as_completed(futures):
            eid = futures[future]
            try:
                eid_res, status, output = future.result()
                if status == 0:
                    log(f"  [OK] ID {eid_res}")
                    results["success"].append(eid_res)
                elif status == "timeout":
                    log(f"  [TIMEOUT] ID {eid_res}")
                    results["timeout"].append(eid_res)
                else:
                    log(f"  [FAIL] ID {eid_res} (exit={status})")
                    err_lines = [l for l in output.split('\n') if l.strip()][-6:]
                    for l in err_lines:
                        log(f"    {l}")
                    results["failed"].append(eid_res)
                    with open(os.path.join(WORKDIR, f"typeb_err_{eid_res}.txt"), "w", encoding="utf-8") as f:
                        f.write(output)
            except Exception as e:
                log(f"  [EXCEPTION] ID {eid}: {e}")

log(f"\nTypB done. Success: {results['success']}, Failed: {results['failed']}, Timeout: {results['timeout']}")
results_path = os.path.join(WORKDIR, "typeb_run_results.json")
with open(results_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
log(f"Saved: {results_path}")
