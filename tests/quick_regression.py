# -*- coding: utf-8 -*-
"""Quick regression test (10 critical cases only)"""
import sys, json, time, requests
sys.stdout.reconfigure(encoding='utf-8')

KB = "http://localhost:8765"

CASES = [
    ("C2_PML_center", "TypeError PML got unexpected keyword argument center", ["PML","thickness"], []),
    ("C4_DPW_kwarg",  "DiffractedPlanewave unexpected keyword argument orders grating_vec", ["DiffractedPlanewave","positional"], ["PML"]),
    ("C5_flux_minus", "T+R 2.0 energy conservation violation load_minus_flux_data", ["load_minus_flux","normalization"], []),
    ("C6_eig_band",   "eig_band 0 eigenmode MEEP 1-based indexing", ["eig_band","band"], []),
    ("ML2_U_SUM",     "MaterialGrid grid_type U_SUM ValueError invalid MEEP 1.31", ["U_DEFAULT","MaterialGrid"], []),
    ("ML3_Source_kw", "mp.Source positional args AttributeError Vector3 center", ["keyword","center"], []),
    ("ML1_cyl_m0",    "zone plate cylindrical MEEP m=0 no focusing", ["m=-1","cylindrical"], []),
    ("ML5_beta_zero", "adjoint metalens final efficiency 0.0 binarized design beta", ["beta","binarize"], []),
    ("ADJ1_grad_2x",  "adjoint gradient finite difference ratio 2.0 chain rule", ["gradient","chain rule"], []),
    ("MPI1_slot",     "mpirun slots error previous process not terminated pkill", ["pkill","mpirun"], ["gradient"]),
]

passed = 0
for cid, query, expected, must_not in CASES:
    try:
        r = requests.post(f"{KB}/api/diagnose", json={"error": query, "n": 3}, timeout=15)
        data = r.json()
        sug = data.get("suggestions", [])
        text = " ".join(
            s.get("title","") + " " + str(s.get("solution","")) + " " + str(s.get("cause",""))
            for s in sug
        ).lower()
        found = [kw for kw in expected if kw.lower() in text]
        fp = [kw for kw in must_not if kw.lower() in text[:300]]
        score = len(found)/max(len(expected),1) - 0.2*len(fp)
        ok = score >= 0.5 and not fp
        if ok: passed += 1
        top = sug[0].get("title","NO RESULT")[:50] if sug else "NO RESULT"
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {cid:20s} score={score:.2f} | {top}")
        if not ok:
            print(f"       Missing: {[k for k in expected if k.lower() not in text]}")
        time.sleep(0.3)
    except Exception as e:
        print(f"[ERROR] {cid}: {e}")

print(f"\n=== {passed}/{len(CASES)} PASS ({passed/len(CASES)*100:.0f}%) ===")

# Save
import pathlib
result = {"passed": passed, "total": len(CASES), "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}
pathlib.Path("tests/regression_result_latest.json").write_text(json.dumps(result, indent=2))
print("Saved: tests/regression_result_latest.json")
