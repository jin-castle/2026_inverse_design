#!/usr/bin/env python3
"""
1. DFT field 플롯 colormap → jet
2. PML → 시간 단계별 스냅샷 3장 + 시간축 감쇠 (at_every 스타일)  
3. bend → 공식 MEEP 튜토리얼 기반 L자형 두 Block
"""
import os, re, sqlite3, subprocess, tempfile
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"
RESULTS_DIR = Path(__file__).parent.parent / "db" / "results"

conn = sqlite3.connect(str(DB_PATH), timeout=15)

# ══════════════════════════════════════════════════════════════════════════════
# 1. DFT colormap hot/inferno → jet (39개 일괄)
# ══════════════════════════════════════════════════════════════════════════════
print("=== Step 1: DFT colormap → jet ===")
rows = conn.execute(
    "SELECT name, demo_code FROM concepts WHERE demo_code LIKE '%get_dft_array%'"
).fetchall()

updated = 0
for name, code in rows:
    new_code = code
    # |Ez|² DFT imshow colormap 교체
    new_code = re.sub(r"cmap='hot'",    "cmap='jet'", new_code)
    new_code = re.sub(r'cmap="hot"',    'cmap="jet"', new_code)
    new_code = re.sub(r"cmap='inferno'", "cmap='jet'", new_code)
    new_code = re.sub(r'cmap="inferno"', 'cmap="jet"', new_code)
    if new_code != code:
        conn.execute("UPDATE concepts SET demo_code=? WHERE name=?", (new_code, name))
        updated += 1

conn.commit()
print(f"  colormap 업데이트: {updated}개")

# ══════════════════════════════════════════════════════════════════════════════
# 2. PML — 시간 단계별 스냅샷 3장 + at_every 감쇠 곡선
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== Step 2: PML — 시간 단계별 스냅샷 ===")

PML_CODE = r'''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# ── 파라미터 (공식 MEEP 튜토리얼 참조) ────────────────────────────────────
sx = sy = 10.0
dpml  = 1.5
fcen  = 0.5
df    = 1.0
resolution = 15

# ── 점 소스 + PML 시뮬레이션 ─────────────────────────────────────────────
def make_sim():
    return mp.Simulation(
        cell_size=mp.Vector3(sx, sy),
        boundary_layers=[mp.PML(dpml)],
        sources=[mp.Source(
            mp.GaussianSource(fcen, fwidth=df),
            component=mp.Ez,
            center=mp.Vector3(),   # 가운데 점 소스
            size=mp.Vector3()
        )],
        resolution=resolution
    )

# ── at_every로 Ez 시계열 기록 ─────────────────────────────────────────────
sim = make_sim()
monitor_center = mp.Vector3()
monitor_edge   = mp.Vector3(sx/2 - dpml - 0.3, 0)

t_vals, ez_center, ez_edge = [], [], []

def record(sim):
    t_vals.append(sim.meep_time())
    ez_center.append(sim.get_field_point(mp.Ez, monitor_center).real)
    ez_edge.append(  sim.get_field_point(mp.Ez, monitor_edge).real)

sim.run(mp.at_every(0.5, record), until=40)
t_arr   = np.array(t_vals)
ez_c    = np.array(ez_center)
ez_e    = np.array(ez_edge)

# ── 시간 단계별 Ez 스냅샷 3장 ────────────────────────────────────────────
snaps = {}
for t_target in [5, 12, 22]:
    s = make_sim()
    s.run(until=t_target)
    snaps[t_target] = s.get_array(
        component=mp.Ez,
        center=mp.Vector3(), size=mp.Vector3(sx, sy)
    )

# ── 4-panel 플롯 ─────────────────────────────────────────────────────────
fig = plt.figure(figsize=(16, 8))
gs  = fig.add_gridspec(2, 4, hspace=0.45, wspace=0.35)

def add_pml_overlay(ax):
    """PML 영역 회색 오버레이 추가"""
    for xy, w, h in [
        ((-sx/2, -sy/2), dpml, sy),   # left
        ((sx/2-dpml, -sy/2), dpml, sy),# right
        ((-sx/2, -sy/2), sx, dpml),    # bottom
        ((-sx/2, sy/2-dpml), sx, dpml),# top
    ]:
        ax.add_patch(Rectangle(xy, w, h, lw=0, fc='gray', alpha=0.3, zorder=5))

# 위쪽: 스냅샷 3장
for col, t_target in enumerate([5, 12, 22]):
    ax = fig.add_subplot(gs[0, col])
    ez = snaps[t_target]
    vmax = np.max(np.abs(ez)) * 0.85 or 1
    im = ax.imshow(ez.T, cmap='RdBu', origin='lower', aspect='equal',
                   extent=[-sx/2, sx/2, -sy/2, sy/2],
                   vmin=-vmax, vmax=vmax, interpolation='bilinear')
    add_pml_overlay(ax)
    ax.plot(0, 0, 'y*', ms=10, zorder=10, label='소스')
    ax.set_title(f't = {t_target}', fontsize=11, fontweight='bold')
    ax.set_xlabel('x (μm)'); ax.set_ylabel('y (μm)')
    plt.colorbar(im, ax=ax, shrink=0.8)

# 오른쪽 위: 범례
ax_leg = fig.add_subplot(gs[0, 3])
ax_leg.axis('off')
ax_leg.text(0.1, 0.85, 'PML 흡수 효과', fontsize=12, fontweight='bold',
            transform=ax_leg.transAxes)
ax_leg.text(0.1, 0.6,
    '점 소스에서 퍼져나가는\nGaussian pulse가\nPML(회색) 경계에서\n반사 없이 흡수됨',
    fontsize=10, transform=ax_leg.transAxes, va='top')
from matplotlib.patches import Patch
ax_leg.legend(handles=[
    Patch(fc='gray', alpha=0.3, label='PML 흡수층'),
    Patch(fc='#d40000', alpha=0.7, label='+Ez'),
    Patch(fc='#002aff', alpha=0.7, label='-Ez'),
], loc='lower left', fontsize=9, framealpha=0.8)

# 아래: at_every 시계열 감쇠 (전체 폭)
ax_t = fig.add_subplot(gs[1, :])
ax_t.plot(t_arr, ez_c, 'b-', lw=1.2, alpha=0.8, label='중앙 Ez(t) — 소스 위치')
ax_t.plot(t_arr, ez_e, 'r-', lw=1.2, alpha=0.8, label='PML 직전 Ez(t)')
ax_t2 = ax_t.twinx()
ax_t2.semilogy(t_arr, np.abs(ez_c)+1e-10, 'b--', lw=0.8, alpha=0.5)
ax_t2.semilogy(t_arr, np.abs(ez_e)+1e-10, 'r--', lw=0.8, alpha=0.5, label='|Ez| (log)')
ax_t2.set_ylabel('|Ez| (log)', fontsize=10, color='gray')
ax_t2.tick_params(colors='gray')
ax_t.set_xlabel('시간 (MEEP 단위)', fontsize=11)
ax_t.set_ylabel('Ez 진폭', fontsize=11)
ax_t.set_title('at_every(0.5, record)로 기록한 Ez 시계열 — PML이 파동을 흡수하면 빠르게 감쇠',
               fontsize=11)
ax_t.legend(loc='upper right', fontsize=9)
ax_t.grid(True, alpha=0.2)
ax_t.axvspan(0, 10, alpha=0.05, color='yellow', label='pulse 방출 구간')

plt.suptitle('PML (Perfectly Matched Layer) — 점 소스 펄스 전파 & 흡수 시뮬레이션',
             fontsize=14, fontweight='bold', y=1.01)
plt.savefig('/tmp/concept_PML.png', dpi=100, bbox_inches='tight')
print("Done")
'''

def run_docker(code, name, timeout=180):
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    tmp = Path(tempfile.gettempdir()) / f"_fix_{safe}.py"
    tmp.write_text(code, encoding="utf-8")
    subprocess.run(["docker", "cp", str(tmp), f"meep-pilot-worker:/tmp/_fix_{safe}.py"],
                   capture_output=True)
    r = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "python3", f"/tmp/_fix_{safe}.py"],
        capture_output=True, text=True, timeout=timeout
    )
    tmp.unlink(missing_ok=True)
    return r

def save_img(name, code, desc=None):
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    img_local = RESULTS_DIR / f"concept_{safe}.png"
    cp = subprocess.run(
        ["docker", "cp", f"meep-pilot-worker:/tmp/concept_{safe}.png", str(img_local)],
        capture_output=True, timeout=10
    )
    size = img_local.stat().st_size // 1024 if img_local.exists() else 0
    if size > 10:
        img_url = f"/static/results/concept_{safe}.png"
        upd = "UPDATE concepts SET demo_code=?, result_images=?"
        args = [code, img_url]
        if desc:
            upd += ", demo_description=?"
            args.append(desc)
        upd += ", updated_at=CURRENT_TIMESTAMP WHERE name=?"
        args.append(name)
        conn.execute(upd, args)
        conn.commit()
        print(f"  ✅ {name}: {size}KB")
    else:
        print(f"  ❌ {name}: 이미지 저장 실패 ({size}KB)")
    return size

# PML 실행
r = run_docker(PML_CODE, "PML", timeout=300)
print(f"  exit={r.returncode}")
if r.returncode != 0:
    for l in r.stderr.splitlines()[-8:]:
        print(f"    {l}")
else:
    save_img("PML", PML_CODE, "점 소스에서 퍼지는 Gaussian pulse의 시간 단계별 Ez 스냅샷(t=5,12,22)과 at_every로 기록한 시계열. PML(회색)이 파동을 반사 없이 흡수하는 것을 보여줌.")

# ══════════════════════════════════════════════════════════════════════════════
# 3. bend — 공식 MEEP 튜토리얼 기반 (두 Block L자형, ContinuousSource)
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== Step 3: bend — 공식 MEEP 코드 기반 ===")

BEND_CODE = r'''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# ── 공식 MEEP 튜토리얼: bent-waveguide 기반 ─────────────────────────────
# https://github.com/NanoComp/meep/blob/master/python/examples/bent-waveguide.py
cell = mp.Vector3(16, 16, 0)

geometry = [
    # 수평 구간
    mp.Block(
        mp.Vector3(12, 1, mp.inf),
        center=mp.Vector3(-2.5, -3.5),
        material=mp.Medium(epsilon=12)
    ),
    # 수직 구간
    mp.Block(
        mp.Vector3(1, 12, mp.inf),
        center=mp.Vector3(3.5, 2),
        material=mp.Medium(epsilon=12)
    ),
]

pml_layers = [mp.PML(1.0)]
resolution = 10

# ContinuousSource — 단일 주파수 (λ = 2√11 ≈ 6.63 μm)
sources = [
    mp.Source(
        mp.ContinuousSource(wavelength=2*(11**0.5), width=20),
        component=mp.Ez,
        center=mp.Vector3(-7, -3.5),
        size=mp.Vector3(0, 1)
    )
]

sim = mp.Simulation(
    cell_size=cell,
    boundary_layers=pml_layers,
    geometry=geometry,
    sources=sources,
    resolution=resolution
)

# ── DFT 필드 모니터 ────────────────────────────────────────────────────────
fcen = 1 / (2*(11**0.5))
dft_obj = sim.add_dft_fields(
    [mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(14, 14))
)

# ── 실행 (t=200까지) ───────────────────────────────────────────────────────
sim.run(until=200)

# ── 필드/구조 추출 ─────────────────────────────────────────────────────────
eps = sim.get_array(component=mp.Dielectric,
                    center=mp.Vector3(), size=mp.Vector3(14, 14))
ez_ss = sim.get_array(component=mp.Ez,
                      center=mp.Vector3(), size=mp.Vector3(14, 14))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

# ── 3-panel 플롯 ───────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
ext = [-7, 7, -7, 7]

# 왼쪽: 유전율 (구조)
im0 = axes[0].imshow(eps.T, cmap='Blues', origin='lower', aspect='equal', extent=ext)
axes[0].set_title('구조 (유전율 ε)\n수평+수직 Block으로 L자형', fontsize=11)
axes[0].set_xlabel('x (μm)'); axes[0].set_ylabel('y (μm)')
plt.colorbar(im0, ax=axes[0], label='ε_r')

# 가운데: Ez 순시 필드 (정상상태)
vmax = np.max(np.abs(ez_ss)) * 0.7 or 1
im1 = axes[1].imshow(ez_ss.T, cmap='RdBu', origin='lower', aspect='equal',
                     extent=ext, vmin=-vmax, vmax=vmax)
axes[1].set_title('Ez 순시 필드 (t=200)\nContinuousSource 정상상태', fontsize=11)
axes[1].set_xlabel('x (μm)')
plt.colorbar(im1, ax=axes[1], label='Ez')

# 오른쪽: |Ez|² DFT (jet colormap)
im2 = axes[2].imshow(np.abs(ez_dft).T**2, cmap='jet', origin='lower', aspect='equal',
                     extent=ext)
axes[2].set_title('|Ez|² DFT (주파수 도메인)\n굴곡부를 통한 모드 전파', fontsize=11)
axes[2].set_xlabel('x (μm)')
plt.colorbar(im2, ax=axes[2], label='|Ez|²')

plt.suptitle('90° Waveguide Bend — 공식 MEEP 튜토리얼 기반\n(ε=12, λ=2√11 μm, ContinuousSource)',
             fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_bend.png', dpi=100, bbox_inches='tight')
print("Done")
'''

r = run_docker(BEND_CODE, "bend", timeout=300)
print(f"  exit={r.returncode}")
if r.returncode != 0:
    for l in r.stderr.splitlines()[-8:]:
        print(f"    {l}")
else:
    save_img("bend", BEND_CODE,
             "공식 MEEP 튜토리얼(bent-waveguide.py)의 L자형 90° 굴곡 도파관. 왼쪽: 유전율 구조, 가운데: Ez 순시 필드(정상상태), 오른쪽: |Ez|² DFT(jet colormap).")

# ══════════════════════════════════════════════════════════════════════════════
# 4. DFT jet 적용된 코드로 Docker에서 핵심 개념 재실행 (이미지 갱신)
#    waveguide, EigenmodeSource, FluxRegion, get_array, plot2D, Symmetry
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== Step 4: DFT jet colormap 적용 후 핵심 개념 재실행 ===")

PRIORITY = ["waveguide", "EigenmodeSource", "FluxRegion", "get_array",
            "plot2D", "Symmetry", "directional_coupler", "grating_coupler"]

for name in PRIORITY:
    row = conn.execute("SELECT demo_code FROM concepts WHERE name=?", (name,)).fetchone()
    if not row or not row[0]:
        continue
    code = row[0]
    # 이미 jet이면 스킵
    if "cmap='jet'" in code or 'cmap="jet"' in code:
        safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        r = run_docker(code, name, timeout=180)
        if r.returncode == 0:
            size = save_img(name, code)
        else:
            print(f"  ❌ {name}: {r.stderr.splitlines()[-3:]}")

conn.close()
print("\n=== 완료 ===")
