"""기존 모든 결과 수집 + 교정 결과 포함"""
import json, re
from pathlib import Path

BASE = Path(__file__).parent / "results"

# 수동으로 알려진 결과 (Single2022, Pixel2022는 원본 재현)
KNOWN = {
    "Single2022": {
        "paper_title": "Single-Layer Bayer Metasurface via Inverse Design (TiO2)",
        "design_type": "discrete_pillar", "material": "TiO2", "n": 2.3,
        "SP_size": 0.8, "Layer_t": 0.3, "FL_t": 2.0, "resolution": 50,
        "res50": {"R": 0.709, "G": 0.457, "B": 0.729},
        "target": {"R": 0.70, "G": 0.60, "B": 0.65},
        "avg_err": 6.0,
    },
    "Pixel2022": {
        "paper_title": "Pixel-level Bayer-type colour router based on metasurfaces (SiN)",
        "design_type": "discrete_pillar", "material": "SiN", "n": 2.0,
        "SP_size": 1.0, "Layer_t": 0.6, "FL_t": 2.0, "resolution": 40,
        "res50": {"R": 0.554, "G": 0.508, "B": 0.556},
        "target": {"R": 0.55, "G": 0.52, "B": 0.50},
        "avg_err": 1.8,
    },
    "SMA2023": {
        "paper_title": "Pixelated Bayer spectral router (sparse meta-atom, Chinese Optics Letters)",
        "design_type": "sparse", "material": "SiN", "n": 2.02,
        "SP_size": 1.12, "Layer_t": 1.0, "FL_t": 4.0, "resolution": 50,
        "res50_before": {"R": 0.081, "G": 0.279, "B": 0.104},
        "res50_after":  {"R": 0.143, "G": 0.344, "B": 0.106},
        "target": {"R": 0.45, "G": 0.35, "B": 0.40},
        "avg_err_before": 82, "avg_err_after": 47.8,
    },
    "Simplest2023": {
        "paper_title": "Simplest GA cylinder router (Nb2O5, Genetic Algorithm)",
        "design_type": "cylinder", "material": "Nb2O5", "n": 2.32,
        "SP_size": 0.8, "Layer_t": 0.51, "FL_t": 1.08, "resolution": 100,
        "res100_before": {"R": 0.068, "G": 0.473, "B": 0.254},
        "res100_after":  {"R": 0.068, "G": 0.473, "B": 0.254},
        "target": {"R": 0.60, "G": 0.55, "B": 0.55},
        "avg_err_before": 89, "avg_err_after": 52.2,
    },
    "RGBIR2025": {
        "paper_title": "Pixel-Level Spectral Routers for RGB+IR Sensing (TiO2, ACS 2025)",
        "design_type": "discrete_pillar", "material": "TiO2", "n": 2.5,
        "SP_size": 1.1, "Layer_t": 0.6, "FL_t": 4.0, "resolution": 50,
        "res50_before": {"R": 0.118, "G": 0.238, "B": 0.403},
        "res50_after":  {"R": 0.118, "G": 0.238, "B": 0.403},  # 업데이트 필요
        "target": {"R": 0.50, "G": 0.40, "B": 0.50},
        "avg_err_before": 76, "avg_err_after": 45.4,
    },
}

# 교정 결과 확인
for pid in ["SMA2023","Simplest2023","RGBIR2025"]:
    corrected_json = BASE / pid / f"corrected_{pid}_results.json"
    if corrected_json.exists():
        r = json.loads(corrected_json.read_text(encoding='utf-8'))
        final = r.get("final",{})
        if final:
            eff = final.get("eff")
            if eff:
                key = "res50_after" if "50" in str(final.get("res","")) else "res100_after"
                KNOWN[pid][key] = eff
                print(f"{pid} 교정 결과 갱신: {eff}")

(BASE / "all_results.json").write_text(json.dumps(KNOWN,indent=2,ensure_ascii=False),encoding='utf-8')
print("\n저장:", BASE / "all_results.json")
