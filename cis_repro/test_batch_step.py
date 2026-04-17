"""배치 스크립트 단계별 테스트"""
import sys, json
from pathlib import Path

BASE    = Path(__file__).parent
NB_DIR  = Path(r"C:\Users\user\.openclaw\workspace\dev\cis_reproduce")
sys.path.insert(0, str(BASE))

from detector import classify_all, auto_fix_loop
from pipeline import _build_design_section, _build_full_code, pre_check_and_fix

# Freeform 파라미터 테스트
params = {
    "paper_id": "Freeform2022",
    "paper_title": "Freeform metasurface color router for deep submicron pixel image sensors",
    "material_name": "SiN", "n_material": 1.92,
    "SP_size": 0.6, "Layer_thickness": 0.6, "FL_thickness": 0.6,
    "EL_thickness": 0, "n_layers": 1, "resolution": 50,
    "focal_material": "Air", "design_type": "materialgrid",
    "weights_layer1": str(NB_DIR / "Freeform metasurface color router for deep submicron pixel image sensors" / "Layer1.txt").replace("\\","/"),
    "decay_by": "1e-4",
    "target_efficiency": {"R": 0.45, "G": 0.45, "B": 0.45},
    "has_code": False, "has_structure": True,
}

# 가중치 파일 존재 확인
wpath = Path(params["weights_layer1"])
print(f"weights_layer1: {wpath.exists()} | {wpath}")

# 설계 섹션 생성
print("\n[설계 섹션 생성]")
try:
    ds = _build_design_section(params)
    print(f"  OK ({len(ds)}자)")
    print(ds[:200])
except Exception as e:
    print(f"  ERROR: {e}")
    sys.exit(1)

# 전체 코드 생성
out_dir = BASE / "results" / "Freeform2022"
out_dir.mkdir(parents=True, exist_ok=True)
print("\n[전체 코드 생성]")
try:
    code = _build_full_code(params, "Freeform2022", ds, out_dir)
    print(f"  OK ({len(code.splitlines())}줄)")
except Exception as e:
    print(f"  ERROR: {e}")
    sys.exit(1)

# Detector 사전 검사
print("\n[Detector 사전 검사]")
issues = classify_all(code, "", {})
if issues:
    print(f"  탐지: {[r.error_id for r in issues]}")
    code_fixed, applied = auto_fix_loop(code)
    print(f"  수정: {applied}")
else:
    print("  이슈 없음")
    code_fixed = code

# 저장
script = out_dir / "reproduce_Freeform2022.py"
script.write_text(code_fixed, encoding="utf-8")
print(f"\n[저장] {script} ({len(code_fixed.splitlines())}줄)")
print("DONE")
