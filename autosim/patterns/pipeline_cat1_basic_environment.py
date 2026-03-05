#!/usr/bin/env python3
"""
Pattern: pipeline_cat1_basic_environment
[Category 1: 시뮬레이션 환경 설정] SOI 220nm 역설계 기본 환경 파라미터.
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "pipeline_cat1_basic_environment"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # ── 기본 단위: μm ──────────────────────────────────────────────────────────
    wavelength = 1.55        # μm (1550 nm)
    fcen       = 1.0 / wavelength  # ~0.6452 (MEEP 주파수 단위)
    fwidth     = 0.2 * fcen  # 가우시안 소스 대역폭

    # ── 재료 ──────────────────────────────────────────────────────────────────
    n_Si   = 3.48            # Silicon @ 1550 nm
    n_SiO2 = 1.44            # Silica
    silicon = mp.Medium(index=n_Si)
    oxide   = mp.Medium(index=n_SiO2)

    # ── SOI 스택 ──────────────────────────────────────────────────────────────
    wg_thick = 0.22          # μm (220 nm Si slab)
    sub_thick = 0.5          # μm (SiO2 기판)

    # ── PML + Cell ────────────────────────────────────────────────────────────
    dpml = 1.0               # μm — PML 두께 (λ/2 = 0.775 이상)
    # cell_size는 디자인 영역 크기에 따라 결정 (아래는 예시)
    # sxy = design_region_x + 2*wg_length + 2*dpml
    # sz  = wg_thick + sub_thick + dpml + air_gap (3D)

    boundary_layers = [mp.PML(thickness=dpml)]

    # ── 해상도 ────────────────────────────────────────────────────────────────
    resolution = 50          # px/μm (최종 최적화용)
    # resolution = 10        # 빠른 검증용 (구조 확인만)

    # ── SiO2 배경 (PML까지 연장 필수) ─────────────────────────────────────────
    # 2D 예시: SiO2 배경을 cell 전체에 깔기
    # geometry_bg = [mp.Block(size=mp.Vector3(mp.inf, mp.inf, mp.inf),
    #                         material=oxide)]
    # 주의: mp.inf 없으면 SiO2가 cell 경계에서 잘려 반사 발생
    # ─────────────────────────────────────────────────────────

    # figure 자동 저장
    _outputs = []
    if plt.get_fignums():
        _out = savefig_safe(_PATTERN)
        if _out:
            _outputs.append("output.png")

    _elapsed = round(_time.time() - _t0, 2)
    save_result(_PATTERN, outputs=_outputs, elapsed=_elapsed)
    if mp.am_master():
        print(f"[OK] {_PATTERN} ({_elapsed}s) outputs={_outputs}")

except Exception as _e:
    _elapsed = round(_time.time() - _t0, 2)
    save_result(_PATTERN, error=_e, elapsed=_elapsed)
    import traceback
    traceback.print_exc()
    sys.exit(1)
