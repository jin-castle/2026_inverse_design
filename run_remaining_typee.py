# -*- coding: utf-8 -*-
"""Run remaining TypeE IDs that haven't been run yet"""
import subprocess
import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

WORKDIR = r"C:\Users\user\projects\meep-kb"
WORKER = "meep-pilot-worker"
PYTHON = "/opt/conda/envs/mp/bin/python3"
TIMEOUT = 150  # seconds per script

# IDs not yet run
REMAINING_IDS = [336, 368, 395, 397, 403, 411, 533, 544, 588, 599, 601]

results = {"success": [], "failed": [], "timeout": []}

def log(msg):
    print(msg, flush=True)

def run_one(eid):
    src = os.path.join(WORKDIR, f"typee_fixed_{eid}.py")
    dst = f"/tmp/typee_{eid}.py"
    
    # Copy to worker
    cp_result = subprocess.run(
        ["docker", "cp", src, f"{WORKER}:{dst}"],
        capture_output=True, text=True, timeout=30
    )
    if cp_result.returncode != 0:
        return eid, "cp_failed", cp_result.stderr
    
    # Run in worker
    try:
        run_result = subprocess.run(
            ["docker", "exec", WORKER, PYTHON, dst],
            capture_output=True, text=True, timeout=TIMEOUT
        )
        output = run_result.stdout + run_result.stderr
        return eid, run_result.returncode, output
    except subprocess.TimeoutExpired:
        return eid, "timeout", f"Process timed out after {TIMEOUT}s"


log(f"Running {len(REMAINING_IDS)} remaining TypeE scripts")
log(f"IDs: {REMAINING_IDS}")

batch_size = 4
total_batches = (len(REMAINING_IDS) + batch_size - 1) // batch_size

for batch_num in range(total_batches):
    batch_ids = REMAINING_IDS[batch_num * batch_size : (batch_num + 1) * batch_size]
    log(f"\nBatch {batch_num + 1}/{total_batches}: {batch_ids}")
    
    with ThreadPoolExecutor(max_workers=batch_size) as executor:
        futures = {executor.submit(run_one, eid): eid for eid in batch_ids}
        
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
                    err_lines = [l for l in output.split('\n') if l.strip()][-5:]
                    for l in err_lines:
                        log(f"    {l}")
                    results["failed"].append(eid_res)
                    err_path = os.path.join(WORKDIR, f"typee_err_{eid_res}.txt")
                    with open(err_path, "w", encoding="utf-8") as f:
                        f.write(output)
            except Exception as e:
                log(f"  [EXCEPTION] ID {eid}: {e}")
                results["failed"].append(eid)

log(f"\nRemaining batch done.")
log(f"Success: {results['success']}")
log(f"Failed: {results['failed']}")
log(f"Timeout: {results['timeout']}")

# Save partial results
results_path = os.path.join(WORKDIR, "typee_remaining_results.json")
with open(results_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
log(f"Results saved to {results_path}")
