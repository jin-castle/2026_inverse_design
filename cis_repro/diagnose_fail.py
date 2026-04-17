import sys, re
sys.path.insert(0, 'C:/Users/user/projects/meep-kb/cis_repro')
from detector import RULE_MAP

BASELINE = open('C:/Users/user/projects/meep-kb/cis_repro/results/_final_verify/bl.py', encoding='utf-8').read()

for rid in ['CIS-EFF-003', 'CIS-EFF-004']:
    rule = RULE_MAP[rid]
    print(f"=== {rid} {rule.error_id} ===")
    print(f"  Baseline FP: {rule.detect(BASELINE, '', {})}")

    fname = f"C:/Users/user/projects/meep-kb/cis_repro/results/_final_verify/{rid.replace('-','_')}.py"
    try:
        buggy = open(fname, encoding='utf-8').read()
    except FileNotFoundError:
        print(f"  [MISS] {fname}")
        continue

    r_buggy = rule.detect(buggy, '', {})
    fixed   = rule.fix(buggy)
    r_fixed = rule.detect(fixed, '', {})

    print(f"  Buggy detect: {r_buggy}")
    print(f"  Fixed detect (still?): {r_fixed}")
    print(f"  Fix changed code: {fixed != buggy}")

    print("  [buggy 관련]")
    for line in buggy.splitlines():
        if any(k in line for k in ['add_flux','tran_gb','greenb','load_minus','sim.run','sim_ref']):
            print(f"    {line[:90]!r}")
    print("  [fixed 관련]")
    for line in fixed.splitlines():
        if any(k in line for k in ['add_flux','tran_gb','greenb','load_minus','sim.run','AUTO-FIX']):
            print(f"    {line[:90]!r}")
    print()
