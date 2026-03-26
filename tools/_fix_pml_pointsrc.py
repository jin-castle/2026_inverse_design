"""PML 데모: 가운데 점 소스 → 사방으로 퍼지는 펄스 → PML에서 흡수
Panel 1: Ez 필드 스냅샷 (파동 전파 모습)
Panel 2: 경계 근처 Ez 진폭의 시간에 따른 감쇠 (PML 흡수 효과)
"""
import subprocess, sqlite3, tempfile, re
from pathlib import Path

DB_PATH = Path("db/knowledge.db")
RESULTS_DIR = Path("db/results")

CODE = r'''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# ── 파라미터 ───────────────────────────────────────────────────────────────
sx = sy = 10.0
dpml = 1.5
fcen = 0.5
df = 1.0
resolution = 15

# ── 시뮬레이션 설정 (PML + 자유공간 + 가운데 점 소스) ───────────────────────
sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    sources=[mp.Source(
        mp.GaussianSource(fcen, fwidth=df),
        component=mp.Ez,
        center=mp.Vector3(0, 0),   # 정가운데 점 소스
        size=mp.Vector3()           # 점 소스 (크기=0)
    )],
    resolution=resolution
)

# ── 필드 기록 ──────────────────────────────────────────────────────────────
# 경계 근처(PML 바로 안쪽)와 중앙에서 Ez 시간 기록
center_ez = []
near_pml_ez = []
monitor_pt_center = mp.Vector3(0, 0)
monitor_pt_edge   = mp.Vector3(sx/2 - dpml - 0.5, 0)  # PML 직전

def record(sim):
    # get_field_point이 스칼라 반환
    center_ez.append(sim.get_field_point(mp.Ez, monitor_pt_center).real)
    near_pml_ez.append(sim.get_field_point(mp.Ez, monitor_pt_edge).real)

# ── 실행 ───────────────────────────────────────────────────────────────────
sim.run(mp.at_every(0.5, record), until=30)

# ── Ez 필드 스냅샷 (t=15에서) ──────────────────────────────────────────────
sim2 = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    sources=[mp.Source(
        mp.GaussianSource(fcen, fwidth=df),
        component=mp.Ez,
        center=mp.Vector3(0, 0),
        size=mp.Vector3()
    )],
    resolution=resolution
)
sim2.run(until=15)
ez_snap = sim2.get_array(
    component=mp.Ez,
    center=mp.Vector3(),
    size=mp.Vector3(sx, sy)
)

# ── 시간축 ─────────────────────────────────────────────────────────────────
t_arr = np.arange(len(center_ez)) * 0.5
abs_center = np.abs(center_ez)
abs_edge   = np.abs(near_pml_ez)

# ── 2-panel 플롯 ───────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# 왼쪽: Ez 스냅샷 (t=15)
vmax = np.max(np.abs(ez_snap)) * 0.8
im = axes[0].imshow(
    ez_snap.T, cmap='RdBu', origin='lower', aspect='equal',
    extent=[-sx/2, sx/2, -sy/2, sy/2],
    vmin=-vmax, vmax=vmax
)
# PML 영역 표시
from matplotlib.patches import Rectangle
for ax_pos, aw, ah, axy in [
    (-sx/2, dpml, sy, (-sx/2, -sy/2)),
    (sx/2-dpml, dpml, sy, (sx/2-dpml, -sy/2)),
    (-sx/2, sx, dpml, (-sx/2, -sy/2)),
    (-sx/2, sx, dpml, (-sx/2, sy/2-dpml)),
]:
    rect = Rectangle(axy, aw, ah, linewidth=0, facecolor='gray', alpha=0.25)
    axes[0].add_patch(rect)
axes[0].plot(0, 0, 'y*', markersize=12, label='점 소스')
axes[0].plot(monitor_pt_edge.x, 0, 'g^', markersize=8, label='PML 경계 모니터')
plt.colorbar(im, ax=axes[0], label='Ez 진폭')
axes[0].set_title('Ez 필드 스냅샷 (t=15)\n회색=PML 흡수층, 파동이 사방으로 전파', fontsize=11)
axes[0].set_xlabel('x (μm)'); axes[0].set_ylabel('y (μm)')
axes[0].legend(loc='upper right', fontsize=8)

# 오른쪽: 시간에 따른 Ez 진폭 감쇠
axes[1].semilogy(t_arr, abs_center + 1e-10, 'b-', lw=1.5, label='중앙 (점 소스 위치)')
axes[1].semilogy(t_arr, abs_edge   + 1e-10, 'r-', lw=1.5, label='PML 경계 근처')
axes[1].set_xlabel('시간 (MEEP 단위)', fontsize=11)
axes[1].set_ylabel('|Ez| 진폭 (log 스케일)', fontsize=11)
axes[1].set_title('시간에 따른 Ez 진폭 감쇠\nPML이 파동을 반사 없이 흡수', fontsize=11)
axes[1].legend(fontsize=10)
axes[1].grid(True, alpha=0.3)
axes[1].annotate('PML 흡수\n→ 빠른 감쇠',
    xy=(t_arr[len(t_arr)//2], abs_edge[len(t_arr)//2] + 1e-8),
    xytext=(20, 1e-5), fontsize=9, color='red',
    arrowprops=dict(arrowstyle='->', color='red'))

plt.suptitle('PML (Perfectly Matched Layer) — 점 소스 펄스 흡수 시뮬레이션',
             fontsize=13, fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_PML.png', dpi=100, bbox_inches='tight')
print("Done")
'''

safe = "PML"
tmp = Path(tempfile.gettempdir()) / "fix_pml.py"
tmp.write_text(CODE, encoding="utf-8")
subprocess.run(["docker", "cp", str(tmp), "meep-pilot-worker:/tmp/fix_pml.py"], capture_output=True)

print("🔄 PML 점 소스 시뮬레이션 실행 중...")
result = subprocess.run(
    ["docker", "exec", "meep-pilot-worker", "python3", "/tmp/fix_pml.py"],
    capture_output=True, text=True, timeout=180
)
print(f"exit={result.returncode}")
if result.returncode != 0:
    for line in (result.stderr or result.stdout).splitlines()[-10:]:
        print(f"  {line}")
else:
    img_local = RESULTS_DIR / "concept_PML.png"
    cp = subprocess.run(
        ["docker", "cp", "meep-pilot-worker:/tmp/concept_PML.png", str(img_local)],
        capture_output=True, timeout=10
    )
    size = img_local.stat().st_size // 1024 if img_local.exists() else 0
    print(f"이미지: {size}KB")

    if size > 10:
        # DB 업데이트
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "UPDATE concepts SET demo_code=?, result_images=?, demo_description=?, updated_at=CURRENT_TIMESTAMP WHERE name='PML'",
            (CODE,
             "/static/results/concept_PML.png",
             "가운데 점 소스에서 퍼져나가는 Gaussian pulse. 왼쪽: t=15에서의 Ez 필드 분포 (회색=PML 흡수층). 오른쪽: 시간에 따른 Ez 진폭 감쇠 (log 스케일) — PML이 반사 없이 파동을 흡수하는 것을 보여줌.")
        )
        conn.commit()
        conn.close()
        print("✅ PML DB 업데이트 완료")

tmp.unlink(missing_ok=True)
