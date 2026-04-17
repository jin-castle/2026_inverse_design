"""
MEEP-KB 코드+에러 진단 엔진
============================
1단계: 에러 패턴 파싱 → DB 검색 (keyword + vector)
2단계: DB 매칭 충분하면 → DB 기반 수정 제안
3단계: DB 매칭 부족 시  → LLM 분석 (폴백)
4단계: 단계별 진단 프레임워크 (STAGE0~STAGE5)

DB FIRST 원칙: meep-kb 지식베이스를 최대한 활용
"""
import re, os, sqlite3
from pathlib import Path
from typing import Optional

# ─── 단계별 진단 프레임워크 ──────────────────────────────────────────────────

DIAGNOSTIC_STAGES = {
    "STAGE0_ENV": {
        "name": "환경/설치 검증",
        "triggers": ["ImportError", "ModuleNotFoundError", "h5topng", "mpi4py", "hdf5",
                     "conda", "import meep", "no module", "version"],
        "symptoms": ["import meep 실패", "h5py 없음", "MPI 오류"],
        "checklist": [
            "conda activate pmp 했는가?",
            "mpirun -np N python ... 올바른 환경에서 실행했는가?",
            "meep 버전 확인: python -c 'import meep; print(meep.__version__)'",
        ],
        "diagnostic_code": '''# [STAGE 0] 환경 검증 스니펫
import sys, subprocess
print(f"Python: {sys.version}")
try:
    import meep as mp; print(f"MEEP: {mp.__version__}")
except ImportError as e: print(f"MEEP import 실패: {e}")
try:
    import h5py; print(f"h5py: {h5py.__version__}")
except ImportError: print("h5py 없음 - conda install h5py")
try:
    import mpi4py; print(f"mpi4py: {mpi4py.__version__}")
except ImportError: print("mpi4py 없음")
result = subprocess.run(["which", "mpirun"], capture_output=True, text=True)
print(f"mpirun: {result.stdout.strip() or '없음'}")''',
        "pitfalls": [],
        "next_stage": "STAGE1_GEOMETRY",
    },

    "STAGE1_GEOMETRY": {
        "name": "구조 레이아웃 검증",
        "triggers": ["plot2D", "geometry", "cell_size", "structure", "layout",
                     "구조", "레이아웃", "geometry.*beyond", "object.*outside",
                     "deadlock", "GeometryError"],
        "symptoms": ["구조가 제대로 안 보임", "geometry 오류", "plot2D 실행 안 됨", "deadlock"],
        "checklist": [
            "cell_size가 모든 geometry를 포함하는가?",
            "PML 두께 포함한 실제 simulation 영역이 geometry보다 충분히 큰가?",
            "plot2D는 반드시 단일 프로세스(mpirun 없이)로 실행해야 함",
            "3D 시뮬레이션이면 output_plane 지정 필요",
        ],
        "diagnostic_code": '''# [STAGE 1] 구조 레이아웃 진단
# ⚠️ 중요: mpirun 없이 단일 프로세스로 실행!
import meep as mp
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- 여기에 시뮬레이션 설정 붙여넣기 ---
# sim = mp.Simulation(...)

fig, ax = plt.subplots(figsize=(10, 8))
sim.plot2D(ax=ax)
ax.set_title("Geometry Layout Check")
plt.tight_layout()
plt.savefig("debug_layout.png", dpi=150)
print("Saved: debug_layout.png")
print(f"Cell size: {sim.cell_size}")
print(f"Geometry objects: {len(sim.geometry)}")
for i, obj in enumerate(sim.geometry):
    print(f"  [{i}] {type(obj).__name__}: center={obj.center}, size={getattr(obj, 'size', 'N/A')}")''',
        "pitfalls": [
            "mpirun으로 plot2D 실행 시 deadlock 발생 가능 → 반드시 단일 프로세스로",
            "3D에서 output_plane 없이 plot2D 호출 시 에러",
            "geometry가 cell 밖으로 나가면 Warning만 나고 무시됨 (확인 필요)",
            "PML 영역 내 geometry는 흡수 이상 동작 유발",
        ],
        "next_stage": "STAGE2_SOURCE",
    },

    "STAGE2_SOURCE": {
        "name": "소스 검증",
        "triggers": ["EigenModeSource", "source", "eig_band", "eig_parity",
                     "source.*cancel", "zero.*field", "symmetry.*cancel",
                     "소스", "source 검증", "SymmetryError"],
        "symptoms": ["필드가 약함", "소스 효율 낮음", "대칭으로 소스 상쇄", "symmetry cancel"],
        "checklist": [
            "소스 size가 도파로(waveguide)를 충분히 덮는가? (waveguide width + 여유 2~3배)",
            "소스 위치가 PML 경계에서 충분히 떨어졌는가? (최소 PML 두께 + 0.5μm)",
            "eig_parity가 올바른가? (TE: ODD_Z, TM: EVEN_Z, 3D: EVEN_Y+ODD_Z)",
            "eig_band가 1부터 시작하는가? (0은 잘못된 값)",
            "symmetry 사용 시 소스와 symmetry plane 관계 확인",
        ],
        "diagnostic_code": '''# [STAGE 2] 소스 검증 스니펫
# ⚠️ 단일 프로세스 실행 권장
import meep as mp, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- 시뮬레이션 설정 ---
# sim = mp.Simulation(...)
DPML = 1.0  # 실제 PML 두께로 교체

print("=== SOURCE VALIDATION ===")
for i, src in enumerate(sim.sources):
    c, s = src.center, src.size
    print(f"Source [{i}]: center={c}, size={s}")
    half_cell = sim.cell_size / 2
    margins = {
        "x-": c.x + half_cell.x - s.x/2,
        "x+": half_cell.x - c.x - s.x/2,
        "y-": c.y + half_cell.y - s.y/2,
        "y+": half_cell.y - c.y - s.y/2,
    }
    for side, margin in margins.items():
        if margin < DPML + 0.3:
            print(f"  ⚠️ {side} 방향 PML 근접 경고: margin={margin:.3f}μm")

sim.init_sim()
sim.run(until=5)
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
sim.plot2D(ax=axes[0], fields=mp.Ez)
axes[0].set_title("Ez field (t=5)")
y_pts = np.linspace(-sim.cell_size.y/2, sim.cell_size.y/2, 100)
ez_profile = [sim.get_field_point(mp.Ez, mp.Vector3(sim.sources[0].center.x, y)) for y in y_pts]
axes[1].plot(y_pts, np.abs(ez_profile))
axes[1].set_title("Source cross-section |Ez|")
plt.savefig("debug_source.png", dpi=150)
print("Saved: debug_source.png")''',
        "pitfalls": [
            "eig_band=0 사용 시 efficiency > 100% 발생 (1부터 시작해야 함)",
            "소스 size가 도파로보다 작으면 고차 모드 여기",
            "2D와 3D의 eig_parity가 다름 (3D: EVEN_Y+ODD_Z for TE)",
            "mpirun 환경에서 get_field_point는 rank 0에서만 유효",
        ],
        "next_stage": "STAGE3_FORWARD",
    },

    "STAGE3_FORWARD": {
        "name": "Forward 필드 / DFT 검증",
        "triggers": ["T>100", "transmittance", "flux", "DFT", "energy.*conservation",
                     "T\\+R", "forward", "투과율", "반사율", "필드", "FluxError",
                     "load_minus_flux", "stop_when_fields_decayed"],
        "symptoms": ["T > 100%", "T + R != 1", "필드가 이상함", "투과율 비정상"],
        "checklist": [
            "T + R ≈ 1 인가? (에너지 보존)",
            "flux monitor가 source보다 downstream에 있는가?",
            "reference flux(빈 셀)로 나누었는가?",
            "resolution이 충분한가? (최소 10 px/μm, 권장 30+)",
            "시뮬레이션이 충분히 decay했는가? (stop_when_fields_decayed)",
        ],
        "diagnostic_code": '''# [STAGE 3] Forward 필드 / DFT 검증
import meep as mp, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- 시뮬레이션 설정 + 실행 ---
# refl_flux = sim.add_flux(fcen, 0, 1, ...)
# tran_flux = sim.add_flux(fcen, 0, 1, ...)
# sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, decay_pt, 1e-3))

T = mp.get_fluxes(tran_flux)[0] / input_flux
R = -mp.get_fluxes(refl_flux)[0] / input_flux
print(f"T = {T:.4f} ({T*100:.1f}%)")
print(f"R = {R:.4f} ({R*100:.1f}%)")
print(f"T+R = {T+R:.4f}")
if T > 1.0:
    print("⚠️ T > 100%: 에너지 보존 위반 → resolution 높이거나 PML 두께 늘리기")
if abs(T+R - 1.0) > 0.05:
    print(f"⚠️ T+R = {T+R:.3f} ≠ 1.0 → 모니터 위치/크기 확인")

# DFT 필드 시각화
dft_fields = sim.add_dft_fields([mp.Ez, mp.Hz], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
ez_dft = sim.get_dft_array(dft_fields, mp.Ez, 0)
im0 = axes[0].imshow(np.abs(ez_dft).T, cmap="hot", origin="lower", aspect="auto")
axes[0].set_title(f"|Ez| DFT @ f={fcen:.3f}")
plt.colorbar(im0, ax=axes[0])
plt.savefig("debug_forward_dft.png", dpi=150)
print("Saved: debug_forward_dft.png")''',
        "pitfalls": [
            "reference flux 없이 normalize하면 T > 100% 발생",
            "모니터가 소스 뒤(upstream)에 있으면 반사 flux 부호 반대",
            "load_minus_flux 안 하면 반사 계산 틀림",
            "stop_when_fields_decayed 없이 짧게 실행하면 스펙트럼 분해능 낮음",
            "3D에서 DFT 메모리 과다 사용 → where 범위 제한 권장",
        ],
        "next_stage": "STAGE4_ADJOINT",
    },

    "STAGE4_ADJOINT": {
        "name": "Adjoint 필드 / 소스 검증",
        "triggers": ["adjoint", "OptimizationProblem", "gradient", "changed_materials",
                     "reset_meep", "adjoint.*source", "adjoint 필드", "AdjointBug",
                     "AdjointAttributeError", "need_gradient"],
        "symptoms": ["adjoint 실행 안 됨", "changed_materials 오류", "gradient NaN", "adjoint 필드 이상"],
        "checklist": [
            "opt(x, need_gradient=True) 전에 sim.run() 호출했는가? (금지!)",
            "design region이 cell 안에 있는가?",
            "EigenmodeCoefficient monitor band가 1부터 시작하는가?",
            "FOM 부호: 최적화는 최소화 → J = -|S21|² 형태여야 함",
            "adjoint DFT 필드가 비어있지 않은가?",
        ],
        "diagnostic_code": '''# [STAGE 4] Adjoint 필드 검증
import meep as mp, meep.adjoint as mpa
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- opt 설정 ---
# opt = mpa.OptimizationProblem(...)

# 1) Forward만 먼저 실행 (gradient 없이)
print("=== Forward only (no gradient) ===")
f0 = opt([rho_vector], need_gradient=False)
print(f"FOM = {float(np.real(f0)):.6f}")
if np.isnan(f0) or np.isinf(f0):
    print("⚠️ FOM is NaN/Inf → monitor 위치 또는 FOM 정의 확인")

# 2) Gradient 계산
print("=== Forward + Adjoint (gradient) ===")
f0, grad = opt([rho_vector])
print(f"FOM = {float(np.real(f0)):.6f}")
print(f"Gradient norm = {np.linalg.norm(grad):.4e}")
print(f"Gradient max  = {np.max(np.abs(grad)):.4e}")
if np.linalg.norm(grad) < 1e-10:
    print("⚠️ Gradient ≈ 0 → monitor가 design_region 밖에 있거나 FOM 정의 오류")

# 3) Gradient 시각화
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
try:
    grad_2d = np.real(grad).reshape(Nx, Ny)
    vmax_g = np.max(np.abs(grad_2d)) or 1
    axes[1].imshow(grad_2d.T, cmap="RdBu_r", origin="lower", aspect="auto",
                   vmin=-vmax_g, vmax=vmax_g)
    axes[1].set_title("Raw Gradient (∂FOM/∂ε)")
    plt.colorbar(axes[1].get_images()[0], ax=axes[1])
except Exception as e:
    axes[1].text(0.5, 0.5, f"Reshape 실패: {e}", ha="center", va="center",
                transform=axes[1].transAxes)
plt.tight_layout()
plt.savefig("debug_adjoint.png", dpi=150)
print("Saved: debug_adjoint.png")''',
        "pitfalls": [
            "opt() 호출 전 sim.run() 금지 → changed_materials 오류",
            "EigenmodeCoefficient mode=0 사용 시 잘못된 값 (1부터 시작)",
            "FOM 최대화 시 부호 반전 필요 (J = -target)",
            "MPI 환경에서 adjoint는 all ranks에서 실행해야 함 (rank 0 only X)",
            "3D adjoint는 메모리 매우 많이 필요 (resolution 낮게 시작)",
        ],
        "next_stage": "STAGE5_GRADIENT",
    },

    "STAGE5_GRADIENT": {
        "name": "Gradient / FOM 수렴 검증",
        "triggers": ["gradient.*nan", "gradient.*zero", "fom.*not.*improve",
                     "gradient.*check", "finite.*difference", "수렴", "그라디언트",
                     "not improving", "gradient is zero", "adjoint gradient"],
        "symptoms": ["gradient가 0", "FOM 개선 안 됨", "최적화 수렴 안 함"],
        "checklist": [
            "Gradient와 유한차분이 일치하는가? (gradient check)",
            "projection β가 너무 크지 않은가? (처음엔 β=1~4 권장)",
            "learning rate가 적절한가? (FOM 변화량 기준 조정)",
            "MaterialGrid 크기(Nx, Ny)가 올바른가?",
            "필터링 후 chain rule 적용했는가?",
        ],
        "diagnostic_code": '''# [STAGE 5] Gradient 검증 - 유한차분 비교
import meep as mp, meep.adjoint as mpa
import numpy as np

# opt = mpa.OptimizationProblem(...)
# rho = np.ones(Nx*Ny) * 0.5

# 1) Adjoint gradient
f0, grad_adj = opt([rho])
grad_adj = np.real(grad_adj)
print(f"FOM = {float(np.real(f0)):.6f}")
print(f"Adjoint grad norm = {np.linalg.norm(grad_adj):.4e}")

# 2) 유한차분 gradient (몇 개 픽셀만)
eps = 1e-3
n_check = min(5, len(rho))
idx_check = np.random.choice(len(rho), n_check, replace=False)

print("\n=== Finite Difference vs Adjoint ===")
print(f"{'idx':>6} | {'FD':>12} | {'Adjoint':>12} | {'ratio':>8}")
print("-" * 48)
for idx in idx_check:
    rho_p = rho.copy(); rho_p[idx] += eps
    rho_m = rho.copy(); rho_m[idx] -= eps
    fp = float(np.real(opt([rho_p], need_gradient=False)))
    fm = float(np.real(opt([rho_m], need_gradient=False)))
    fd_grad = (fp - fm) / (2 * eps)
    adj_grad = grad_adj[idx]
    ratio = adj_grad / fd_grad if abs(fd_grad) > 1e-12 else float('nan')
    match = "✅" if abs(ratio - 1.0) < 0.05 else "⚠️"
    print(f"{idx:>6} | {fd_grad:>12.6e} | {adj_grad:>12.6e} | {ratio:>7.3f} {match}")

# 3) Gradient 분포 시각화
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
grad_2d = grad_adj.reshape(Nx, Ny)
im = axes[0].imshow(grad_2d.T, cmap="RdBu_r", origin="lower", aspect="auto",
                     vmin=-np.max(np.abs(grad_2d)), vmax=np.max(np.abs(grad_2d)))
axes[0].set_title("Adjoint Gradient Map")
plt.colorbar(im, ax=axes[0], label="∂FOM/∂ρ")
axes[1].hist(grad_adj, bins=50)
axes[1].set_title("Gradient Distribution")
plt.savefig("debug_gradient.png", dpi=150)
print("Saved: debug_gradient.png")''',
        "pitfalls": [
            "subpixel averaging(eps_averaging=True) 켜면 adjoint gradient 불일치 → 꺼야 함",
            "FourierFields/Near2FarFields adjoint는 MEEP v1.17+ 버그 있음",
            "β 너무 크면 gradient binarization에 의해 plateau 발생",
            "filter_and_project chain rule 빠트리면 gradient 수렴 불가",
        ],
        "next_stage": None,
    },
}


def detect_stage(code: str, error: str, query: str = "") -> list:
    """
    코드/에러/쿼리에서 관련 진단 단계를 감지.
    여러 단계가 해당될 수 있음.

    Returns: [{"stage_key": ..., "stage_name": ..., "match_score": ...,
               "checklist": ..., "diagnostic_code": ..., "pitfalls": ...,
               "next_stage": ...}, ...]
    """
    combined = " ".join([code or "", error or "", query or ""]).lower()
    matched = []

    for stage_key, stage_info in DIAGNOSTIC_STAGES.items():
        score = 0
        for trigger in stage_info["triggers"]:
            if re.search(trigger.lower(), combined):
                score += 1
        if score > 0:
            matched.append({
                "stage_key":       stage_key,
                "stage_name":      stage_info["name"],
                "match_score":     score,
                "checklist":       stage_info["checklist"],
                "diagnostic_code": stage_info["diagnostic_code"],
                "pitfalls":        stage_info["pitfalls"],
                "next_stage":      stage_info["next_stage"],
            })

    return sorted(matched, key=lambda x: x["match_score"], reverse=True)

# 시맨틱 검색 모듈 — startup에서 main.py가 주입 (sys.path 충돌 방지)
_SEM_MOD = None

BASE = Path(os.environ.get("APP_DIR", Path(__file__).parent.parent))
DB_PATH = BASE / "db/knowledge.db"

# ─── 에러 패턴 정규식 ─────────────────────────────────────────────────────────
ERROR_PATTERNS = [
    # Python 기본
    (r"AttributeError: module 'numpy'.*no attribute '(\w+)'",
     "NumPyAttributeError", "NumPy 속성 없음"),
    (r"AttributeError: module 'meep'.*no attribute '(\w+)'",
     "MeepAPIAttributeError", "MEEP API 속성 없음"),
    (r"AttributeError: '?Simulation'? object has no attribute '(\w+)'",
     "SimulationAttributeError", "Simulation 속성 없음"),
    (r"AttributeError: '?OptimizationProblem'? object has no attribute",
     "AdjointAttributeError", "adjoint 속성 없음"),
    (r"AttributeError: '?EigenmodeCoefficient'? object has no attribute",
     "EigenModeAttributeError", "EigenmodeCoefficient 속성 없음"),
    (r"AttributeError: '?([\w.]+)'? object has no attribute '(\w+)'",
     "AttributeError", "객체 속성 없음"),
    (r"AttributeError: module '?([\w.]+)'? has no attribute '(\w+)'",
     "AttributeError", "모듈 속성 없음"),
    (r"AttributeError: (.*)",
     "AttributeError", "속성 오류"),
    (r"TypeError: (.*)", "TypeError", "타입 오류"),
    (r"ValueError: (.*)", "ValueError", "값 오류"),
    (r"ImportError: No module named '([^']+)'",
     "ImportError", "모듈 없음"),
    (r"ModuleNotFoundError: No module named '([^']+)'",
     "ImportError", "모듈 없음"),
    (r"RuntimeError: (.*)", "RuntimeError", "런타임 오류"),
   (r"MemoryError", "MemoryError", "메모리 부족"),
   (r"KeyboardInterrupt", "KeyboardInterrupt", "사용자 중단"),
   (r"NameError: name '(\w+)' is not defined", "NameError", "이름 미정의"),
   (r"IndentationError: (.*)", "IndentationError", "들여쓰기 오류"),
   (r"SyntaxError: (.*)", "SyntaxError", "문법 오류"),
   # MEEP 특화
  (r"h5topng.*not found|h5topng.*command", "ToolNotFound", "h5topng 없음"),
  (r"Purcell.*[<>].*1|LDOS.*normaliz|ldos.*wrong", "LDOSError", "LDOS 정규화 오류"),
  # MEEP 특화
   (r"geometry.*beyond.*cell|extends.*cell.*bound|object.*outside.*cell", "GeometryError", "geometry 셀 범위 초과"),
   (r"Q.*lower.*than.*expected|cavity.*Q.*[<>]\s*\d|photonic.*crystal.*Q|PhC.*cavity", "WrongGeometry", "PhC cavity Q 낮음"),
   (r"solve_cw.*convergence|convergence.*failure.*cw|CW.*solver.*fail", "SolverError", "CW solver 수렴 실패"),
   (r"fields.*not.*decay|not.*converging|stop_when_fields_decayed", "ConvergenceError", "필드 감쇠 안 됨"),
   (r"T\+R.*>[0-9]|energy.*conservation.*violat|load_minus_flux", "FluxError", "에너지 보존 위반"),
   (r"source.*cancel|zero.*field.*symmetry|symmetry.*cancel", "SymmetryError", "대칭 소스 상쇄"),
   (r"adjoint.*amplitude|amplitude.*adjoint|place_adjoint_source", "AdjointSourceError", "adjoint 소스 진폭 오류"),
    (r"changed_materials|reset_meep", "AdjointBug", "adjoint 재설정 버그"),
    (r"Simulation diverged|diverged", "Divergence", "시뮬레이션 발산"),
    (r"NaN|nan|inf|Inf", "NumericalError", "수치 불안정"),
    (r"MPIError|mpi4py|MPI", "MPIError", "MPI 병렬화 오류"),
    (r"EigenModeSource|eigenmode", "EigenMode", "고유모드 소스 오류"),
    (r"PML|perfectly matched layer", "PML", "PML 경계 오류"),
    (r"adjoint|OptimizationProblem", "Adjoint", "adjoint 최적화 오류"),
    (r"Harminv|harminv", "Harminv", "Harminv 오류"),
    (r"(out of memory|OOM|CUDA out)", "OOM", "메모리 부족"),
    (r"segmentation fault|Segmentation", "SegFault", "세그폴트"),
    (r"nlopt|NLopt", "NLopt", "NLopt 최적화 오류"),
]


def parse_error(code: str, error: str) -> dict:
    """에러 메시지에서 에러 타입 및 키워드 추출"""
    combined = error + " " + code
    detected = []

    for pattern, err_type, description in ERROR_PATTERNS:
        m = re.search(pattern, combined, re.IGNORECASE)
        if m:
            detected.append({
                "type":        err_type,
                "description": description,
                "matched":     m.group(0)[:100],
                "groups":      m.groups() if m.groups() else [],
            })

    # 에러 메시지에서 핵심 줄 추출 (Traceback 마지막 줄)
    error_lines = [l.strip() for l in error.split("\n") if l.strip()]
    last_error = ""
    for line in reversed(error_lines):
        if not line.startswith("File ") and not line.startswith("Traceback"):
            last_error = line
            break

    # 코드에서 MEEP 관련 키워드 추출
    meep_keywords = re.findall(
        r'\b(mp\.\w+|meep\.\w+|EigenModeSource|OptimizationProblem|'
        r'adjoint|ModeMonitor|FluxRegion|Simulation|PML|Vector3|'
        r'Harminv|add_flux|run_until|force_complex_fields)\b',
        code
    )

    # 에러 메시지에서도 핵심 키워드 추출 (속성명, 모듈명 등)
    error_kw_patterns = [
        r"has no attribute '(\w+)'",
        r"No module named '([^']+)'",
        r"name '(\w+)' is not defined",
        r"cannot import name '([^']+)'",
        r"'(\w+)' object has no attribute",
    ]
    for pat in error_kw_patterns:
        for m in re.findall(pat, error, re.IGNORECASE):
            if m and len(m) > 2:
                meep_keywords.append(m)

    return {
        "detected_types": detected,
        "primary_type":   detected[0]["type"] if detected else "Unknown",
        "last_error_line": last_error,
        "meep_keywords":   list(set(meep_keywords))[:10],
    }


def search_db(error_info: dict, code: str, error: str, n: int = 5) -> list:
    """SQLite DB에서 에러 패턴 검색 (FTS + LIKE 혼합)"""
    results = []
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.row_factory = sqlite3.Row

        # 검색 키워드 구성
        kws = set()
        for t in error_info["detected_types"]:
            kws.add(t["type"])
            kws.add(t["description"])
        kws.update(error_info["meep_keywords"][:5])
        if error_info["last_error_line"]:
            words = re.findall(r'\b[A-Za-z]\w+\b', error_info["last_error_line"])
            kws.update(words[:5])
        # 불필요한 단어 제거
        kws -= {"", "None", "True", "False", "the", "a", "an", "and", "or", "in", "is", "to"}

        # ── 1. errors FTS 검색 (빠른 전문 검색) ──────────────────────────────
        fts_kws = [kw for kw in kws if len(kw) > 3][:5]
        for kw in fts_kws:
            try:
                rows = conn.execute("""
                    SELECT e.id, e.error_msg, e.category, e.cause, e.solution,
                           e.source_url, 'error' as rtype
                    FROM errors_fts ft
                    JOIN errors e ON e.id = ft.rowid
                    WHERE errors_fts MATCH ?
                    LIMIT 4
                """, (kw,)).fetchall()
                for row in rows:
                    sol = (row["solution"] or "").strip()
                    if sol:  # solution 있는 것만
                        results.append({
                            "type":     "error",
                            "title":    row["error_msg"] or row["category"] or "MEEP 오류",
                            "cause":    row["cause"] or "",
                            "solution": sol,
                            "url":      row["source_url"] or "",
                            "score":    0.75,
                            "source":   "kb_fts",
                        })
            except Exception:
                pass

        # ── 2. errors LIKE 검색 (FTS가 못 잡는 케이스 보완) ─────────────────
        for kw in list(kws)[:6]:
            if len(kw) < 4:
                continue
            try:
                rows = conn.execute("""
                    SELECT error_msg, category, cause, solution, source_url
                    FROM errors
                    WHERE (cause LIKE ? OR solution LIKE ? OR error_msg LIKE ?)
                      AND solution IS NOT NULL AND solution != ''
                    LIMIT 3
                """, (f"%{kw}%", f"%{kw}%", f"%{kw}%")).fetchall()
                for row in rows:
                    results.append({
                        "type":     "error",
                        "title":    row["error_msg"] or row["category"] or "MEEP 오류",
                        "cause":    row["cause"] or "",
                        "solution": row["solution"] or "",
                        "url":      row["source_url"] or "",
                        "score":    0.65,
                        "source":   "kb_sqlite",
                    })
            except Exception:
                pass

        # ── 3. sim_errors 테이블 검색 (검증된 오류-해결쌍) ──────────────────
        try:
            primary_type = error_info.get("primary_type", "")
            err_kws_for_sim = [kw for kw in kws if len(kw) > 4][:4]
            # 에러 메시지 조각들로 LIKE 검색
            err_msg_parts = re.findall(r'\b[A-Za-z][A-Za-z0-9_]{4,}\b', error or "")[:5]
            all_search_kws = list(set(err_kws_for_sim + err_msg_parts))[:6]

            rows = []
            seen_sim = set()

            # 3a. error_type 직접 매칭
            if primary_type and primary_type not in ("Unknown", "General"):
                rs = conn.execute("""
                    SELECT error_type, error_message, fix_description, fixed_code,
                           fix_applied, root_cause, context, pattern_name,
                           fix_worked, source, confidence
                    FROM sim_errors WHERE error_type = ?
                    ORDER BY fix_worked DESC,
                             CASE COALESCE(confidence,'low')
                               WHEN 'high' THEN 4 WHEN 'medium' THEN 3
                               WHEN 'draft' THEN 2 ELSE 1 END DESC
                    LIMIT 3
                """, (primary_type,)).fetchall()
                for r in rs:
                    k = (r["error_type"] + r["error_message"])[:60]
                    if k not in seen_sim:
                        seen_sim.add(k); rows.append(r)

            
            # 3a-2. sim_errors FTS search
            if primary_type and primary_type not in ("Unknown", "General"):
                try:
                    fts_q = """
                        SELECT s.error_type, s.error_message, s.fix_description,
                               s.fixed_code, s.fix_applied, s.root_cause,
                               s.context, s.pattern_name, s.fix_worked, s.source,
                               s.confidence
                        FROM sim_errors_fts ft
                        JOIN sim_errors s ON s.id = ft.rowid
                        WHERE sim_errors_fts MATCH ?
                        ORDER BY s.fix_worked DESC,
                                 CASE COALESCE(s.confidence,'low')
                                   WHEN 'high' THEN 4 WHEN 'medium' THEN 3
                                   WHEN 'draft' THEN 2 ELSE 1 END DESC
                        LIMIT 5
                    """
                    for r in conn.execute(fts_q, (primary_type,)).fetchall():
                        k = (r["error_type"] + (r["error_message"] or ""))[:60]
                        if k not in seen_sim:
                            seen_sim.add(k)
                            rows.append(r)
                except Exception:
                    pass

# 3b. 에러 메시지 키워드 LIKE 검색 (marl_auto, error_injector 포함)
            for kw in all_search_kws:
                if len(rows) >= 5:
                    break
                rs = conn.execute("""
                   SELECT error_type, error_message, fix_description, fixed_code,
                          fix_applied, root_cause, context, pattern_name,
                          fix_worked, source, confidence
                   FROM sim_errors
                   WHERE error_message LIKE ? OR fix_description LIKE ? OR root_cause LIKE ?
                    OR fix_keywords LIKE ? OR pattern_name LIKE ?
                    ORDER BY fix_worked DESC,
                             CASE COALESCE(confidence,'low')
                               WHEN 'high' THEN 4 WHEN 'medium' THEN 3
                               WHEN 'draft' THEN 2 ELSE 1 END DESC
                    LIMIT 3
                """, (f"%{kw}%", f"%{kw}%", f"%{kw}%", f"%{kw}%", f"%{kw}%")).fetchall()
                for r in rs:
                    k = (r["error_type"] + r["error_message"])[:60]
                    if k not in seen_sim:
                        seen_sim.add(k)
                        rows.append(r)

            # ── 3b-NEW: sim_errors_v2 검색 (5계층 구조) ─────────────────────────────
            try:
                seen_v2 = set()
                rows_v2 = []

                # 3b-NEW-1: error_type 정확/LIKE 매칭 (파생 타입 포함: EigenMode_eig_band_zero 등)
                rs = conn.execute("""
                    SELECT error_class, error_type, error_message, symptom,
                           physics_cause, code_cause, root_cause_chain,
                           fix_type, fix_description, code_diff, fix_worked, source
                    FROM sim_errors_v2
                    WHERE (error_type = ? OR error_type LIKE ?)
                      AND fix_worked = 1
                    ORDER BY fix_worked DESC LIMIT 4
                """, (primary_type, f"{primary_type}%")).fetchall()
                for r in rs:
                    k = (r["error_type"] + (r["error_message"] or ""))[:60]
                    if k not in seen_v2:
                        seen_v2.add(k)
                        rows_v2.append(r)

                # 3b-NEW-2: error_message + physics_cause LIKE 검색 (마지막 에러줄 기반)
                if len(rows_v2) < 3 and error_info.get("last_error_line"):
                    last_err = error_info["last_error_line"][:50]
                    rs2 = conn.execute("""
                        SELECT error_class, error_type, error_message, symptom,
                               physics_cause, code_cause, root_cause_chain,
                               fix_type, fix_description, code_diff, fix_worked, source
                        FROM sim_errors_v2
                        WHERE (error_message LIKE ? OR physics_cause LIKE ? OR code_cause LIKE ?)
                          AND fix_worked = 1
                        ORDER BY fix_worked DESC LIMIT 3
                    """, (f"%{last_err}%", f"%{last_err}%", f"%{last_err}%")).fetchall()
                    for r in rs2:
                        k = (r["error_type"] + (r["error_message"] or ""))[:60]
                        if k not in seen_v2:
                            seen_v2.add(k)
                            rows_v2.append(r)

                # 3b-NEW-3: MEEP 키워드 기반 검색
                if len(rows_v2) < 2:
                    for kw in error_info.get("meep_keywords", [])[:3]:
                        if len(rows_v2) >= 4:
                            break
                        rs3 = conn.execute("""
                            SELECT error_class, error_type, error_message, symptom,
                                   physics_cause, code_cause, root_cause_chain,
                                   fix_type, fix_description, code_diff, fix_worked, source
                            FROM sim_errors_v2
                            WHERE (physics_cause LIKE ? OR fix_description LIKE ?)
                              AND fix_worked = 1
                            LIMIT 2
                        """, (f"%{kw}%", f"%{kw}%")).fetchall()
                        for r in rs3:
                            k = (r["error_type"] + (r["error_message"] or ""))[:60]
                            if k not in seen_v2:
                                seen_v2.add(k)
                                rows_v2.append(r)

                for row in rows_v2[:4]:
                    fix_text = row["fix_description"] or row["code_diff"] or ""
                    cause_text = row["physics_cause"] or row["code_cause"] or row["error_message"] or ""
                    source_label = row["source"] or "live_run"
                    # 소스별 점수
                    v2_score_map = {
                        "live_run": 0.75, "error_injector": 0.90, "marl_auto": 0.94,
                        "research_notes": 0.88, "verified_fix": 0.92,
                    }
                    base_score = v2_score_map.get(source_label, 0.90)
                    if not row["fix_worked"]:
                        base_score = min(base_score, 0.70)
                    results.append({
                        "type":             "sim_error_v2",
                        "title":            f"[v2:{row['error_class']}] {row['error_type']}: {(row['error_message'] or '')[:50]}",
                        "cause":            cause_text[:300],
                        "solution":         fix_text[:400],
                        "code":             (row["code_diff"] or "")[:400],
                        "physics_cause":    (row["physics_cause"] or "")[:500],  # 명시적 노출
                        "code_cause":       (row["code_cause"] or "")[:300],
                        "symptom":          row["symptom"] or "",
                        "fix_type":         row["fix_type"] or "",
                        "root_cause_chain": row["root_cause_chain"] or "[]",
                        "error_class":      row["error_class"] or "",
                        "url":              "",
                        "score":            base_score,
                        "source":           f"sim_errors_v2:{source_label}",
                    })
            except Exception:
                pass

            # score 우선순위 체계 (소스별 신뢰도)
            SCORE_BY_SOURCE = {
                "live_run":                    0.98,  # 실제 실행 캡처
                "meep_official_docs":          0.97,  # MEEP 공식 문서
                "meep_official_troubleshooting":0.97, # MEEP 공식 Troubleshooting
                "nanocomp_meep_official":      0.96,  # 공식 예제 직접 실행
                "meep_official_verified":      0.96,  # 직접 검증됨
                "verified_fix":                0.95,  # MEEP Docker 실행 검증
                "github_issue_analyzed":       0.95,  # GitHub 원문 LLM 분석 + 코드 작성
                "marl_auto":                   0.92,  # MARL 자동 수정 검증
                "error_injector":              0.93,  # v2 구조 (2026-03-25)
                "jin_live_run_2026-03-28":     0.96,  # 실제 실행
                "jin_verified":                0.96,  # 수동 검증
                "e2e_demo":                    0.94,
                "ablation_sell2017":           0.95,
                "github_structured":           0.72,  # LLM 구조화 요약
                "github_issue":                0.55,  # GitHub 텍스트 (코드 없음)
                "kb_fts":                      0.65,  # FTS 텍스트 검색
                "err_file":                    0.60,  # 에러 파일 텍스트
            }

            # confidence → 점수 보정
            CONFIDENCE_BONUS = {
                "high":   +0.05,   # 실행 검증 완료
                "medium":  0.00,   # 합성/미검증
                "draft":  -0.10,   # LLM 추론만, 미검증
                "low":    -0.20,   # 코드 없음 (증상만)
            }

            # rows → results 변환 (루프 밖에서 한 번만)
            for row in rows:
                fix_worked   = row["fix_worked"] or 0
                confidence   = row["confidence"] if "confidence" in row.keys() else "medium"
                verified_tag = "검증됨" if fix_worked else "참고용"
                fix_text = row["fix_description"] or row["fix_applied"] or row["root_cause"] or ""
                fix_code = row["fixed_code"] or ""
                source_label = row["source"] or "sim_errors"
                # 소스별 기본 점수
                base_score = SCORE_BY_SOURCE.get(source_label, 0.70)
                # confidence 보정
                base_score += CONFIDENCE_BONUS.get(confidence or "low", -0.20)
                base_score = max(0.10, min(1.0, base_score))
                if not fix_worked:
                    base_score = min(base_score, 0.70)  # 미검증은 최대 0.70
                # confidence=low이면 fix_code 숨김 (할루시네이션 방지)
                if confidence == "low":
                    fix_code = ""  # 코드 없이 증상/원인만 노출

                # Tie-break 비활성화 (광범위 키워드로 오히려 노이즈 증가)
                # 대신 error_type 직접 매칭이 우선순위를 결정
                results.append({
                    "type":     "sim_error",
                    "title":    f"[{verified_tag}] {row['error_type']}: {(row['error_message'] or '')[:60]}",
                    "cause":    row["error_message"] or row["context"] or "",
                    "solution": fix_text[:400],
                    "code":     fix_code[:400],
                    "url":      "",
                    "score":    base_score,
                    "source":   f"sim_errors:{source_label}",
                })
        except Exception:
            pass

        # ── 4. examples 테이블 검색 (MEEP 함수 기반) ─────────────────────────
        for kw in error_info["meep_keywords"][:5]:
            try:
                rows = conn.execute("""
                    SELECT title, code, description, source_repo
                    FROM examples
                    WHERE code LIKE ? OR description LIKE ? OR title LIKE ?
                    LIMIT 2
                """, (f"%{kw}%", f"%{kw}%", f"%{kw}%")).fetchall()
                for row in rows:
                    results.append({
                        "type":        "example",
                        "title":       row["title"] or "MEEP 예제",
                        "code":        (row["code"] or "")[:400],
                        "description": row["description"] or "",
                        "url":         row["source_repo"] or "",
                        "score":       0.55,
                        "source":      "kb_sqlite",
                    })
            except Exception:
                pass

        # ── 5. sim_errors_unified 마스터 테이블 검색 ────────────────────────
        try:
            # 에러 메시지 / symptom 컬럼 전체 검색 (fix_worked=1만)
            last_err_q = (error_info.get("last_error_line") or "")[:50]
            primary    = error_info.get("primary_type", "")
            seen_uni   = set()

            # 5a. error_type + last_error_line 매칭
            uni_rows = conn.execute("""
                SELECT error_type, error_message, physics_cause, code_cause,
                       fix_description, fixed_code, verification_criteria,
                       diagnostic_snippet, fix_worked, source,
                       symptom_numerical, symptom_behavioral, symptom_error_pattern
                FROM sim_errors_unified
                WHERE (error_message LIKE ? OR symptom_error_pattern LIKE ?
                       OR error_type = ?)
                  AND fix_worked = 1
                ORDER BY fix_worked DESC
                LIMIT 5
            """, (f"%{last_err_q}%", f"%{last_err_q}%", primary)).fetchall()

            # 5b. physics_cause / symptom_behavioral LIKE 보완
            for kw in list(kws)[:4]:
                if len(uni_rows) >= 5:
                    break
                if len(kw) < 5:
                    continue
                more = conn.execute("""
                    SELECT error_type, error_message, physics_cause, code_cause,
                           fix_description, fixed_code, verification_criteria,
                           diagnostic_snippet, fix_worked, source,
                           symptom_numerical, symptom_behavioral, symptom_error_pattern
                    FROM sim_errors_unified
                    WHERE (physics_cause LIKE ? OR symptom_behavioral LIKE ?
                           OR fix_description LIKE ?)
                      AND fix_worked = 1
                    LIMIT 2
                """, (f"%{kw}%", f"%{kw}%", f"%{kw}%")).fetchall()
                uni_rows = list(uni_rows) + list(more)

            for row in uni_rows[:5]:
                key = (row[0] or "") + (row[1] or "")[:50]
                if key in seen_uni:
                    continue
                seen_uni.add(key)
                src = row[9] or "sim_errors_unified"
                score_map = {
                    "live_run": 0.72, "error_injector": 0.85,
                    "marl_auto": 0.88, "verified_fix": 0.90,
                }
                score = score_map.get(src, 0.88)
                results.append({
                    "type":          "sim_error_unified",
                    "title":         f"[unified] {row[0]}: {(row[1] or '')[:50]}",
                    "cause":         (row[2] or row[3] or "")[:300],
                    "solution":      (row[4] or "")[:400],
                    "code":          (row[5] or "")[:600],
                    "verification":  row[6] or "",
                    "diag_snippet":  (row[7] or "")[:300],
                    "symptom_num":   row[10] or "",
                    "symptom_beh":   row[11] or "",
                    "symptom_err":   row[12] or "",
                    "score":         score,
                    "source":        f"sim_errors_unified:{src}",
                })
        except Exception:
            pass

        conn.close()
    except Exception as e:
        pass

    # 점수 내림차순 정렬 후 중복 제거 (sim_errors score=0.90이 kb_fts score=0.75보다 앞에)
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    seen = set()
    unique = []
    for r in results:
        key = r.get("title", "") + r.get("cause", "")[:50]
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:n]


def search_vector(query: str, n: int = 3, model=None, client=None) -> list:
    """
    시맨틱 검색 — fastembed/bge-small-en-v1.5 기반.
    OOD 감지: score < 0.40이면 is_ood=True 마킹.
    기존 model/client 인자는 무시 (하위 호환성 유지).
    """
    global _SEM_MOD
    # 지연 초기화: 최초 호출 시 semantic_search 로드 + build_index
    if _SEM_MOD is None:
        try:
            import semantic_search as _mod   # sys.path에서 /app/query 우선 로드
            if _mod.index_size() == 0:
                _mod.build_index()
            _SEM_MOD = _mod
        except Exception as _e:
            import logging
            logging.getLogger("diagnose_engine").warning(f"semantic_search 초기화 실패: {_e}")
            return []

    try:
        _sem = _SEM_MOD
        if _sem is None or _sem.index_size() == 0:
            return []

        sem_results = _sem.search(query, n=n)
        results = []
        for r in sem_results:
            score = r["score"]
            if score < 0.40:
                # OOD — 최상위 결과만 낮은 점수로 포함 (미지 에러 플래그용)
                if not results:
                    results.append({
                        "type":         "sim_error_ood",
                        "title":        f"[미지에러] {r.get('error_type','Unknown')}: {str(r.get('error_message',''))[:50]}",
                        "cause":        r.get("root_cause", ""),
                        "solution":     "",
                        "code":         "",
                        "url":          "",
                        "score":        round(score, 3),
                        "source":       "kb_semantic:ood",
                        "is_ood":       True,
                        "sem_score":    round(score, 3),
                    })
                break

            # 신뢰 수준 결정
            confidence_level = "high" if score >= 0.60 else "medium"
            fixed_code = r.get("fixed_code", "") or ""
            results.append({
                "type":         "sim_error_semantic",
                "title":        f"[시맨틱:{confidence_level}] {r.get('error_type','')}: {str(r.get('error_message',''))[:60]}",
                "cause":        r.get("root_cause", "") or "",
                "solution":     r.get("fix_description", "") or "",
                "code":         fixed_code[:400],
                "url":          "",
                "score":        round(score, 3),
                "source":       f"kb_semantic:{r.get('source','db')}",
                "is_ood":       False,
                "sem_score":    round(score, 3),
                "confidence":   r.get("confidence", "medium"),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:n]

    except ImportError:
        # semantic_search 모듈 없으면 기존 chromadb 방식 fallback
        if not model or not client:
            return []
        try:
            embedding = model.encode([query])[0].tolist()
            results = []
            seen_titles = set()
            for coll_name in ["sim_errors_v1", "errors", "examples"]:
                try:
                    collection = client.get_collection(coll_name)
                    res = collection.query(query_embeddings=[embedding], n_results=n)
                    if res and res["documents"]:
                        for i, doc in enumerate(res["documents"][0]):
                            meta  = res["metadatas"][0][i] if res.get("metadatas") else {}
                            dist  = res["distances"][0][i] if res.get("distances") else 1.0
                            score = max(0, 1.0 - dist)
                            title = meta.get("title", "")
                            if score >= 0.25 and title not in seen_titles:
                                seen_titles.add(title)
                                results.append({
                                    "type": meta.get("type", "unknown"),
                                    "title": title,
                                    "cause": meta.get("cause", ""),
                                    "solution": doc[:500],
                                    "url": meta.get("url", ""),
                                    "score": round(score, 3),
                                    "source": f"kb_vector:{coll_name}",
                                })
                except Exception:
                    continue
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:n]
        except Exception:
            return []
    except Exception as e:
        return []


def extract_physics_context(code: str) -> dict:
    """MEEP 코드에서 물리적 파라미터 자동 추출"""
    ctx = {}

    # resolution
    m = re.search(r'resolution\s*=\s*([\d.]+)', code)
    if m: ctx["resolution"] = float(m.group(1))

    # cell size — Vector3(x, y) or Vector3(x, y, z)
    m = re.search(r'cell_size\s*=\s*mp\.Vector3\(([^)]+)\)', code)
    if m:
        ctx["cell_size"] = m.group(1).strip()
        parts = [p.strip() for p in m.group(1).split(",")]
        try:
            ctx["cell_x"] = float(parts[0]) if parts[0] else 0.0
            ctx["cell_y"] = float(parts[1]) if len(parts) > 1 else 0.0
            ctx["cell_z"] = float(parts[2]) if len(parts) > 2 else 0.0
        except ValueError:
            pass

    # PML thickness — PML(1.0) or PML(thickness=1.0)
    m = re.search(r'PML\s*\(\s*(?:thickness\s*=\s*)?([\d.]+)', code)
    if m: ctx["pml_thickness"] = float(m.group(1))

    # frequency / wavelength
    m = re.search(r'fcen\s*=\s*([\d.]+)', code)
    if m: ctx["fcen"] = float(m.group(1))
    m = re.search(r'wavelength\s*=\s*([\d.]+)', code)
    if m: ctx["wavelength"] = float(m.group(1))

    # dt / courant
    m = re.search(r'courant\s*=\s*([\d.]+)', code)
    if m: ctx["courant"] = float(m.group(1))

    # source bandwidth
    m = re.search(r'fwidth\s*=\s*([\d.eE+\-]+)', code)
    if m: ctx["fwidth"] = m.group(1)

    # geometry materials
    materials = re.findall(r'mp\.(Medium|silicon|SiO2|air|vacuum|glass)\b', code, re.IGNORECASE)
    if materials: ctx["materials"] = list(set(materials))

    # epsilon — index=N 또는 epsilon=N 모두 수집, index → epsilon 변환
    epsilons = re.findall(r'epsilon\s*=\s*([\d.]+)', code)
    indices  = re.findall(r'index\s*=\s*([\d.]+)', code)
    all_eps  = [float(e) for e in epsilons[:3]]
    all_eps += [float(i)**2 for i in indices[:3]]
    if all_eps: ctx["epsilons"] = sorted(set(all_eps), reverse=True)[:4]

    # MPI / num_chunks
    if 'num_chunks' in code or 'split_chunks' in code:
        ctx["uses_mpi"] = True

    # adjoint
    if 'OptimizationProblem' in code or 'adjoint' in code.lower():
        ctx["uses_adjoint"] = True

    # symmetry
    if 'Symmetry' in code or 'Mirror' in code:
        ctx["uses_symmetry"] = True

    # k_point 비영 여부
    kp = re.search(r'k_point\s*=\s*mp\.Vector3\(([^)]+)\)', code)
    if kp:
        vals = kp.group(1).split(",")
        non_zero = [v.strip() for v in vals if v.strip() not in ("0", "0.0", "")]
        if non_zero:
            ctx["k_point_nonzero"] = True

    return ctx


# ─────────────────────────────────────────────────────────────────────────────
# 물리/수치 정적 분석 — check_physics_issues()
# ─────────────────────────────────────────────────────────────────────────────

def _extract_source_center(code: str):
    """
    코드에서 Source center 좌표 추출.
    mp.Source(..., center=mp.Vector3(x, y)) 패턴.
    Returns (x, y, z) float tuple 또는 None.

    중첩 괄호 문제 해결: Source 전체 블록에서 center= 추출
    """
    # 방법1: center=mp.Vector3(x, y) 리터럴 좌표 직접 추출
    m = re.search(
        r'center\s*=\s*mp\.Vector3\s*\(\s*([\-\d.]+)\s*,\s*([\-\d.]+)',
        code
    )
    if m:
        try:
            return (float(m.group(1)), float(m.group(2)), 0.0)
        except ValueError:
            pass

    # 방법2: src_pt = mp.Vector3(x, y) → center=src_pt 패턴
    for var_name in ['src_pt', 'src_center', 'source_center', 'source_pt']:
        vec_m = re.search(
            rf'{var_name}\s*=\s*mp\.Vector3\s*\(\s*([\-\d.]+)\s*,\s*([\-\d.]+)',
            code
        )
        if vec_m:
            try:
                return (float(vec_m.group(1)), float(vec_m.group(2)), 0.0)
            except ValueError:
                pass

    return None


def check_physics_issues(code: str, phys_ctx: dict) -> list:
    """
    MEEP 코드에서 물리/수치 문제를 정적 분석으로 탐지.

    Returns list of:
        {
          "rule":     str,   # 규칙 ID
          "severity": str,   # critical | warning | info
          "message":  str,   # 한 줄 설명
          "fix_hint": str,   # 수정 방법
        }
    """
    issues = []

    res      = phys_ctx.get("resolution")
    pml      = phys_ctx.get("pml_thickness")
    fcen     = phys_ctx.get("fcen")
    courant  = phys_ctx.get("courant")
    epsilons = phys_ctx.get("epsilons", [])
    cell_y   = phys_ctx.get("cell_y")

    # ── 규칙 1: SRC_IN_PML ────────────────────────────────────────────────
    # cell_y가 수식 변수(sy 등)인 경우도 처리
    cell_y_val = cell_y
    if cell_y_val is None:
        # sy = N.N 패턴에서 직접 추출
        for var in ['sy', 'cell_y', 'Sy', 'sy_cell']:
            m_sy = re.search(rf'\b{var}\s*=\s*([\d.]+)', code)
            if m_sy:
                try:
                    cell_y_val = float(m_sy.group(1))
                    break
                except ValueError:
                    pass

    # pml도 변수인 경우 처리
    pml_val = pml
    if pml_val is None:
        for var in ['dpml', 'pml_thickness', 'pml_size', 'dpml_y']:
            m_pml = re.search(rf'\b{var}\s*=\s*([\d.]+)', code)
            if m_pml:
                try:
                    pml_val = float(m_pml.group(1))
                    break
                except ValueError:
                    pass

    if pml_val is not None and cell_y_val is not None and cell_y_val > 0:
        src_coords = _extract_source_center(code)
        if src_coords is not None:
            src_y = src_coords[1]
            pml_inner = cell_y_val / 2.0 - pml_val
            if pml_inner > 0 and abs(src_y) > pml_inner * 0.95:
                issues.append({
                    "rule": "SRC_IN_PML",
                    "severity": "critical",
                    "message": (
                        f"소스 center.y={src_y:.3f} — PML 경계 y=±{pml_inner:.3f} 내부/근접 "
                        f"(cell_y={cell_y_val}, pml={pml_val})"
                    ),
                    "fix_hint": (
                        f"소스를 PML 밖 기판 영역에 배치하세요:\n"
                        f"  src_pt = mp.Vector3(0, -0.5*sy + dpml + 0.5*dsub)\n"
                        f"PML 두께={pml_val}, 소스 y 범위: ({-pml_inner:.3f}, {pml_inner:.3f})"
                    ),
                })

    # ── 규칙 2: PML_TOO_THIN ─────────────────────────────────────────────
    pml_for_thin = pml_val or pml
    if res is not None and pml_for_thin is not None:
        pml_cells = res * pml_for_thin
        if pml_cells < 8:
            req_pml = 8.0 / res
            issues.append({
                "rule": "PML_TOO_THIN",
                "severity": "warning",
                "message": (
                    f"PML {pml_cells:.1f}셀 — 최소 8셀 필요 "
                    f"(resolution={res}, pml={pml_for_thin})"
                ),
                "fix_hint": (
                    f"PML 두께를 {req_pml:.2f} 이상으로 늘리세요:\n"
                    f"  dpml = {req_pml:.1f}\n"
                    f"  pml_layers = [mp.PML(thickness=dpml)]\n"
                    f"권장: PML ≈ 1/fcen (파장) 이상"
                ),
            })

    # ── 규칙 3: LOW_RESOLUTION ───────────────────────────────────────────
    if res is not None and fcen is not None and epsilons:
        max_eps = max(epsilons)
        n_eff   = max_eps ** 0.5
        req_res = 8.0 * fcen * n_eff
        if res < req_res * 0.8:
            issues.append({
                "rule": "LOW_RESOLUTION",
                "severity": "warning",
                "message": (
                    f"resolution={res} — ε={max_eps:.1f}(n≈{n_eff:.2f}), "
                    f"fcen={fcen:.3f}에서 권장값 {req_res:.0f} 미달"
                ),
                "fix_hint": (
                    f"resolution을 {int(req_res)+1} 이상으로 높이세요:\n"
                    f"  resolution = {int(req_res)+1}\n"
                    f"기준: 8 × fcen × sqrt(ε) = 8 × {fcen:.3f} × {n_eff:.2f}"
                ),
            })

    # ── 규칙 4: COURANT_HIGH ─────────────────────────────────────────────
    if courant is not None and courant >= 0.5:
        issues.append({
            "rule": "COURANT_HIGH",
            "severity": "warning",
            "message": (
                f"courant={courant} — MEEP 권장 상한 0.5 초과 (수치 불안정)"
            ),
            "fix_hint": (
                f"courant 줄이거나 제거하세요 (기본값 0.5가 안전):\n"
                f"  # courant={courant}  ← 이 줄 삭제 또는\n"
                f"  courant = 0.5  # 명시적 설정"
            ),
        })

    # ── 규칙 5: ADJOINT_NO_RESET ─────────────────────────────────────────
    if "OptimizationProblem" in code:
        opt_calls = len(re.findall(r'\bopt\s*\(', code))
        if opt_calls > 1 and "reset_meep" not in code:
            issues.append({
                "rule": "ADJOINT_NO_RESET",
                "severity": "warning",
                "message": (
                    f"OptimizationProblem opt() {opt_calls}회 호출 — "
                    f"reset_meep() 미사용 (changed_materials 버그 가능)"
                ),
                "fix_hint": (
                    "MEEP 1.31 미만: optimization_problem.py L552 reset_meep() 버그.\n"
                    "각 opt() 전에 추가하거나 MEEP 1.31+ 사용:\n"
                    "  opt.sim.reset_meep()\n"
                    "  f, dJ = opt([x], need_gradient=True)"
                ),
            })

    # ── 규칙 6: EIGENMODE_NO_PARITY ──────────────────────────────────────
    if re.search(r'EigenModeSource|EigenmodeSource', code):
        if "eig_parity" not in code:
            issues.append({
                "rule": "EIGENMODE_NO_PARITY",
                "severity": "info",
                "message": "EigenModeSource에 eig_parity 미설정 (모드 탐색 실패 가능)",
                "fix_hint": (
                    "편광에 맞는 eig_parity를 추가하세요:\n"
                    "  TE: eig_parity=mp.EVEN_Y + mp.ODD_Z\n"
                    "  TM: eig_parity=mp.ODD_Y + mp.EVEN_Z\n"
                    "  1D P-pol grating: eig_parity=mp.EVEN_Z"
                ),
            })

    # ── 규칙 7: K_POINT_NO_COMPLEX ───────────────────────────────────────
    # k_point= 또는 eig_kpoint= 비영 사용 시
    has_nonzero_k = phys_ctx.get("k_point_nonzero", False)
    if not has_nonzero_k:
        # eig_kpoint=mp.Vector3(x,y,z) 패턴 체크
        eig_kp = re.search(r'eig_kpoint\s*=\s*mp\.Vector3\(([^)]+)\)', code)
        if eig_kp:
            vals = eig_kp.group(1).split(",")
            non_zero = [v.strip() for v in vals if v.strip() not in ("0", "0.0", "")]
            if non_zero:
                has_nonzero_k = True

    if has_nonzero_k and "force_complex_fields" not in code:
        issues.append({
            "rule": "K_POINT_NO_COMPLEX",
            "severity": "info",
            "message": "비영 k_point/eig_kpoint 사용 — force_complex_fields=True 권장",
            "fix_hint": (
                "mp.Simulation()에 force_complex_fields=True 추가:\n"
                "  sim = mp.Simulation(\n"
                "      ...,\n"
                "      k_point=k_point,\n"
                "      force_complex_fields=True,  # ← 추가\n"
                "  )"
            ),
        })

    return issues


def build_physics_diagnosis_prompt(code: str, error: str,
                                   error_info: dict, db_results: list,
                                   phys_ctx: dict,
                                   physics_issues: list = None) -> str:
    """MEEP 물리 도메인에 특화된 진단 프롬프트 생성"""

    # ── 정적 분석 이슈 섹션 ──────────────────────────────────────────────────
    issues_section = ""
    if physics_issues:
        issues_section = "\n\n## 정적 분석 감지 이슈\n"
        sev_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
        for iss in physics_issues:
            icon = sev_icon.get(iss["severity"], "•")
            issues_section += f"\n{icon} **{iss['rule']}** ({iss['severity']}): {iss['message']}\n"
            issues_section += f"  → 수정 방법: {iss['fix_hint']}\n"
        issues_section += "\n**위 이슈를 최우선으로 수정 코드에 반영하세요.**"

    # ── DB 지식 컨텍스트 ──────────────────────────────────────────────────────
    db_section = ""
    if db_results:
        db_section = "\n\n## meep-kb 지식베이스 관련 항목\n"
        for i, r in enumerate(db_results[:3]):
            db_section += f"\n### [{i+1}] {r.get('title','')}"
            if r.get("cause"):
                db_section += f"\n- **원인**: {r['cause'][:300]}"
            if r.get("solution"):
                db_section += f"\n- **해결책**: {r['solution'][:300]}"
            if r.get("code"):
                db_section += f"\n```python\n{r['code'][:400]}\n```"
        db_section += "\n\n**위 DB 지식을 최우선으로 활용하고, DB에 없는 경우만 추론하세요.**"

    # ── 물리 파라미터 컨텍스트 ───────────────────────────────────────────────
    phys_section = ""
    if phys_ctx:
        phys_section = "\n\n## 코드에서 추출된 물리 파라미터\n"
        if "resolution" in phys_ctx:
            res = phys_ctx["resolution"]
            # 수치 안정성 힌트
            courant = phys_ctx.get("courant", 0.5)
            phys_section += f"- resolution={res} (dt≈{courant/(res*2):.4f} MEEP units)\n"
        if "cell_size" in phys_ctx:
            phys_section += f"- cell_size: {phys_ctx['cell_size']}\n"
        if "pml_thickness" in phys_ctx:
            pml = phys_ctx["pml_thickness"]
            res = phys_ctx.get("resolution", 0)
            if res > 0:
                pml_cells = pml * res
                hint = "⚠️ PML 셀 수 부족 (<8)" if pml_cells < 8 else "✅ PML 충분"
                phys_section += f"- PML={pml} ({pml_cells:.0f}셀, {hint})\n"
        if "fcen" in phys_ctx:
            phys_section += f"- 중심주파수 fcen={phys_ctx['fcen']}\n"
        if "fwidth" in phys_ctx:
            phys_section += f"- 소스 대역폭 fwidth={phys_ctx['fwidth']}\n"
        if "epsilons" in phys_ctx:
            phys_section += f"- 유전율 ε={phys_ctx['epsilons']}\n"
        if phys_ctx.get("uses_adjoint"):
            phys_section += "- ⚡ Adjoint 최적화 사용\n"

    # ── 에러 타입별 물리 힌트 ────────────────────────────────────────────────
    err_hints = {
        "Divergence": """
**수치 발산 체크리스트:**
1. Courant 조건: dt < dx/(c√D) — resolution 낮으면 dt 자동 증가로 발산
2. PML이 너무 얇거나 (권장: 파장의 1~2배), 또는 소스가 PML 내부에 위치
3. 고유전율 재료(ε>20)에서 resolution 부족 시 발산
4. `force_complex_fields=True` 미설정 시 특정 모드에서 불안정
5. `decay_by` 조건 대신 고정 시간(`until`)으로 발산 전에 종료 고려""",

        "AdjointBug": """
**Adjoint 버그 체크리스트 (pmp130 환경 알려진 이슈):**
1. `optimization_problem.py` L552 `reset_meep()` 호출이 `changed_materials` 충돌 유발
2. 해결: L552를 주석 처리 (`# self.reset_meep()`)
3. 또는 MEEP 1.31.0+ 사용 (버그 수정됨)
4. `update_design()` 후 `prepare_forward_run()` 중복 호출 여부 확인""",

        "EigenMode": """
**EigenModeSource 체크리스트:**
1. `eig_parity`가 구조 대칭과 일치하는지 확인 (EVEN_Y+ODD_Z for TE, ODD_Y+EVEN_Z for TM)
2. `eig_kpoint` 방향이 전파 방향과 일치해야 함
3. 소스 크기(`size`)가 도파관보다 충분히 크게 (최소 셀 높이의 70% 이상)
4. `resolution`이 최소 파장/재료굴절률의 8배 이상 권장
5. 소스 위치가 균일한 재료 영역에 있어야 함 (경계면 근처 금지)""",

        "NumericalError": """
**수치 불안정 체크리스트:**
1. NaN: 보통 발산의 전조 — resolution 증가 또는 Courant 감소
2. Inf: PML 흡수 실패 — PML 두께 증가 또는 위치 조정
3. 복소 모드에서 실수 필드 사용 시 → `force_complex_fields=True`
4. 재료 분산(dispersive) 모델 파라미터 범위 초과 여부 확인""",

        "MPIError": """
**MPI 병렬화 체크리스트:**
1. `num_chunks` > 코어 수: 불균형 분할로 OOM 유발 가능
2. `mpi4py` 버전 MPICH/OpenMPI 버전 불일치
3. 큰 배열 gather 시 rank 0 메모리 부족 → `meep.Simulation.get_array()` 분산 처리
4. `mp.quiet(True)` 설정으로 출력 중복 방지""",
    }

    primary_type = error_info.get("primary_type", "")
    physics_hint = ""
    for err_type, hint in err_hints.items():
        if err_type.lower() in primary_type.lower():
            physics_hint = f"\n\n## 물리/수치 진단 가이드\n{hint}"
            break

    return f"""당신은 MEEP FDTD 시뮬레이션 + Photonics inverse design 전문가입니다.
일반적인 Python 디버거가 아닌, **MEEP API와 전자기 물리 법칙을 깊이 이해한** 관점으로 분석하세요.
{db_section}{phys_section}{issues_section}{physics_hint}

## 제출된 코드
```python
{code[:3000]}
```

## 에러 메시지
```
{error[:1500]}
```

## 요청 형식 (반드시 이 구조로 답하세요)

### 🔍 근본 원인
[MEEP/물리 관점에서 에러의 근본 원인을 1~3문장으로 설명.
단순히 "속성이 없다"가 아니라 왜 그 API가 그렇게 동작하는지 설명]

### ⚡ 물리적 해석
[이 에러가 시뮬레이션 물리에 미치는 영향. 예: "PML이 얇으면 반사파가 생겨 결과가 부정확해짐"]

### 🔧 수정된 전체 코드
아래에 반드시 **실행 가능한 전체 코드**를 출력하세요. 변경 부분에 # FIXED: 이유 주석 추가.
```python
# 수정된 전체 코드 (실행 가능)
```

### ✅ 검증 방법
[수정 후 올바르게 동작하는지 확인하는 방법 1~2가지]

**DB 지식이 있으면 우선 활용하고, 없을 때만 물리적 추론으로 보완하세요.**"""


def extract_fixed_code(llm_answer: str, original_code: str) -> str | None:
    """
    LLM 답변에서 수정된 전체 코드 블록을 추출.
    우선순위:
      1. ```python ... ``` 블록 중 원본 코드 길이의 30% 이상인 것
      2. 없으면 가장 긴 코드 블록
      3. 없으면 None
    """
    import re as _re
    blocks = _re.findall(r'```python\s*(.*?)```', llm_answer, _re.DOTALL)
    if not blocks:
        blocks = _re.findall(r'```\s*(.*?)```', llm_answer, _re.DOTALL)
    if not blocks:
        return None

    # 원본 길이 기준 30% 이상 + import meep 포함 우선
    threshold = max(len(original_code) * 0.3, 100)
    valid = [b.strip() for b in blocks
             if len(b.strip()) >= threshold]
    if not valid:
        valid = [b.strip() for b in blocks if b.strip()]
    if not valid:
        return None

    # "import meep" 포함된 것 우선, 아니면 가장 긴 것
    meep_blocks = [b for b in valid if "import meep" in b or "import mp" in b.lower()]
    return max(meep_blocks or valid, key=len)


def llm_diagnose(code: str, error: str, db_results: list,
                 error_info: dict = None,
                 physics_issues: list = None) -> dict:
    """MEEP 물리 도메인 특화 LLM 진단 (DB 결과 + 물리 컨텍스트 활용)"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"available": False, "reason": "ANTHROPIC_API_KEY 없음"}

    if error_info is None:
        error_info = {}

    # 물리 파라미터 추출
    phys_ctx = extract_physics_context(code)

    # 특화 프롬프트 생성 (physics_issues 포함)
    prompt = build_physics_diagnosis_prompt(
        code, error, error_info, db_results, phys_ctx,
        physics_issues=physics_issues or []
    )

    try:
        import urllib.request, json
        body = json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
            text = data["content"][0]["text"]
            fixed = extract_fixed_code(text, code)
            return {
                "available": True,
                "answer": text,
                "fixed_code": fixed,
                "physics_context": phys_ctx,
            }
    except Exception as e:
        return {"available": False, "reason": str(e)}


def check_mpi_deadlock_risk(code: str) -> dict:
    """
    MEEP 코드에서 MPI deadlock 유발 가능 패턴을 사전 검토.
    실행 전에 호출하여 deadlock 위험이 있으면 사용자에게 경고.

    Returns:
        {
          "risk_level": "none" | "low" | "medium" | "high",
          "issues": [...],      # 발견된 위험 패턴 목록
          "safe_to_run": bool,  # True면 MPI 실행 안전
          "recommendations": [...],  # 권장 조치
        }
    """
    issues = []
    recommendations = []

    # ── 1. sys.exit() / os._exit() in non-rank-0 ─────────────────────────────
    if re.search(r'\bsys\.exit\b|\bos\._exit\b|\bexit\(\)', code):
        issues.append({
            "pattern": "sys.exit() / os._exit() 감지",
            "risk": "high",
            "reason": "MPI 환경에서 일부 rank만 종료 시 나머지 rank가 MPI_Barrier에서 무한 대기 (deadlock)",
            "fix": "sys.exit() 대신 `if mp.am_master(): sys.exit()` 또는 MPI_Finalize 후 종료 패턴 사용"
        })

    # ── 2. print() in all ranks (collective 아님, 단독 print는 안전하나 flush 문제) ─
    # 실제 위험: print 후 MPI_Barrier 순서 어긋남
    if re.search(r'mpirun|MPI_Comm_rank|mp\.comm_rank', code):
        if re.search(r'\bprint\s*\(', code) and not re.search(r'mp\.am_master\(\)', code):
            issues.append({
                "pattern": "MPI 환경에서 모든 rank에서 print() 호출",
                "risk": "low",
                "reason": "stdout flush 타이밍 불일치로 출력 혼재 가능. 직접 deadlock 원인은 아니지만 디버깅 어려움",
                "fix": "`if mp.am_master(): print(...)` 로 rank 0에서만 출력"
            })

    # ── 3. mp.Simulation 없이 mp 함수 호출 ──────────────────────────────────
    if re.search(r'mpirun|from mpi4py', code):
        if not re.search(r'mp\.Simulation\s*\(', code):
            issues.append({
                "pattern": "MPI 사용하지만 mp.Simulation 객체 없음",
                "risk": "medium",
                "reason": "MEEP MPI는 Simulation 객체 없이 collective 연산 호출 시 rank 불일치 발생 가능",
                "fix": "Simulation 객체를 먼저 생성 후 MPI 연산 수행"
            })

    # ── 4. input() / stdin 읽기 ──────────────────────────────────────────────
    if re.search(r'\binput\s*\(|\bsys\.stdin\b|\braw_input\b', code):
        issues.append({
            "pattern": "input() / sys.stdin 감지",
            "risk": "high",
            "reason": "MPI 환경에서 stdin 읽기는 rank 0만 stdin에 연결 → 나머지 rank deadlock",
            "fix": "input() 제거. 파라미터는 argparse나 config 파일로 전달"
        })

    # ── 5. 파일 I/O를 모든 rank에서 동시에 ─────────────────────────────────
    # 동일한 파일을 여러 rank가 쓰면 충돌
    if re.search(r'open\s*\(.*["\']w["\']', code) and not re.search(r'mp\.am_master\(\)', code):
        if re.search(r'mpirun|from mpi4py|mp\.comm_rank', code):
            issues.append({
                "pattern": "모든 rank에서 파일 쓰기 (write 모드)",
                "risk": "medium",
                "reason": "여러 MPI rank가 동일 파일에 쓰면 파일 충돌 또는 데이터 손상 가능",
                "fix": "`if mp.am_master(): open(...)` 또는 rank별 파일명 분리"
            })

    # ── 6. Barrier 없는 collective 연산 (get_array 등) ──────────────────────
    collective_ops = re.findall(
        r'sim\.get_array|mp\.get_fluxes|sim\.get_eigenmode_coefficients|'
        r'sim\.fields\.synchronize_magnetic_fields', code
    )
    if collective_ops:
        # wait for fields decayed 없이 즉시 collective 호출 체크
        if not re.search(r'stop_when_fields_decayed|run\(.*until', code):
            issues.append({
                "pattern": f"collective 연산 ({', '.join(set(collective_ops[:3]))}) 사전 동기화 없음",
                "risk": "medium",
                "reason": "필드 수렴 전 collective 연산 호출 시 rank간 타이밍 불일치로 deadlock 가능",
                "fix": "stop_when_fields_decayed 또는 충분한 until 값으로 수렴 확인 후 get_array 호출"
            })

    # ── 7. try-except로 MPI collective 감싸기 ───────────────────────────────
    # 일부 rank만 exception → 나머지 rank는 barrier에서 대기
    if re.search(r'try\s*:', code):
        try_blocks = re.findall(r'try\s*:.*?(?=try\s*:|$)', code, re.DOTALL)
        for block in try_blocks[:5]:
            collective_in_try = re.search(
                r'sim\.run|sim\.get_array|mp\.get_fluxes|'
                r'sim\.get_eigenmode_coefficients', block
            )
            if collective_in_try:
                issues.append({
                    "pattern": "try-except 안에 MPI collective 연산 (sim.run, get_array 등)",
                    "risk": "high",
                    "reason": "일부 rank에서 exception 발생 시 해당 rank는 except로 빠지고 나머지는 collective에서 무한 대기 → deadlock",
                    "fix": "try 블록에서 MPI collective 연산 제거. 에러는 모든 rank가 동시에 처리하도록 설계"
                })
                break

    # ── 8. mpirun 없이 mp.divide_parallel_processes ─────────────────────────
    if re.search(r'mp\.divide_parallel_processes|mp\.merge_subgroup', code):
        if not re.search(r'mp\.count_processors\(\)|mp\.my_rank\(\)', code):
            issues.append({
                "pattern": "divide_parallel_processes 사용 시 rank 수 확인 없음",
                "risk": "medium",
                "reason": "프로세스 수가 분할 그룹 수보다 적으면 deadlock",
                "fix": "실행 전 `assert mp.count_processors() >= num_groups` 체크 추가"
            })

    # ── 9. sleep() in parallel context ──────────────────────────────────────
    if re.search(r'time\.sleep|os\.system', code):
        if re.search(r'mpirun|from mpi4py', code):
            issues.append({
                "pattern": "MPI 환경에서 time.sleep() 또는 os.system() 감지",
                "risk": "low",
                "reason": "rank별 sleep 시간 차이로 collective 연산 타이밍 불일치 발생 가능",
                "fix": "sleep 대신 stop_when_fields_decayed 조건 사용. os.system()은 rank 0에서만 실행"
            })

    # ── 10. 무한 루프 (while True) + MPI collective ─────────────────────────
    if re.search(r'while\s+True\s*:', code):
        if re.search(r'sim\.run|sim\.get_array|mp\.get_fluxes', code):
            issues.append({
                "pattern": "while True 루프 내 MPI collective 연산",
                "risk": "high",
                "reason": "루프 종료 조건 불일치 시 일부 rank만 루프 탈출 → deadlock",
                "fix": "루프 종료 조건을 모든 rank가 동시에 평가하도록 설계. mp.broadcast()로 종료 시그널 공유"
            })

    # ── 위험도 집계 ───────────────────────────────────────────────────────────
    risk_levels = [i["risk"] for i in issues]
    if "high" in risk_levels:
        overall = "high"
        safe_to_run = False
    elif "medium" in risk_levels:
        overall = "medium"
        safe_to_run = True  # 실행은 가능하나 주의 필요
    elif "low" in risk_levels:
        overall = "low"
        safe_to_run = True
    else:
        overall = "none"
        safe_to_run = True

    # 권장 조치
    if overall == "high":
        recommendations.append("[HIGH RISK] mpirun 실행 전 반드시 코드 수정 필요. deadlock 발생 시 강제 종료: `pkill -9 -f mpirun`")
    if overall in ("high", "medium"):
        recommendations.append("실행 시 타임아웃 설정 권장: `timeout 300 mpirun -np N python script.py`")
        recommendations.append("deadlock 감지: 별도 터미널에서 `watch -n 5 'pgrep -a mpirun'`")
    if not issues:
        recommendations.append("[OK] MPI deadlock 위험 패턴 미발견. 안전하게 실행 가능")

    return {
        "risk_level":      overall,
        "safe_to_run":     safe_to_run,
        "issues":          issues,
        "issue_count":     len(issues),
        "recommendations": recommendations,
    }


def diagnose(code: str, error: str, n: int = 5,
             model=None, client=None) -> dict:
    """
    메인 진단 함수
    Returns:
        {
          "error_info": {...},
          "db_results": [...],
          "db_sufficient": bool,
          "llm_result": {...} | None,
          "mode": "db_only" | "db+llm" | "llm_only",
          "suggestions": [...],  # 최종 수정 제안 목록
          "physics_issues": [...],  # 정적 분석 결과
          "fixed_code": str | None, # 수정된 코드
        }
    """
    # 1. 에러 파싱
    error_info = parse_error(code, error)

    # 2. 물리 컨텍스트 추출 + 정적 분석
    phys_ctx = extract_physics_context(code)
    physics_issues = check_physics_issues(code, phys_ctx)

    # 3. DB 검색 (keyword)
    db_results = search_db(error_info, code, error, n=n)

    # 4. 시맨틱 검색 (fastembed/bge-small-en-v1.5)
    sem_query = f"{error_info['primary_type']} {error_info['last_error_line']} {' '.join(error_info['meep_keywords'][:3])} {error or ''}".strip()[:700]
    vec_results = search_vector(sem_query, n=3, model=model, client=client)

    # OOD 감지: 시맨틱 점수가 모두 낮으면 → 미지 에러
    ood_detected = False
    if vec_results:
        best_sem = max((r.get("sem_score", 0) for r in vec_results), default=0)
        ood_detected = best_sem < 0.40 and best_sem > 0   # 0은 시맨틱 비활성

    # 통합 + 중복 제거
    # db_results와 vec_results를 함께 사용 (is_ood=True인 것은 제외)
    seen_msgs = {x.get("title","")[:40] for x in db_results}
    merged_vec = []
    for r in vec_results:
        if r.get("is_ood"):
            continue  # OOD 결과는 통합에서 제외
        if r.get("title","")[:40] in seen_msgs:
            continue  # 중복 제외
        seen_msgs.add(r.get("title","")[:40])
        # sem_score를 최종 score에 반영 (가중 평균)
        sem_s = r.get("sem_score", 0)
        # 시맨틱 score는 보조 신호로만 사용 (최대 +0.05)
        r["score"] = min(1.0, r["score"] + sem_s * 0.05)
        merged_vec.append(r)

    all_results = db_results + merged_vec
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    all_results = all_results[:n]
    # 4. DB 충분성 판단
    top_score = all_results[0]["score"] if all_results else 0
    db_sufficient = top_score >= 0.55 and len(all_results) >= 1

    # 5. LLM 폴백 결정 (OOD이거나 DB 부족할 때)
    llm_result = None
    if not db_sufficient or ood_detected:
        llm_result = llm_diagnose(
            code, error, all_results,
            error_info=error_info,
            physics_issues=physics_issues,
        )

    # 5a. OOD + LLM 결과가 있으면 자동 학습 파이프라인 실행
    if ood_detected and llm_result:
        try:
            import asyncio
            from auto_learn_pipeline import learn_from_unknown_error
            learn_result = asyncio.get_event_loop().run_until_complete(
                learn_from_unknown_error(code, error, llm_result)
            )
            if learn_result and learn_result.get("learned"):
                import logging
                logging.getLogger("auto_learn").info(
                    f"Auto-learned: id={learn_result['new_id']} verified={learn_result['verified']}"
                )
        except Exception:
            pass   # 학습 실패해도 진단 결과는 반환

    # DB hit에서 fixed_code 추출 시도
    db_fixed_code = None
    for r in all_results:
        if r.get("code") and len(r["code"]) > max(len(code) * 0.3, 100):
            db_fixed_code = r["code"]
            break

    # fixed_code 우선순위: LLM > DB
    fixed_code = (
        (llm_result or {}).get("fixed_code")
        or db_fixed_code
    )

    # 6. 최종 제안 목록 구성
    suggestions = []
    for r in all_results[:3]:
        s = {
            "source":  r.get("source", "kb"),
            "title":   r.get("title", ""),
            "score":   r.get("score", 0),
            "type":    r.get("type", ""),
        }
        if r.get("cause"):
            s["cause"]    = r["cause"]
        if r.get("solution"):
            s["solution"] = r["solution"]
        if r.get("code"):
            s["code"]     = r["code"]
        if r.get("url"):
            s["url"]      = r["url"]
        suggestions.append(s)

    mode = "db_only" if db_sufficient else ("db+llm" if llm_result and llm_result.get("available") else "db_only_low_confidence")

    # 7. 단계별 진단 프레임워크
    stages = detect_stage(code, error)
    diagnostic_stages = stages[:2] if stages else []
    primary_stage     = stages[0] if stages else None

    return {
        "error_info":        error_info,
        "db_results":        all_results,
        "db_sufficient":     db_sufficient,
        "top_score":         round(top_score, 3),
        "llm_result":        llm_result,
        "mode":              mode,
        "suggestions":       suggestions,
        "physics_context":   (llm_result or {}).get("physics_context", {}),
        "physics_issues":    physics_issues,
        "fixed_code":        fixed_code,
        "diagnostic_stages": diagnostic_stages,
        "primary_stage":     primary_stage,
    }
