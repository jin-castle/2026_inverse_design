"""SMA bayer_config=sma 코드 즉시 생성 + 테스트"""
import sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# bayer_config=sma를 override에 추가해서 코드 생성
params = {
    "paper_id": "SMA2023_bayer_sma",
    "paper_title": "SMA — Bayer sma 배치 테스트",
    "material_name": "SiN", "n_material": 2.02,
    "SP_size": 1.12, "Layer_thickness": 1.0, "FL_thickness": 4.0,
    "EL_thickness": 0, "n_layers": 1, "resolution": 50,
    "focal_material": "SiO2", "design_type": "sparse",
    "sparse_pillars": [
        {"label":"R",  "wx":0.92,"wy":0.92,"cx":-0.56,"cy": 0.56},
        {"label":"G1", "wx":0.16,"wy":0.16,"cx":-0.56,"cy":-0.56},
        {"label":"G2", "wx":0.16,"wy":0.16,"cx": 0.56,"cy": 0.56},
        {"label":"B",  "wx":0.28,"wy":0.28,"cx": 0.56,"cy":-0.56},
    ],
    "target_efficiency": {"R":0.45,"G":0.35,"B":0.40},
    "has_code": False, "has_structure": True,
    # SMA 원본과 동일한 override
    "_override": {
        "stop_decay":    "1e-8",
        "cover_glass":   False,
        "ref_sim_type":  "air",
        "source_count":  2,
        "sipd_material": "SiO2",
        "bayer_config":  "sma",   # ← 핵심 변경
    }
}

# corrected_codegen의 build_corrected_code를 override 포함해 호출
from corrected_codegen import build_corrected_code

# ERROR_PATTERNS에 임시 등록
import json
ep_path = Path(__file__).parent / "error_patterns.json"
ep = json.loads(ep_path.read_text(encoding="utf-8"))
ep["paper_specific"]["SMA2023_bayer_sma"] = {
    "overrides": params["_override"]
}
ep_path.write_text(json.dumps(ep, indent=2, ensure_ascii=False), encoding="utf-8")

# 코드 생성
code = build_corrected_code(params, "SMA2023_bayer_sma")

# res=20으로 빠른 테스트
code20 = re.sub(r'\bresolution\s*=\s*\d+', 'resolution = 20', code, count=1)

out = Path(__file__).parent / "results" / "SMA2023_bayer_sma"
out.mkdir(parents=True, exist_ok=True)
script = out / "test_bayer_sma_res20.py"
script.write_text(code20, encoding="utf-8")
print(f"생성 완료: {script}")

# Bayer 배치 확인
import subprocess
subprocess.run(["docker","cp",str(script),"meep-pilot-worker:/tmp/sma_bayer_sma.py"],
               capture_output=True)
subprocess.Popen(
    ["docker","exec","meep-pilot-worker","bash","-c",
     "mpirun -np 4 --allow-run-as-root python /tmp/sma_bayer_sma.py > /tmp/sma_bayer_sma.log 2>&1"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)
print("실행 시작 (res=20)")
print("모니터링: docker exec meep-pilot-worker bash -c 'grep Result /tmp/sma_bayer_sma.log'")

# 생성된 코드에서 Bayer 배치 확인
print("\n생성된 Bayer 배치 코드:")
for line in code20.splitlines():
    if "tR" in line or "tGr" in line or "tB " in line or "tGb" in line:
        if "add_flux" in line:
            print(f"  {line.strip()[:100]}")
