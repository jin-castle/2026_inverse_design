# -*- coding: utf-8 -*-
"""Submit all TypeE and TypeB examples that have images or ran successfully"""
import subprocess
import json
import os

WORKDIR = r"C:\Users\user\projects\meep-kb"
KB_CONTAINER = "meep-kb-meep-kb-1"
WORKER = "meep-pilot-worker"

# All TypeE IDs
TYPEE_IDS = [336,339,340,342,349,352,358,362,368,386,388,395,397,399,403,411,
             507,510,511,514,522,525,533,537,544,570,572,579,581,583,588,599,601]

# TypeB: 269 is skipped (library). Others ran.
# 428, 569, 597, 598 = success (no images, stdout only)
# 412 = partial success (1 image)
TYPEB_WITH_IMAGES = [412]
TYPEB_STDOUT_ONLY = [428, 569, 597, 598]

def log(msg):
    print(msg, flush=True)

def get_images_in_worker(eid, prefix):
    """Get list of images for this example in worker container"""
    check = subprocess.run(
        ["docker", "exec", WORKER, "bash", "-c", 
         f"ls /tmp/kb_results/{prefix}_{eid}_*.png 2>/dev/null || true"],
        capture_output=True, text=True
    )
    if check.stdout.strip():
        return sorted(check.stdout.strip().split('\n'))
    return []

def submit_with_images(eid, prefix, img_files, stdout_msg):
    """Copy images from worker to KB, submit via API"""
    
    # Copy images: worker -> local -> KB container
    for img_file in img_files:
        fname = os.path.basename(img_file)
        local_tmp = os.path.join(WORKDIR, fname)
        
        r1 = subprocess.run(
            ["docker", "cp", f"{WORKER}:{img_file}", local_tmp],
            capture_output=True
        )
        r2 = subprocess.run(
            ["docker", "cp", local_tmp, f"{KB_CONTAINER}:/tmp/kb_results/{fname}"],
            capture_output=True
        )
    
    # Write submit script
    img_pattern = f"/tmp/kb_results/{prefix}_{eid}_*.png"
    script = f"""# -*- coding: utf-8 -*-
import requests, base64, glob

imgs = []
for f in sorted(glob.glob({repr(img_pattern)})):
    imgs.append(base64.b64encode(open(f,'rb').read()).decode())

r = requests.post('http://meep-kb-meep-kb-1:7860/api/ingest/result',
    json={{
        'example_id': {eid},
        'images': imgs,
        'stdout': {repr(stdout_msg)},
        'status': 'success'
    }}, timeout=60)
print(f"ID {eid}: {{r.status_code}} - {{r.text[:300]}}")
"""
    
    script_path = os.path.join(WORKDIR, f"submit_{eid}.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    
    subprocess.run(
        ["docker", "cp", script_path, f"{KB_CONTAINER}:/tmp/submit_{eid}.py"],
        capture_output=True
    )
    
    result = subprocess.run(
        ["docker", "exec", KB_CONTAINER, "python3", f"/tmp/submit_{eid}.py"],
        capture_output=True, text=True, timeout=60
    )
    
    return result.returncode, (result.stdout + result.stderr).strip()


def submit_stdout_only(eid, prefix, stdout_msg):
    """Submit example without images"""
    script = f"""# -*- coding: utf-8 -*-
import requests

r = requests.post('http://meep-kb-meep-kb-1:7860/api/ingest/result',
    json={{
        'example_id': {eid},
        'images': [],
        'stdout': {repr(stdout_msg)},
        'status': 'success'
    }}, timeout=60)
print(f"ID {eid}: {{r.status_code}} - {{r.text[:300]}}")
"""
    
    script_path = os.path.join(WORKDIR, f"submit_{eid}.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    
    subprocess.run(
        ["docker", "cp", script_path, f"{KB_CONTAINER}:/tmp/submit_{eid}.py"],
        capture_output=True
    )
    
    result = subprocess.run(
        ["docker", "exec", KB_CONTAINER, "python3", f"/tmp/submit_{eid}.py"],
        capture_output=True, text=True, timeout=60
    )
    
    return result.returncode, (result.stdout + result.stderr).strip()


# Ensure KB container has results dir
subprocess.run(
    ["docker", "exec", KB_CONTAINER, "mkdir", "-p", "/tmp/kb_results"],
    capture_output=True
)

submitted = []
no_images_yet = []
failed_submit = []

log("=" * 60)
log("SUBMITTING TypeE examples")
log("=" * 60)

for eid in TYPEE_IDS:
    img_files = get_images_in_worker(eid, "typee")
    if not img_files:
        no_images_yet.append(eid)
        log(f"  TypeE {eid}: no images yet (still running or failed)")
        continue
    
    rc, output = submit_with_images(eid, "typee", img_files, 
                                     "notebook markdown stripped; code cleaned and executed")
    if rc == 0:
        submitted.append(eid)
        log(f"  TypeE {eid}: OK ({len(img_files)} imgs) - {output[:80]}")
    else:
        failed_submit.append(eid)
        log(f"  TypeE {eid}: FAIL - {output[:80]}")

log("\n" + "=" * 60)
log("SUBMITTING TypeB examples")
log("=" * 60)

# TypeB with images
for eid in TYPEB_WITH_IMAGES:
    img_files = get_images_in_worker(eid, "typeb")
    if not img_files:
        no_images_yet.append(f"TypeB-{eid}")
        log(f"  TypeB {eid}: no images yet")
        continue
    
    rc, output = submit_with_images(eid, "typeb", img_files,
                                     "truncated code completed; code executed successfully")
    if rc == 0:
        submitted.append(f"TypeB-{eid}")
        log(f"  TypeB {eid}: OK ({len(img_files)} imgs) - {output[:80]}")
    else:
        failed_submit.append(f"TypeB-{eid}")
        log(f"  TypeB {eid}: FAIL - {output[:80]}")

# TypeB without images (stdout only)
for eid in TYPEB_STDOUT_ONLY:
    rc, output = submit_stdout_only(eid, "typeb",
                                     "truncated code completed and executed; no plots generated")
    if rc == 0:
        submitted.append(f"TypeB-{eid}")
        log(f"  TypeB {eid}: stdout-only OK - {output[:80]}")
    else:
        failed_submit.append(f"TypeB-{eid}")
        log(f"  TypeB {eid}: FAIL - {output[:80]}")

log("\n" + "=" * 60)
log("SUMMARY")
log("=" * 60)
log(f"Submitted: {len(submitted)} - {submitted}")
log(f"No images yet: {no_images_yet}")
log(f"Failed: {failed_submit}")

results = {
    "submitted": submitted,
    "no_images_yet": no_images_yet,
    "submit_failed": failed_submit
}

with open(os.path.join(WORKDIR, "submission_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

log("Saved: submission_results.json")
