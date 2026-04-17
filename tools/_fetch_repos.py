"""EIDL 레포 코드 수집 → meep-kb patterns 삽입"""
import subprocess, sqlite3, base64, json
from pathlib import Path

DB_PATH = Path("db/knowledge.db")

def gh_file(repo, path):
    r = subprocess.run(
        ["gh", "api", f"repos/nanophotonics-lab/{repo}/contents/{path}", "--jq", ".content"],
        capture_output=True, text=True, timeout=20
    )
    if r.returncode != 0:
        return None
    raw = r.stdout.strip().replace("\\n","").replace("\n","")
    try:
        return base64.b64decode(raw).decode("utf-8", errors="replace")
    except Exception as e:
        return None

def gh_dir(repo, path=""):
    r = subprocess.run(
        ["gh", "api", f"repos/nanophotonics-lab/{repo}/contents/{path}", "--jq", "[.[] | {name:.name, type:.type, path:.path}]"],
        capture_output=True, text=True, timeout=20
    )
    if r.returncode != 0:
        return []
    return json.loads(r.stdout.strip())

# 수집 대상
TARGETS = [
    ("Samsung_CIS", "final_code/samsung_adam_multi_layer_9pp_PEC_freeform_TiO2.py"),
    ("2023-Corning-AI-Challenge", "iteration.py"),
    ("2023-Corning-AI-Challenge", "model.py"),
    ("LNOI-KIST", "Mode-converter/Optimization.py"),
    ("LNOI-KIST", "Mode-converter/Sub_Mapping.py"),
    ("Adjoint-FNO", "iteration.py"),
    ("surrogate-solver", "main.py"),
    ("Chiral_metasurface", "3d_adjoint_chiral_meta.py"),
    ("inverse-design-of-ultrathin-metamaterial-absorber", "2D-absorber-adjoint-optimization"),
    ("PSO-absorber", "pso.py"),
    ("2025-Large_scale_metalens", "250717_Cylindrical_metalens_reproduce_z_averaging_GLC.py"),
    ("shape_optimization", "chanik_ver/shapeopt.py"),
    ("grayscale_penalizer", "grating"),
    ("Oblique_Planewave", "README.md"),
    ("meep_python", "adjoint_optimization_examples"),
]

results = {}
for repo, path in TARGETS:
    print(f"Fetching {repo}/{path}...")
    code = gh_file(repo, path)
    if code:
        results[f"{repo}/{path}"] = code[:5000]
        print(f"  OK ({len(code)} chars)")
    else:
        items = gh_dir(repo, path)
        if items:
            for item in items[:5]:
                if item["type"] == "file" and item["name"].endswith(".py"):
                    c = gh_file(repo, item["path"])
                    if c:
                        results[f"{repo}/{item['path']}"] = c[:5000]
                        print(f"  OK dir item: {item['name']} ({len(c)} chars)")

# 저장
Path("tools/_eidl_codes.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print(f"\nTotal collected: {len(results)} files")
