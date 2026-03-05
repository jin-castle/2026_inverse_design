"""
skip_patterns.py
외부 의존성/코드 잘림으로 실행 불가능한 패턴들의 result.json을 skip 상태로 생성.
Docker 컨테이너 내에서 실행.
"""
import json
from pathlib import Path

RESULT_DIR = Path("/root/autosim/results")

SKIP_PATTERNS = {
    # 코드 잘림 (DB 저장 한계)
    "EigenModeSource_basic":    "code truncated in DB (1000 chars limit)",
    "materials_library":        "code truncated in DB (6000 chars limit)",
    "metasurface_lens":         "code truncated in DB (6000 chars limit)",
    "waveguide_crossing":       "code truncated in DB (6000 chars limit)",
    "material_grid_adjoint":    "code truncated in DB - incomplete code fragment",
    "mode_coeff_phase":         "code truncated in DB - R_me assignment incomplete",
    "dft_field_monitor_3d":     "code fragment only - sim object not defined in snippet",
    # GDS 파일 없음
    "coupler_mode_decomposition": "requires coupler.gds (not available)",
    "directional_coupler":        "requires coupler.gds (not available)",
    # 외부 도구 없음
    "waveguide_source_setup":   "requires h5topng (not installed)",
    # mpb 모듈 없음
    "mpb_bragg_bands":          "requires mpb module (not installed in pmp env)",
    "mpb_tutorial_complete":    "requires mpb module (not installed in pmp env)",
}

print("=== SKIP 패턴 result.json 생성 ===")
for name, reason in SKIP_PATTERNS.items():
    d = RESULT_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    data = {
        "pattern": name,
        "status": "skip",
        "elapsed_s": 0,
        "outputs": [],
        "error": None,
        "skip_reason": reason,
    }
    (d / "result.json").write_text(json.dumps(data, indent=2))
    print(f"  [SKIP] {name}: {reason[:60]}")

print(f"\n완료: {len(SKIP_PATTERNS)}개 skip 처리됨")
