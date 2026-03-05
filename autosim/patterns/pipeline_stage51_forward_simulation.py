#!/usr/bin/env python3
"""
Pattern: pipeline_stage51_forward_simulation
[Stage 5-1: Forward Simulation] mp.Animate2D로 전파 애니메이션 + DFT 정적 필드 플롯.
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "pipeline_stage51_forward_simulation"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    matplotlib.use('Agg')   # 헤드리스 서버 필수 (GUI 없을 때)

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # ── Forward Simulation with mp.Animate2D ──────────────────────────────────
    # (sim, geometry, sources 등은 Cat.1~4에서 이미 정의됨)

    print("Running forward simulation...")
    animate_fwd = mp.Animate2D(
        sim_fwd,
        fields=mp.Ez,
        realtime=False,    # 헤드리스 서버에서 반드시 False
        normalize=True,    # 필드값 정규화 (색상 스케일 안정화)
    )

    sim_fwd.run(
        mp.at_every(1.0, animate_fwd),   # 1 MEEP 시간 단위마다 프레임 수집
        until=150                         # 충분한 전파 시간 (구조 크기에 따라 조정)
    )

    # ── 애니메이션 저장 ───────────────────────────────────────────────────────
    if mp.am_master():
        # MP4 (ffmpeg 필요)
        animate_fwd.to_mp4(
            fps=15,
            filename=os.path.join(output_dir, "forward_simulation.mp4")
        )
        print("Saved: forward_simulation.mp4")

        # GIF (Pillow 필요, 파일 크기 주의)
        animate_fwd.to_gif(
            fps=10,
            filename=os.path.join(output_dir, "forward_simulation.gif")
        )
        print("Saved: forward_simulation.gif")

    # ── DFT 정적 필드 플롯 (sim.run() 완료 후) ───────────────────────────────
    # sim.get_array()는 마지막 시간 스텝의 순시 필드값
    # DFT 시간 평균 필드는 별도 DftFields 모니터 등록 필요

    if mp.am_master():
        # Epsilon (유전율 분포)
        eps_data = sim_fwd.get_array(
            center=mp.Vector3(),
            size=sim_fwd.cell_size,
            component=mp.Dielectric
        )

        # Ez 필드 (마지막 스텝)
        ez_data = sim_fwd.get_array(
            center=mp.Vector3(),
            size=sim_fwd.cell_size,
            component=mp.Ez
        )

        fig, axes = plt.subplots(1, 2, figsize=(16, 6))

        # 구조 플롯
        axes[0].imshow(
            eps_data.T, cmap='binary', origin='lower',
            interpolation='none'
        )
        axes[0].set_title('Permittivity (Epsilon) Distribution')
        axes[0].axis('off')

        # 필드 플롯 (RdBu: 양/음 모두 표시)
        ez_max = np.abs(ez_data).max() or 1.0
        axes[1].imshow(
            ez_data.T, cmap='RdBu', origin='lower',
            vmin=-ez_max, vmax=ez_max,
            interpolation='bilinear'
        )
        axes[1].set_title('Ez Forward Field (last timestep)')
        axes[1].axis('off')

        plt.tight_layout()
        plt.savefig(
            os.path.join(output_dir, 'forward_field_dft.png'),
            dpi=150, bbox_inches='tight'
        )
        plt.close()
        print("Saved: forward_field_dft.png")

    mp.all_wait()
    sim_fwd.reset_meep()   # 메모리 해제 (필수!)

    # ── DFT 시간 평균 필드 플롯 (더 정확한 방법) ──────────────────────────────
    # sim.run() 전에 DftFields 모니터를 등록해야 함:
    #
    # dft_monitor = sim.add_dft_fields(
    #     [mp.Ez],
    #     fcen, 0, 1,
    #     center=mp.Vector3(), size=cell_size
    # )
    # sim.run(until=150)
    # ez_dft = sim.get_dft_array(dft_monitor, mp.Ez, 0)  # shape: (Nx, Ny)
    # plt.imshow(np.abs(ez_dft).T, ...)
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
