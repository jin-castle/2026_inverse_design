#!/usr/bin/env python3
"""
Pattern: pipeline_stage52_adjoint_simulation
[Stage 5-2: Adjoint Simulation] 출력 포트에 mp.Source 배치 + mp.Animate2D.
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "pipeline_stage52_adjoint_simulation"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    matplotlib.use('Agg')

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # ── Adjoint 소스: 출력 포트(모니터) 위치에 배치 ───────────────────────────
    # Forward에서 모니터로 쓰던 x, y 위치를 그대로 사용
    # 예: 3포트 beam splitter (top / mid / bottom)

    # 포트 위치 정의 (Forward 모니터 위치와 동일)
    adjoint_source_positions = [
        (mon_x, y_top,    size_top),    # 상단 출력 포트
        (mon_x, y_mid,    size_mid),    # 중앙 출력 포트
        (mon_x, y_bottom, size_bottom), # 하단 출력 포트
    ]

    # Adjoint 소스 생성 (시각화용: mp.Source + Ez)
    # gradient 계산용이면 EigenModeSource로 교체
    sources_adj = []
    for x, y, size_y in adjoint_source_positions:
        sources_adj.append(
            mp.Source(
                src=mp.GaussianSource(fcen, fwidth=df),
                center=mp.Vector3(x, y, 0),
                size=mp.Vector3(0, size_y, 0),
                component=mp.Ez,   # TE 모드
            )
        )

    # ── Adjoint Simulation 객체 ───────────────────────────────────────────────
    sim_adj = mp.Simulation(
        cell_size=cell_size,
        boundary_layers=pml_layers,
        geometry=geometry_adj,    # Forward와 동일한 geometry
        sources=sources_adj,
        resolution=resolution,
        default_material=mp.Medium(epsilon=eps_air),
    )

    # ── mp.Animate2D ──────────────────────────────────────────────────────────
    print("Running adjoint simulation...")
    animate_adj = mp.Animate2D(
        sim_adj,
        fields=mp.Ez,
        realtime=False,
        normalize=True,
    )

    sim_adj.run(
        mp.at_every(1.0, animate_adj),
        until=150
    )

    # ── 애니메이션 저장 ───────────────────────────────────────────────────────
    if mp.am_master():
        animate_adj.to_mp4(
            fps=15,
            filename=os.path.join(output_dir, "adjoint_simulation.mp4")
        )
        print("Saved: adjoint_simulation.mp4")

        animate_adj.to_gif(
            fps=10,
            filename=os.path.join(output_dir, "adjoint_simulation.gif")
        )
        print("Saved: adjoint_simulation.gif")

    # ── DFT 정적 필드 플롯 ────────────────────────────────────────────────────
    if mp.am_master():
        eps_data = sim_adj.get_array(
            center=mp.Vector3(),
            size=sim_adj.cell_size,
            component=mp.Dielectric
        )
        ez_data = sim_adj.get_array(
            center=mp.Vector3(),
            size=sim_adj.cell_size,
            component=mp.Ez
        )

        fig, axes = plt.subplots(1, 2, figsize=(16, 6))

        axes[0].imshow(eps_data.T, cmap='binary', origin='lower', interpolation='none')
        axes[0].set_title('Structure (Adjoint geometry)')
        axes[0].axis('off')

        ez_max = np.abs(ez_data).max() or 1.0
        axes[1].imshow(
            ez_data.T, cmap='RdBu', origin='lower',
            vmin=-ez_max, vmax=ez_max,
            interpolation='bilinear'
        )
        axes[1].set_title('Ez Adjoint Field (last timestep)')
        axes[1].axis('off')

        plt.tight_layout()
        plt.savefig(
            os.path.join(output_dir, 'adjoint_field_dft.png'),
            dpi=150, bbox_inches='tight'
        )
        plt.close()
        print("Saved: adjoint_field_dft.png")

    mp.all_wait()
    sim_adj.reset_meep()   # 메모리 해제

    # ── Forward vs Adjoint 비교 플롯 ──────────────────────────────────────────
    # Forward와 Adjoint 필드를 나란히 비교 (곱셈 = gradient와 연관)
    # overlap = np.real(ez_fwd_dft * np.conj(ez_adj_dft))  → gradient map과 유사
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
