# -*- coding: utf-8 -*-
"""Orchestrator: copy + run TypeE fixed scripts in batches of 4"""
import subprocess
import os
import sys
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

WORKDIR = r"C:\Users\user\projects\meep-kb"
WORKER = "meep-pilot-worker"
PYTHON = "/opt/conda/envs/mp/bin/python3"
TIMEOUT = 120  # seconds per script

TYPEE_IDS = [336,339,340,342,349,352,358,362,368,386,388,395,397,399,403,411,
             507,510,511,514,522,525,533,537,544,570,572,579,581,583,588,599,601]

results = {"success": [], "failed": [], "timeout": []}
log_lines = []

def log(msg):
    print(msg)
    log_lines.append(msg)

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
        return eid, "timeout", "Process timed out after 120s"


log(f"TypeE Orchestrator - {len(TYPEE_IDS)} scripts")
log(f"Worker: {WORKER}, Timeout: {TIMEOUT}s")
log("=" * 60)

batch_size = 4
total_batches = (len(TYPEE_IDS) + batch_size - 1) // batch_size

for batch_num in range(total_batches):
    batch_ids = TYPEE_IDS[batch_num * batch_size : (batch_num + 1) * batch_size]
    log(f"\nBatch {batch_num + 1}/{total_batches}: IDs {batch_ids}")
    
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
                elif status == "cp_failed":
                    log(f"  [CP_FAIL] ID {eid_res}: {output[:100]}")
                    results["failed"].append(eid_res)
                else:
                    log(f"  [FAIL] ID {eid_res} (exit={status})")
                    # Show last 3 lines of output
                    err_lines = [l for l in output.split('\n') if l.strip()][-5:]
                    for l in err_lines:
                        log(f"    {l}")
                    results["failed"].append(eid_res)
                    
                    # Save full error to file
                    err_path = os.path.join(WORKDIR, f"typee_err_{eid_res}.txt")
                    with open(err_path, "w", encoding="utf-8") as f:
                        f.write(output)
            except Exception as e:
                log(f"  [EXCEPTION] ID {eid}: {e}")
                results["failed"].append(eid)

log("\n" + "=" * 60)
log(f"SUMMARY:")
log(f"  Success: {len(results['success'])} - {results['success']}")
log(f"  Failed:  {len(results['failed'])} - {results['failed']}")
log(f"  Timeout: {len(results['timeout'])} - {results['timeout']}")

# Save log
log_path = os.path.join(WORKDIR, "typee_run_log.txt")
with open(log_path, "w", encoding="utf-8") as f:
    f.write('\n'.join(log_lines))

# Save results JSON
results_path = os.path.join(WORKDIR, "typee_run_results.json")
with open(results_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to {results_path}")
print(f"Log saved to {log_path}")
