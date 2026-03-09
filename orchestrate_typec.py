#!/usr/bin/env python3
"""
Orchestrate TypeC MPI simulations: 2 at a time, 16 cores each, 600s timeout.
Handles docker cp, exec, result checking, and API submission.
"""
import subprocess
import time
import os
import json
import base64
import sys
import io

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJ = r"C:\Users\user\projects\meep-kb"
IDS = [333,341,353,375,378,381,389,400,505,513,526,528,539,548,554,559,562,573,575,592]
TIMEOUT = 600
BATCH_SIZE = 2
API_URL = "http://meep-kb-meep-kb-1:7860/api/ingest/result"

results = {"successful": [], "timeout": [], "errors": []}

def run(cmd, capture=True, timeout=30):
    """Run a shell command."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=capture, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", -1

def log(msg, level="INFO"):
    prefix = {"INFO": "+", "WARN": "!", "ERROR": "X", "BATCH": "="}.get(level, " ")
    print(f"[{prefix}] {msg}", flush=True)

def docker_cp_to(local_path, remote_path):
    out, err, rc = run(f'docker cp "{local_path}" meep-pilot-worker:{remote_path}')
    return rc == 0

def docker_exec_detached(cmd):
    """Run command in background in container."""
    full_cmd = f'docker exec -d meep-pilot-worker bash -c "{cmd}"'
    out, err, rc = run(full_cmd)
    return rc == 0

def docker_exec_check(cmd, timeout=10):
    out, err, rc = run(f'docker exec meep-pilot-worker bash -c "{cmd}"', timeout=timeout)
    return out, err, rc

def is_running(eid):
    """Check if simulation for eid is still running."""
    out, _, _ = docker_exec_check(f"pgrep -f 'typec_{eid}\\.py' 2>/dev/null | head -1", timeout=10)
    return bool(out.strip())

def kill_sim(eid):
    docker_exec_check(f"pkill -f 'typec_{eid}\\.py' 2>/dev/null; true", timeout=10)

def get_log(eid):
    out, _, _ = docker_exec_check(f"tail -30 /tmp/typec_{eid}.log 2>/dev/null", timeout=10)
    return out

def get_images(eid):
    out, _, rc = docker_exec_check(f"ls /tmp/kb_results/typec_{eid}_*.png 2>/dev/null", timeout=10)
    if rc == 0 and out.strip():
        return [p.strip() for p in out.strip().split('\n') if p.strip().endswith('.png')]
    return []

def has_error(eid):
    out, _, _ = docker_exec_check(f"grep -i 'Traceback\\|Error\\|Exception' /tmp/typec_{eid}.log 2>/dev/null | tail -3", timeout=10)
    return out.strip()

# Step 1: Copy all scripts to container first
log("Copying all 20 fixed scripts to container...", "BATCH")
copy_ok = []
copy_fail = []
for eid in IDS:
    src = os.path.join(PROJ, f"typec_fixed_{eid}.py")
    if not os.path.exists(src):
        log(f"Source not found: {src}", "ERROR")
        results["errors"].append({"id": eid, "reason": "source file not found"})
        copy_fail.append(eid)
        continue
    if docker_cp_to(src, f"/tmp/typec_{eid}.py"):
        log(f"Copied ID {eid}")
        copy_ok.append(eid)
    else:
        log(f"Copy failed for ID {eid}", "ERROR")
        results["errors"].append({"id": eid, "reason": "docker cp failed"})
        copy_fail.append(eid)

log(f"Copy done: {len(copy_ok)} OK, {len(copy_fail)} failed", "BATCH")

# Filter to only IDs that copied successfully
run_ids = [eid for eid in IDS if eid in copy_ok]

# Ensure results dir exists in container
docker_exec_check("mkdir -p /tmp/kb_results")

# Step 2: Run in batches of 2
batches = [run_ids[i:i+BATCH_SIZE] for i in range(0, len(run_ids), BATCH_SIZE)]
log(f"Running {len(run_ids)} simulations in {len(batches)} batches of {BATCH_SIZE}", "BATCH")

for batch_num, batch in enumerate(batches):
    log(f"\n{'='*50}", "BATCH")
    log(f"BATCH {batch_num+1}/{len(batches)}: IDs {batch}", "BATCH")
    log(f"{'='*50}", "BATCH")
    
    started = []
    for eid in batch:
        mpi_cmd = (
            f"/usr/bin/mpirun --allow-run-as-root -np 16 "
            f"/opt/conda/envs/mp/bin/python3 /tmp/typec_{eid}.py "
            f"> /tmp/typec_{eid}.log 2>&1"
        )
        if docker_exec_detached(mpi_cmd):
            log(f"Started simulation {eid} (16 MPI cores)")
            started.append(eid)
        else:
            log(f"Failed to start simulation {eid}", "ERROR")
            results["errors"].append({"id": eid, "reason": "failed to start docker exec"})
    
    if not started:
        log("No simulations started in this batch, skipping wait", "WARN")
        continue
    
    # Wait with periodic check-ins every 60s
    log(f"Waiting up to {TIMEOUT}s for batch {batch_num+1}...")
    start_time = time.time()
    still_running = list(started)
    
    while still_running and (time.time() - start_time) < TIMEOUT:
        elapsed = time.time() - start_time
        time.sleep(60)
        elapsed = time.time() - start_time
        
        # Check which ones are done
        just_finished = []
        for eid in still_running:
            if not is_running(eid):
                just_finished.append(eid)
                log(f"  ID {eid} completed at {elapsed:.0f}s")
        
        for eid in just_finished:
            still_running.remove(eid)
        
        if still_running:
            log(f"  Still running at {elapsed:.0f}s: {still_running}")
        else:
            log(f"  All done at {elapsed:.0f}s!")
    
    # Kill any that are still running (timeout)
    for eid in still_running:
        log(f"TIMEOUT: Killing {eid} after {TIMEOUT}s", "WARN")
        kill_sim(eid)
        results["timeout"].append(eid)
    
    # Check results for completed simulations
    completed = [eid for eid in started if eid not in still_running]
    for eid in completed:
        log(f"\nChecking results for ID {eid}:")
        log_tail = get_log(eid)
        imgs = get_images(eid)
        err = has_error(eid)
        
        if err:
            log(f"  ERROR in {eid}: {err[:200]}", "ERROR")
            results["errors"].append({"id": eid, "reason": err[:300]})
        elif imgs:
            log(f"  SUCCESS: {eid} produced {len(imgs)} image(s): {imgs}")
            results["successful"].append(eid)
        else:
            # Check log for any output
            if log_tail and "error" not in log_tail.lower() and "exception" not in log_tail.lower():
                log(f"  COMPLETED (no images): {eid} - may not produce plots", "WARN")
                results["successful"].append(eid)
            else:
                log(f"  FAILED (no images, check log): {eid}", "ERROR")
                results["errors"].append({"id": eid, "reason": f"no images; log: {log_tail[-200:] if log_tail else 'empty'}"})

log("=" * 50, "BATCH")
log("ALL BATCHES DONE", "BATCH")
log(f"Successful: {results['successful']}")
log(f"Timeout:    {results['timeout']}")
log(f"Errors:     {[e['id'] if isinstance(e, dict) else e for e in results['errors']]}")

# Save preliminary results
with open(os.path.join(PROJ, "agent2b_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
log("Saved preliminary results to agent2b_results.json")

# Step 3: Submit results to API for successful ones that have images
log("=" * 50, "BATCH")
log("SUBMITTING RESULTS TO meep-kb API", "BATCH")

submitted_ok = []
submitted_fail = []

for eid in results["successful"]:
    imgs = get_images(eid)
    log_content, _, _ = docker_exec_check(f"tail -2000c /tmp/typec_{eid}.log 2>/dev/null", timeout=15)
    
    if not imgs:
        log(f"  {eid}: no images to submit, skipping API call")
        continue
    
    # Write submit script
    submit_code = f'''import requests, base64, glob
imgs = []
for f in sorted(glob.glob('/tmp/kb_results/typec_{eid}_*.png')):
    imgs.append(base64.b64encode(open(f,'rb').read()).decode())
if imgs:
    r = requests.post(
        'http://meep-kb-meep-kb-1:7860/api/ingest/result',
        json={{'example_id': {eid}, 'images': imgs,
               'stdout': open('/tmp/typec_{eid}.log').read()[-2000:],
               'status': 'success'}},
        timeout=60
    )
    print(r.status_code, r.text[:200])
else:
    print("no images")
'''
    submit_path = os.path.join(PROJ, f"submit_{eid}.py")
    with open(submit_path, "w", encoding="utf-8") as f:
        f.write(submit_code)
    
    if docker_cp_to(submit_path, f"/tmp/submit_{eid}.py"):
        out, err, rc = run(
            f"docker exec meep-pilot-worker /opt/conda/envs/mp/bin/python3 /tmp/submit_{eid}.py",
            timeout=90
        )
        if rc == 0:
            log(f"  Submitted {eid}: {out[:100]}")
            submitted_ok.append(eid)
        else:
            log(f"  Submit FAILED {eid}: {err[:100]}", "WARN")
            submitted_fail.append(eid)
    else:
        log(f"  Could not copy submit script for {eid}", "ERROR")
        submitted_fail.append(eid)

log(f"\nSubmission: {len(submitted_ok)} OK, {len(submitted_fail)} failed")

# Final results save
results["api_submitted"] = submitted_ok
results["api_submit_failed"] = submitted_fail
with open(os.path.join(PROJ, "agent2b_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

log("=" * 50, "BATCH")
log("ORCHESTRATION COMPLETE", "BATCH")
log(f"Successful simulations: {len(results['successful'])}")
log(f"Timeouts:               {len(results['timeout'])}")
log(f"Errors:                 {len(results['errors'])}")
log(f"API submitted:          {len(submitted_ok)}")
log(f"Results at: {os.path.join(PROJ, 'agent2b_results.json')}")
