# -*- coding: utf-8 -*-
"""Submit newly completed TypeE examples"""
import subprocess
import json
import os

WORKDIR = r"C:\Users\user\projects\meep-kb"
KB_CONTAINER = "meep-kb-meep-kb-1"
WORKER = "meep-pilot-worker"

NEW_IDS = [397, 511, 581]  # Newly completed

def log(msg):
    print(msg, flush=True)

def get_images_in_worker(eid, prefix="typee"):
    check = subprocess.run(
        ["docker", "exec", WORKER, "bash", "-c", 
         f"ls /tmp/kb_results/{prefix}_{eid}_*.png 2>/dev/null || true"],
        capture_output=True, text=True
    )
    if check.stdout.strip():
        return sorted(check.stdout.strip().split('\n'))
    return []

def submit_example(eid, img_files, prefix="typee"):
    # Copy images: worker -> local -> KB container
    for img_file in img_files:
        fname = os.path.basename(img_file)
        local_tmp = os.path.join(WORKDIR, fname)
        subprocess.run(["docker", "cp", f"{WORKER}:{img_file}", local_tmp], capture_output=True)
        subprocess.run(["docker", "cp", local_tmp, f"{KB_CONTAINER}:/tmp/kb_results/{fname}"], capture_output=True)
    
    img_pattern = f"/tmp/kb_results/{prefix}_{eid}_*.png"
    script = f"""# -*- coding: utf-8 -*-
import requests, base64, glob
imgs = []
for f in sorted(glob.glob({repr(img_pattern)})):
    imgs.append(base64.b64encode(open(f,'rb').read()).decode())
r = requests.post('http://meep-kb-meep-kb-1:7860/api/ingest/result',
    json={{'example_id': {eid}, 'images': imgs, 'stdout': 'notebook markdown stripped and re-run', 'status': 'success'}}, timeout=60)
print(f"ID {eid}: {{r.status_code}} - {{r.text[:200]}}")
"""
    
    script_path = os.path.join(WORKDIR, f"submit_{eid}.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    
    subprocess.run(["docker", "cp", script_path, f"{KB_CONTAINER}:/tmp/submit_{eid}.py"], capture_output=True)
    result = subprocess.run(
        ["docker", "exec", KB_CONTAINER, "python3", f"/tmp/submit_{eid}.py"],
        capture_output=True, text=True, timeout=60
    )
    return result.returncode, (result.stdout + result.stderr).strip()

subprocess.run(["docker", "exec", KB_CONTAINER, "mkdir", "-p", "/tmp/kb_results"], capture_output=True)

submitted = []
for eid in NEW_IDS:
    imgs = get_images_in_worker(eid)
    if not imgs:
        log(f"  TypeE {eid}: no images yet")
        continue
    rc, out = submit_example(eid, imgs)
    if rc == 0:
        submitted.append(eid)
        log(f"  TypeE {eid}: OK - {out[:100]}")
    else:
        log(f"  TypeE {eid}: FAIL - {out[:100]}")

log(f"\nSubmitted: {submitted}")
