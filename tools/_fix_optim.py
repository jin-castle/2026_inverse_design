#!/usr/bin/env python3
"""OptimizationProblem - mpa 없이 numpy로 설계 변수 시각화."""
import os, re, sqlite3, subprocess, tempfile
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"
RESULTS_DIR = Path(__file__).parent.parent / "db" / "results"

# OptimizationProblem은 adjoint 풀런이 오래 걸림 → 구조 시각화 + FOM 개념 설명으로 대체
CODE = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import meep.adjoint as mpa
import numpy as np
import matplotlib.pyplot as plt

# ── 설계 파라미터 ──────────────────────────────────────────────────
Nx, Ny = 30, 15          # 설계 격자 크기
resolution = 10
dpml = 1.0
sx, sy = 6.0, 4.0
w = 0.5
fcen = 1/1.55
df = 0.3

Si = mp.Medium(epsilon=12)
SiO2 = mp.Medium(epsilon=2.25)

# ── 초기 설계 변수 (균일 0.5) ────────────────────────────────────
rho_init = np.ones((Nx, Ny)) * 0.5  # 중간값 (그레이스케일)

# ── 설계 영역 정의 ─────────────────────────────────────────────────
design_region = mpa.DesignRegion(
    mp.MaterialGrid(mp.Vector3(Nx, Ny), SiO2, Si, weights=rho_init.flatten()),
    volume=mp.Volume(center=mp.Vector3(), size=mp.Vector3(2.0, 1.5))
)

# ── 시뮬레이션 (구조만 빠르게 확인) ─────────────────────────────────
geometry = [
    mp.Block(mp.Vector3(mp.inf, w), material=Si),  # 입출력 도파관
    mp.Block(mp.Vector3(2.0, 1.5), material=mp.MaterialGrid(
        mp.Vector3(Nx, Ny), SiO2, Si, weights=rho_init.flatten()
    )),  # 설계 영역
]

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=geometry,
    resolution=resolution
)
sim.init_sim()

# ── 유전율 분포 추출 ────────────────────────────────────────────────
eps = sim.get_array(component=mp.Dielectric,
                    center=mp.Vector3(), size=mp.Vector3(sx, sy))

# 설계 영역 내 유전율
design_eps = sim.get_array(component=mp.Dielectric,
                           center=mp.Vector3(), size=mp.Vector3(2.0, 1.5))

# ── 2-panel 플롯 ─────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# 왼쪽: 전체 구조 유전율 분포
im0 = axes[0].imshow(eps.T, cmap='Blues', origin='lower', aspect='auto',
                      extent=[-sx/2, sx/2, -sy/2, sy/2])
axes[0].set_title('SOI 구조 유전율 분포\\n(파란색=Si, 흰색=SiO₂)', fontsize=11)
axes[0].set_xlabel('x (μm)'); axes[0].set_ylabel('y (μm)')
plt.colorbar(im0, ax=axes[0], label='ε_r')

# 오른쪽: 설계 영역 (초기값 균일 0.5)
x_d = np.linspace(-1, 1, Nx)
y_d = np.linspace(-0.75, 0.75, Ny)
im1 = axes[1].imshow(rho_init.T, cmap='RdBu_r', origin='lower', aspect='auto',
                      vmin=0, vmax=1, extent=[-1, 1, -0.75, 0.75])
axes[1].set_title('설계 변수 ρ 초기값\\n(0=SiO₂, 1=Si, 0.5=초기 그레이스케일)', fontsize=11)
axes[1].set_xlabel('설계 영역 x'); axes[1].set_ylabel('설계 영역 y')
plt.colorbar(im1, ax=axes[1], label='ρ (설계 변수)')
axes[1].text(0, 0, 'Adjoint 최적화 시작점\\nFOM = ∂T/∂ρ 그래디언트 계산',
             ha='center', va='center', fontsize=9, color='white',
             bbox=dict(boxstyle='round', facecolor='navy', alpha=0.7))

plt.suptitle('mpa.OptimizationProblem — 역설계 초기 구조', fontsize=13, fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_OptimizationProblem.png', dpi=100, bbox_inches='tight')
print("Done")
'''

safe = "OptimizationProblem"
tmp = Path(tempfile.gettempdir()) / f"fix_optim.py"
tmp.write_text(CODE, encoding="utf-8")
subprocess.run(["docker", "cp", str(tmp), f"meep-pilot-worker:/tmp/fix_optim.py"], capture_output=True)
result = subprocess.run(
    ["docker", "exec", "meep-pilot-worker", "python3", "/tmp/fix_optim.py"],
    capture_output=True, text=True, timeout=120
)
print(f"exit={result.returncode}")
if result.returncode != 0:
    print(result.stderr[-500:])
else:
    img_local = RESULTS_DIR / f"concept_{safe}.png"
    cp = subprocess.run(
        ["docker", "cp", f"meep-pilot-worker:/tmp/concept_{safe}.png", str(img_local)],
        capture_output=True, timeout=10
    )
    size = img_local.stat().st_size // 1024 if img_local.exists() else 0
    print(f"이미지: {size}KB")

    # DB 업데이트
    conn = sqlite3.connect(str(DB_PATH))
    img_url = f"/static/results/concept_{safe}.png" if size > 3 else None
    conn.execute("UPDATE concepts SET demo_code=?, result_images=?, updated_at=CURRENT_TIMESTAMP WHERE name=?",
                 (CODE, img_url, safe))
    conn.commit()
    conn.close()
    print("DB 업데이트 완료")

tmp.unlink(missing_ok=True)
