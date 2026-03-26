import subprocess, json
r = subprocess.run(["docker", "inspect", "meep-kb-meep-kb-1", "--format", "{{json .Mounts}}"],
                   capture_output=True, text=True)
mounts = json.loads(r.stdout)
for m in mounts:
    print(f"  {m.get('Source','?')} -> {m.get('Destination','?')} ({m.get('Type','?')})")
