# -*- coding: utf-8 -*-
"""Final retry for fixed TypeE scripts"""
import subprocess
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

WORKDIR = r"C:\Users\user\projects\meep-kb"
WORKER = "meep-pilot-worker"
PYTHON = "/opt/conda/envs/mp/bin/python3"
TIMEOUT = 300  # 5 min - longer for Mie scattering

# These have been newly fixed
FINAL_IDS = [368, 544, 411, 601]

results = {"success": [], "failed": []}

def log(msg):
    print(msg, flush=True)

def run_one(eid):
    src = os.path.join(WORKDIR, f"typee_fixed_{eid}.py")
    dst = f"/tmp/typee_{eid}.py"
    
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
        return eid, "timeout", f"Process timed out after {TIMEOUT}s"


log(f"Final retry: {FINAL_IDS}")

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(run_one, eid): eid for eid in FINAL_IDS}
    
    for future in as_completed(futures):
        eid = futures[future]
        try:
            eid_res, status, output = future.result()
            
            if status == 0:
                log(f"  [OK] ID {eid_res}")
                results["success"].append(eid_res)
            elif status == "timeout":
                log(f"  [TIMEOUT] ID {eid_res}")
                results["failed"].append({"id": eid_res, "reason": "timeout"})
            else:
                log(f"  [FAIL] ID {eid_res} (exit={status})")
                err_lines = [l for l in output.split('\n') if l.strip()][-6:]
                for l in err_lines:
                    log(f"    {l}")
                results["failed"].append({"id": eid_res, "reason": str(status)})
                with open(os.path.join(WORKDIR, f"typee_err_{eid_res}.txt"), "w", encoding="utf-8") as f:
                    f.write(output)
        except Exception as e:
            log(f"  [EXCEPTION] ID {eid}: {e}")

log(f"Success: {results['success']}")
log(f"Failed: {results['failed']}")

results_path = os.path.join(WORKDIR, "typee_final_results.json")
with open(results_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
log(f"Saved: {results_path}")
