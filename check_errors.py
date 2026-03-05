import json
data = json.load(open('/root/autosim/run_summary.json'))
failed = [d for d in data if d['status'] in ('error', 'timeout')]
print("=== FAILED/TIMEOUT PATTERNS ===")
print("Total failed:", len(failed))
print()
for d in failed:
    err = str(d.get('error',''))[:150]
    print("[{}] {}".format(d['status'].upper(), d['pattern']))
    print("  -> " + err)
    print()
