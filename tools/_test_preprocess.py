import sys, re
sys.path.insert(0, 'tools')
from run_concept_demos import preprocess_code

tests = [
    ("FluxRegion", "plt.savefig('output.png', dpi=100, bbox_inches='tight')"),
    ("Harminv",    "plt.savefig('output.png', dpi=120, bbox_inches='tight')"),
    ("bend",       "plt.savefig('output.png', dpi=100)"),
    ("DFT",        "plt.savefig('output.png', dpi=100)"),
]
for name, savefig_line in tests:
    code = f"import matplotlib\nmatplotlib.use('Agg')\nimport meep as mp\nimport matplotlib.pyplot as plt\n\n{savefig_line}\n"
    processed = preprocess_code(code, name)
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    target = f"/tmp/concept_{safe}.png"
    ok = target in processed
    print(f"{'✅' if ok else '❌'} {name}: {target in processed}")
    if not ok:
        for l in processed.splitlines():
            if 'savefig' in l:
                print(f"   savefig: {l}")
