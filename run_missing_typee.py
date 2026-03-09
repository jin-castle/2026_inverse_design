# -*- coding: utf-8 -*-
"""Run TypeE scripts that were missing or need rerun with plt.show() fixed"""
import subprocess
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

WORKDIR = r"C:\Users\user\projects\meep-kb"
WORKER = "meep-pilot-worker"
PYTHON = "/opt/conda/envs/mp/bin/python3"
TIMEOUT = 180

# These have been updated with plt.show() and need to be run
# Note: They're at /tmp/typee_{id}_fixed.py in the worker
IDS_TO_RUN = [342, 349, 403, 514, 522, 588]

results = {"success": [], "failed": [], "timeout": []}

def log(msg):
    print(msg, flush=True)

def run_one(eid):
    # Script already copied as typee_{id}_fixed.py
    dst = f"/tmp/typee_{eid}_fixed.py"
    
    try:
        run_result = subprocess.run(
            ["docker", "exec", WORKER, PYTHON, dst],
            capture_output=True, text=True, timeout=TIMEOUT
        )
        output = run_result.stdout + run_result.stderr
        return eid, run_result.returncode, output
    except subprocess.TimeoutExpired:
        return eid, "timeout", f"Timed out after {TIMEOUT}s"


log(f"Running {len(IDS_TO_RUN)} fixed TypeE scripts: {IDS_TO_RUN}")

batch_size = 3
for i in range(0, len(IDS_TO_RUN), batch_size):
    batch = IDS_TO_RUN[i:i+batch_size]
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
                    err_lines = [l for l in output.split('\n') if l.strip()][-5:]
                    for l in err_lines:
                        log(f"    {l}")
                    results["failed"].append(eid_res)
            except Exception as e:
                log(f"  [EXCEPTION] ID {eid}: {e}")

log(f"\nDone. Success: {results['success']}, Failed: {results['failed']}, Timeout: {results['timeout']}")

with open(os.path.join(WORKDIR, "missing_typee_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
log("Saved results")
