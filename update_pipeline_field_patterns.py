"""
Stage 5-1 (Forward) + Stage 5-2 (Adjoint) 패턴 업데이트
- 실제 검증된 mp.Animate2D 코드 반영
- DFT 정적 필드 플롯 추가
- Adjoint: 출력 포트에 mp.Source 배치하는 실제 방법 반영
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "knowledge.db")

# ─────────────────────────────────────────────────────────────────────────────
# Stage 5-1: Forward Simulation — Animate2D + DFT 정적 플롯
# ─────────────────────────────────────────────────────────────────────────────

STAGE51_DESC = """\
[Stage 5-1: Forward Simulation] mp.Animate2D로 전파 애니메이션 + DFT 정적 필드 플롯.

주요 주의사항:
- mp.Animate2D: fields=mp.Ez, normalize=True 설정. realtime=False (헤드리스 서버 필수).
- sim.run() 호출 시 mp.at_every(dt, animate)를 등록하면 프레임 자동 수집.
- to_mp4(fps, filename): ffmpeg 필요. to_gif()는 Pillow 필요.
- DFT 정적 플롯: sim.run() 완료 후 sim.get_array()로 eps, Ez 추출하여 imshow.
- matplotlib.use('Agg') 헤드리스 서버에서 필수 (GUI 없을 때 segfault 방지).
- mp.am_master() 없이 저장하면 MPI 환경에서 중복 저장 오류.
- sim.reset_meep(): 메모리 해제. 다음 시뮬레이션 실행 전 반드시 호출.
- 애니메이션 until 값: 충분한 전파 시간. 보통 100~200 (단위: MEEP 시간).
"""

STAGE51_CODE = """\
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')   # 헤드리스 서버 필수 (GUI 없을 때)
import matplotlib.pyplot as plt
import meep as mp

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
"""

# ─────────────────────────────────────────────────────────────────────────────
# Stage 5-2: Adjoint Simulation — 출력 포트 소스 배치 + Animate2D
# ─────────────────────────────────────────────────────────────────────────────

STAGE52_DESC = """\
[Stage 5-2: Adjoint Simulation] 출력 포트에 mp.Source 배치 + mp.Animate2D.

핵심 개념:
- Adjoint 시뮬레이션은 Forward의 역방향: 출력 모니터 위치에 소스를 배치하여 역전파.
- mpa.OptimizationProblem 사용 시 adjoint는 자동 처리됨 (내부 API 접근 불가).
- 직접 시각화할 때는 출력 포트마다 mp.Source(또는 EigenModeSource)를 수동 배치.
- 소스 위치: Forward에서 출력 모니터로 쓰던 위치와 동일.
- 소스 종류: 단순 시각화는 mp.Source(mp.Ez), gradient 계산용은 EigenModeSource.

주요 주의사항:
- 출력 포트가 여러 개면 (beam splitter 등) 각 포트에 별도 소스 배치.
- mp.Animate2D는 Forward와 동일한 설정 사용.
- 시각화 목적 adjoint와 gradient 계산 목적 adjoint는 소스 설정이 다름.
- mp.am_master() 없이 저장하면 MPI 환경에서 중복 저장 오류.
- sim.reset_meep() 반드시 호출 (Forward와 구분).
"""

STAGE52_CODE = """\
import meep as mp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

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
"""

# ─────────────────────────────────────────────────────────────────────────────
# DB 업데이트
# ─────────────────────────────────────────────────────────────────────────────

def update_pattern(conn, name, desc, code):
    result = conn.execute(
        "UPDATE patterns SET description=?, code_snippet=? WHERE pattern_name=?",
        (desc, code, name)
    )
    if result.rowcount == 0:
        print(f"  [WARN] {name} not found in DB")
    else:
        print(f"  [UPDATE] {name} (rowcount={result.rowcount})")

conn = sqlite3.connect(DB_PATH)
print(f"DB: {DB_PATH}")

update_pattern(conn, "pipeline_stage51_forward_simulation", STAGE51_DESC, STAGE51_CODE)
update_pattern(conn, "pipeline_stage52_adjoint_simulation", STAGE52_DESC, STAGE52_CODE)

conn.commit()
conn.close()
print("\nDB update done.")
