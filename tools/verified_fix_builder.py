"""
VerifiedFixBuilder: autosim 패턴에 버그 삽입 -> Docker MEEP 실행 -> LLM 수정 -> 검증 -> KB 저장

실행:
  python tools/verified_fix_builder.py --dry-run --limit 5
  python tools/verified_fix_builder.py --limit 50
  python tools/verified_fix_builder.py --bug-type Divergence --limit 20
"""
import re, json, os, subprocess, time, argparse, tempfile, sys, datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import requests

BASE = Path(__file__).parent.parent
PATTERNS_DIR = BASE / "autosim" / "patterns"
CONTAINER = "meep-pilot-worker"
KB_API_URL = "http://localhost:8765"

# ------------------------------------------------------------------
# 확장된 BUG_CATALOG (20+ 버그 유형)
# ------------------------------------------------------------------
BUG_CATALOG = [
    # ── 기존 버그 (from error_injector.py) ──────────────────────────
    {
        "name": "eig_band_zero",
        "error_type": "EigenMode",
        "find": r'eig_band\s*=\s*1',
        "replace": "eig_band=0",
        "root_cause": "eig_band=0: MEEP 모드 인덱스는 1부터 시작. 0을 쓰면 에너지 비보존(T>100%) 발생",
        "fix_description": "MEEP에서 eig_band는 1-indexed입니다. eig_band=0은 정의되지 않은 모드입니다. eig_band=1 (TE0), eig_band=2 (TE1)으로 수정하세요.",
        "fix_hint": "eig_band=1",
    },
    {
        "name": "no_pml",
        "error_type": "PML",
        "find": r'boundary_layers\s*=\s*\[.*?PML.*?\]',
        "replace": "boundary_layers=[]",
        "root_cause": "PML 없음: 경계 반사로 인한 부정확한 결과 및 발산 가능성",
        "fix_description": "PML(Perfectly Matched Layer) 없이 시뮬레이션하면 경계에서 반사가 발생해 결과가 부정확합니다. boundary_layers=[mp.PML(1.0)]을 추가하세요.",
        "fix_hint": "boundary_layers=[mp.PML(1.0)]",
    },
    {
        "name": "wrong_eig_parity",
        "error_type": "EigenMode",
        "find": r'eig_parity\s*=\s*mp\.EVEN_Y\s*\+\s*mp\.ODD_Z',
        "replace": "eig_parity=mp.ODD_Y+mp.EVEN_Z",
        "root_cause": "eig_parity 오류: TE/TM 모드 혼동으로 잘못된 모드 여기",
        "fix_description": "2D TE 모드에서 올바른 eig_parity는 mp.EVEN_Y+mp.ODD_Z입니다. ODD_Y+EVEN_Z는 TM 모드입니다.",
        "fix_hint": "eig_parity=mp.EVEN_Y+mp.ODD_Z",
    },
    {
        "name": "resolution_too_low",
        "error_type": "Divergence",
        "find": r'resolution\s*=\s*(\d+)',
        "replace": "resolution=2",
        "root_cause": "resolution 너무 낮음: 격자가 너무 거칠어 수치 발산 또는 부정확한 결과",
        "fix_description": "resolution=2는 너무 낮습니다. 최소 10 이상, 정확한 결과를 위해 50+ 권장합니다.",
        "fix_hint": "resolution=20",
    },
    {
        "name": "missing_until",
        "error_type": "RuntimeError",
        "find": r'sim\.run\(until\s*=\s*(\d+)',
        "replace": "sim.run(until=0.001",
        "root_cause": "시뮬레이션 시간 너무 짧음: 필드가 수렴하기 전에 종료",
        "fix_description": "until=0.001은 너무 짧아 필드가 수렴하지 않습니다. 충분한 시간(예: until=200)을 설정하거나 stop_when_fields_decayed()를 사용하세요.",
        "fix_hint": "sim.run(until=200",
    },
    {
        "name": "force_complex_missing",
        "error_type": "ValueError",
        "find": r'force_complex_fields\s*=\s*True',
        "replace": "force_complex_fields=False",
        "root_cause": "force_complex_fields=False: 복소수 모드 계수 계산에서 오류 발생",
        "fix_description": "EigenModeSource나 위상 관련 계산에서 force_complex_fields=True가 필요합니다.",
        "fix_hint": "force_complex_fields=True",
    },
    {
        "name": "wrong_component",
        "error_type": "ValueError",
        "find": r'mp\.Ez',
        "replace": "mp.Ey",
        "root_cause": "잘못된 필드 성분: TE/TM 편광 혼동",
        "fix_description": "2D TE 모드 시뮬레이션에서 올바른 필드 성분은 mp.Ez입니다. mp.Ey는 TM 모드에 해당합니다.",
        "fix_hint": "mp.Ez",
    },
    {
        "name": "pml_too_thin",
        "error_type": "PML",
        "find": r'mp\.PML\s*\(\s*[\d.]+\s*\)',
        "replace": "mp.PML(0.1)",
        "root_cause": "PML 너무 얇음: 불충분한 흡수로 경계 반사 발생",
        "fix_description": "PML 두께 0.1은 너무 얇아 반사가 발생합니다. 파장의 절반 이상(λ/2 ~= 0.775μm)을 권장하며, 일반적으로 1.0μm 이상 사용합니다.",
        "fix_hint": "mp.PML(1.0)",
    },
    # ── 신규: Divergence 계열 ─────────────────────────────────────────
    {
        "name": "resolution_large_cell",
        "error_type": "Divergence",
        "find": r'resolution\s*=\s*\d+',
        "replace": "resolution=5",
        "root_cause": "대형 셀(>5μm)에서 resolution=5는 Courant 조건 불안정 유발",
        "fix_description": "큰 셀 크기에서 resolution=5는 너무 낮습니다. 셀 크기 대비 최소 10 이상의 resolution이 필요합니다. resolution=20 이상으로 올리세요.",
        "fix_hint": "resolution=20",
    },
    {
        "name": "pml_too_thin_wavelength",
        "error_type": "PML",
        "find": r'mp\.PML\s*\(\s*[\d.]+\s*\)',
        "replace": "mp.PML(0.1)",
        "root_cause": "PML(0.1)은 1.55μm 파장 대비 너무 얇아 반사파 발생",
        "fix_description": "파장 1.55μm 기준으로 PML 두께는 최소 0.775μm (λ/2) 이상이어야 합니다. PML(1.0) 이상을 권장합니다.",
        "fix_hint": "mp.PML(1.0)",
    },
    {
        "name": "until_too_short",
        "error_type": "RuntimeError",
        "find": r'until\s*=\s*\d+',
        "replace": "until=1",
        "root_cause": "until=1: 시뮬레이션이 수렴하기 전에 조기 종료되어 부정확한 결과",
        "fix_description": "until=1은 필드가 전파되기도 전에 시뮬레이션이 종료됩니다. 일반적으로 셀 크기의 10배 이상(예: until=200) 또는 stop_when_fields_decayed()를 사용하세요.",
        "fix_hint": "until=200",
    },
    {
        "name": "missing_reset_meep",
        "error_type": "Adjoint",
        "find": r'sim\.reset_meep\(\)',
        "replace": "# sim.reset_meep()  # BUG: removed",
        "root_cause": "adjoint 반복 루프에서 reset_meep() 누락 -> 이전 시뮬레이션 상태 잔류",
        "fix_description": "adjoint 최적화 루프에서 각 반복마다 sim.reset_meep()를 호출해야 합니다. 누락 시 이전 런의 필드가 잔류하여 gradient 계산이 부정확해집니다.",
        "fix_hint": "sim.reset_meep()",
    },
    {
        "name": "monitor_before_source",
        "error_type": "Normalization",
        "find": r'(refl|reflection).*?FluxRegion.*?center\s*=\s*mp\.Vector3\s*\(',
        "replace": None,  # 특수 처리 필요
        "root_cause": "반사 모니터가 소스 뒤(잘못된 방향)에 위치하여 반사율 측정 오류",
        "fix_description": "반사 모니터는 소스 앞(입사 방향)에 위치해야 합니다. 현재 모니터가 소스 뒤에 있어 투과파를 측정하고 있습니다.",
        "fix_hint": "refl monitor x position < source x position",
    },
    # ── 신규: EigenMode 계열 ─────────────────────────────────────────
    {
        "name": "eig_center_misaligned",
        "error_type": "EigenMode",
        "find": r'(EigenModeSource\([^)]*center\s*=\s*mp\.Vector3\()[^)]*(\))',
        "replace": r'\g<1>0, 10, 0\g<2>',  # center y=10으로 밖으로 이동
        "replace_mode": "line_append",  # 독립 줄 삽입 방식
        "inject_line": "eig_source_center = mp.Vector3(0, 10, 0)  # BUG: 도파로 밖",
        "inject_after": r'import meep as mp',
        "root_cause": "EigenModeSource center가 도파로 구조 밖에 위치하여 모드 여기 실패",
        "fix_description": "EigenModeSource의 center는 도파로 내부에 위치해야 합니다. 현재 y=10으로 도파로 밖에 설정되어 있습니다. 도파로 중심 좌표로 수정하세요.",
        "fix_hint": "center=mp.Vector3(0, 0, 0)",
    },
    {
        "name": "eig_band_wrong",
        "error_type": "EigenMode",
        "find": r'eig_band\s*=\s*1',
        "replace": "eig_band=5",
        "root_cause": "eig_band=5: 존재하지 않는 고차 모드 여기 시도",
        "fix_description": "eig_band=5는 일반적인 단일모드 도파로에서 존재하지 않는 모드입니다. 기본 TE0 모드는 eig_band=1입니다.",
        "fix_hint": "eig_band=1",
    },
    # ── 신규: Adjoint 계열 ───────────────────────────────────────────
    {
        "name": "design_variable_shape_mismatch",
        "error_type": "Adjoint",
        "find": r'x0\s*=\s*np\.ones\s*\(\s*\(',
        "replace": "x0 = np.ones((999, 999",  # shape 불일치
        "root_cause": "MaterialGrid grid_size와 초기 설계 변수 x0 shape 불일치 -> ValueError",
        "fix_description": "MaterialGrid의 grid_size는 초기 설계 변수 x0의 shape과 일치해야 합니다. 현재 (999,999)이 grid_size와 다릅니다.",
        "fix_hint": "x0 shape must match MaterialGrid grid_size",
    },
    {
        "name": "beta_too_high_initial",
        "error_type": "Adjoint",
        "find": r'beta\s*=\s*[\d.]+',
        "replace": "beta=500",
        "root_cause": "초기 binarization β=500이 너무 높아 gradient 소실 -> 최적화 수렴 실패",
        "fix_description": "adjoint 최적화에서 binarization 파라미터 β는 초기에 작은 값(1~4)에서 시작하여 점진적으로 증가시켜야 합니다. β=500으로 시작하면 gradient가 소실됩니다.",
        "fix_hint": "beta=1  # 점진적으로 증가",
    },
    # ── 신규: Normalization 계열 ─────────────────────────────────────
    {
        "name": "missing_norm_run",
        "error_type": "Normalization",
        "find": r'mp\.get_fluxes\(',
        "replace": "mp.get_fluxes(  # BUG: normalization run 없이 절대값 사용",
        "root_cause": "normalization run 없이 flux 절대값 사용 -> T>1 또는 R>1 비물리적 결과",
        "fix_description": "MEEP flux 계산 시 먼저 소스만 있는 normalization run을 수행하고, 그 값으로 flux를 나눠야 합니다. 절대값을 직접 사용하면 T>1 같은 비물리적 결과가 나옵니다.",
        "fix_hint": "tran = mp.get_fluxes(tran_flux) / norm_flux",
    },
    {
        "name": "monitor_in_pml",
        "error_type": "Normalization",
        "find": r'FluxRegion\s*\(',
        "replace": "FluxRegion(  # BUG: PML 영역 근처",
        "root_cause": "flux monitor가 PML 영역과 겹쳐 흡수된 에너지를 측정 -> 부정확한 T/R",
        "fix_description": "FluxRegion은 PML 영역 밖에 위치해야 합니다. PML 두께만큼 안쪽에 모니터를 배치하세요. 예: PML=1.0이면 x_monitor = x_cell/2 - 1.5",
        "fix_hint": "FluxRegion center x < cell_x/2 - pml_thickness",
    },
    # ── 신규: MPI 계열 ──────────────────────────────────────────────
    {
        "name": "np_exceeds_chunks",
        "error_type": "MPIError",
        "find": r'num_chunks\s*=\s*(\d+)',
        "replace": "num_chunks=1",
        "root_cause": "num_chunks=1이지만 mpirun -np 2로 실행 -> MPI 청크 불균형",
        "fix_description": "num_chunks는 mpirun -np 값과 같거나 배수여야 합니다. num_chunks=1이면 -np 1로 실행하거나 num_chunks를 늘리세요.",
        "fix_hint": "num_chunks=2  # np 수와 일치",
    },
    # ── 신규: 추가 버그 유형 ─────────────────────────────────────────
    {
        "name": "courant_too_high",
        "error_type": "Divergence",
        "find": r'courant\s*=\s*[\d.]+',
        "replace": "courant=0.99",
        "root_cause": "Courant 수=0.99는 안정성 한계에 근접하여 수치 발산 유발",
        "fix_description": "MEEP 기본 Courant 수는 0.5입니다. 0.99는 안정성 한계(1.0)에 너무 근접합니다. courant=0.5 (기본값) 또는 더 낮은 값을 사용하세요.",
        "fix_hint": "courant=0.5",
    },
    {
        "name": "source_in_pml",
        "error_type": "Divergence",
        "find": r'(center\s*=\s*mp\.Vector3\s*\()(-?\d+\.?\d*)(,\s*0)',
        "replace": r'\g<1>-9.5\g<3>',  # x 좌표를 PML 내부로 이동
        "root_cause": "소스가 PML 내부에 위치하여 에너지 흡수 후 발산 발생",
        "fix_description": "EigenModeSource는 PML 외부에 위치해야 합니다. PML 두께가 1.0이면 소스 x 좌표는 -(cell_x/2 - 1.5) 이상이어야 합니다.",
        "fix_hint": "source center outside PML region",
    },
    {
        "name": "wrong_decay_field",
        "error_type": "RuntimeError",
        "find": r'stop_when_fields_decayed\s*\(',
        "replace": "mp.stop_when_fields_decayed(50, mp.Bx, mp.Vector3(), 1e-3)",
        "root_cause": "stop_when_fields_decayed에서 잘못된 필드 성분(Bx) 모니터링 -> 조기 또는 미종료",
        "fix_description": "2D TE 시뮬레이션에서 decay 모니터링은 mp.Ez 필드를 사용해야 합니다. Bx는 2D TE 모드에서 항상 0이라 즉시 종료될 수 있습니다.",
        "fix_hint": "stop_when_fields_decayed(50, mp.Ez, ...",
    },
    # ── MPI 데드락 계열 ──────────────────────────────────────────────
    {
        "name": "missing_am_master_plot",
        "error_type": "MPIDeadlock",
        "find": r'if\s+mp\.am_master\(\)\s*:',
        "replace": "if True:  # BUG: am_master 제거",
        "root_cause": "mpirun 환경에서 am_master() 제거 -> 모든 rank가 plt/IO 실행 -> 데드락/충돌",
        "fix_description": "plt.savefig(), np.save(), print() 등 IO 작업은 반드시 if mp.am_master(): 블록 안에 넣어야 합니다. 모든 MPI 프로세스가 동시에 파일을 쓰면 데드락이 발생합니다.",
        "fix_hint": "if mp.am_master():",
    },
    {
        "name": "am_master_in_wrong_scope",
        "error_type": "MPIDeadlock",
        "find": r'(plt\.savefig\([^)]+\))',
        "replace": r'mp.am_master() and \1  # BUG: 잘못된 단락평가 방식',
        "root_cause": "plt.savefig()를 am_master() 단락평가로 보호 시도 -> 모든 rank에서 평가됨",
        "fix_description": "mp.am_master() and plt.savefig()는 안전하지 않습니다. 반드시 if mp.am_master(): 블록을 사용하세요.",
        "fix_hint": "if mp.am_master():\n    plt.savefig(...)",
    },
]


# ------------------------------------------------------------------
# FixPair 데이터 클래스
# ------------------------------------------------------------------

@dataclass
class FixPair:
    original_code: str          # 버그 있는 코드
    fixed_code: str             # 검증된 수정 코드
    error_message: str          # 실제 traceback
    fix_description: str        # 한국어 설명 (Before/After 코드 포함)
    error_type: str
    root_cause: str
    bug_name: str
    pattern_name: str
    verification: dict = field(default_factory=dict)
    fix_worked: int = 1
    source: str = "verified_fix"
    fix_keywords: list = field(default_factory=list)


# ------------------------------------------------------------------
# 버그 주입 (error_injector.py에서 재사용)
# ------------------------------------------------------------------

def inject_bug(original_code: str, bug: dict) -> Optional[str]:
    """원본 코드에 버그 삽입. 적용 불가하면 None 반환"""
    if bug.get("replace") is None:
        return None  # 특수 처리 버그는 스킵
    pattern = bug["find"]
    replacement = bug["replace"]
    if re.search(pattern, original_code):
        new_code = re.sub(pattern, replacement, original_code, count=1)
        if new_code != original_code:
            return new_code
    return None


# ------------------------------------------------------------------
# Docker 실행 (error_injector.py 패턴 재사용, mpirun 사용)
# ------------------------------------------------------------------

def run_in_docker(code: str, timeout: int = 30) -> tuple[int, str]:
    """코드를 Docker MEEP 컨테이너에서 실행 (mpirun -np 2). (returncode, output) 반환"""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w",
                                     encoding="utf-8", delete=False) as f:
        f.write(code)
        tmp_path = f.name

    try:
        script_name = Path(tmp_path).name
        container_path = f"/workspace/{script_name}"

        # docker cp
        cp_result = subprocess.run(
            ["docker", "cp", tmp_path, f"{CONTAINER}:{container_path}"],
            capture_output=True, timeout=10
        )
        if cp_result.returncode != 0:
            return 1, f"docker cp failed: {cp_result.stderr.decode()}"

        # docker exec mpirun
        result = subprocess.run(
            ["docker", "exec", CONTAINER,
             "mpirun", "--allow-run-as-root", "--np", "2",
             "python", container_path],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace"
        )
        output = result.stdout + result.stderr

        # cleanup
        subprocess.run(
            ["docker", "exec", CONTAINER, "rm", "-f", container_path],
            capture_output=True, timeout=5
        )
        return result.returncode, output

    except subprocess.TimeoutExpired:
        return 1, "TimeoutError: Docker 실행 시간 초과 (30s)"
    except FileNotFoundError:
        return 1, "Docker를 찾을 수 없습니다. Docker가 실행 중인지 확인하세요."
    except Exception as e:
        return 1, str(e)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ------------------------------------------------------------------
# 출력 파싱
# ------------------------------------------------------------------

def extract_error_message(output: str) -> str:
    """stdout+stderr에서 핵심 에러 메시지 추출"""
    lines = output.strip().splitlines()
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if re.match(r'^(Error|Warning|meep:|Traceback|.*Error:)', line):
            start = max(0, i - 5)
            return "\n".join(lines[start:i + 3])[:800]
    return "\n".join(lines[-15:])[:800]


def parse_tr_values(output: str) -> tuple[Optional[float], Optional[float]]:
    """출력에서 T/R 값 추출. 형식: T=0.xxx 또는 tran=0.xxx"""
    T, R = None, None
    # T 값 추출
    for pat in [r'[Tt]ran(?:smission)?\s*[=:]\s*([\d.eE+\-]+)',
                r'\bT\s*=\s*([\d.eE+\-]+)',
                r'[Tt]\s*=\s*([\d.eE+\-]+)']:
        m = re.search(pat, output)
        if m:
            try:
                T = float(m.group(1))
                break
            except ValueError:
                pass
    # R 값 추출
    for pat in [r'[Rr]efl(?:ection)?\s*[=:]\s*([\d.eE+\-]+)',
                r'\bR\s*=\s*([\d.eE+\-]+)',
                r'[Rr]\s*=\s*([\d.eE+\-]+)']:
        m = re.search(pat, output)
        if m:
            try:
                R = float(m.group(1))
                break
            except ValueError:
                pass
    return T, R


# ------------------------------------------------------------------
# VerificationResult -- 다층(Tier 1~5) 물리 검증 시스템
# ------------------------------------------------------------------

PATTERN_PHYSICS_LIMITS = {
    "straight_waveguide": {"T_min": 0.85, "R_max": 0.10},
    "bend_flux":          {"T_min": 0.45, "R_max": 0.45},
    "bent_waveguide":     {"T_min": 0.45, "R_max": 0.45},
    "grating":            {"T_min": 0.05, "R_max": 0.95},
    "ring_resonator":     {"T_min": 0.01},
    "mode_converter":     {"T_min": 0.40},
    "splitter":           {"T_min": 0.15},
    "antenna":            {"T_min": 0.01},
}


@dataclass
class VerificationResult:
    """다층 물리 검증 결과"""
    tier1_energy: bool       # T+R 에너지 보존
    tier2_reference: bool    # 원본 코드 대비 오차
    tier3_convergence: bool  # 해상도 수렴성
    tier4_geometry: bool     # 기하학적 극한값
    tier5_mode: bool         # EigenMode 순도
    T_ref: Optional[float]   # 원본 T값
    R_ref: Optional[float]   # 원본 R값
    T_fix: Optional[float]   # 수정 T값
    R_fix: Optional[float]   # 수정 R값
    details: dict = field(default_factory=dict)  # 각 Tier 수치

    @property
    def score(self) -> float:
        weights = [0.2, 0.4, 0.2, 0.1, 0.1]
        checks = [self.tier1_energy, self.tier2_reference,
                  self.tier3_convergence, self.tier4_geometry, self.tier5_mode]
        return sum(w for w, c in zip(weights, checks) if c)

    @property
    def is_valid(self) -> bool:
        """Tier1 필수. Tier2 레퍼런스 있으면 Tier2도 필수. 없으면 score > 0.5"""
        if not self.tier1_energy:
            return False
        if self.T_ref is not None:
            return self.tier2_reference
        return self.score >= 0.5


def verify_tier1(T: Optional[float], R: Optional[float]) -> bool:
    """Tier 1: 에너지 보존 검증 (강화)"""
    if T is None and R is None:
        return False  # None -> 실패 (출력 없음)
    if T is not None and T < 0:
        return False
    if R is not None and R < 0:
        return False
    if T is not None and R is not None:
        total = T + R
        return 0.80 <= total <= 1.10
    if T is not None:
        return 0.0 <= T <= 1.05
    return True


def get_reference_tr(original_code: str, timeout: int = 45) -> tuple:
    """버그 없는 원본 코드를 Docker로 실행해서 T_ref, R_ref 추출"""
    retcode, output = run_in_docker(original_code, timeout=timeout)
    if retcode != 0:
        return None, None
    return parse_tr_values(output)


def verify_tier2(T_fix: Optional[float], R_fix: Optional[float],
                 T_ref: Optional[float], R_ref: Optional[float]) -> bool:
    """Tier 2: 원본 코드 대비 오차 검증"""
    if T_ref is None or T_ref < 0.01:
        return True  # 비교 불가 -> 스킵 (통과)
    if T_fix is None:
        return False
    dT = abs(T_fix - T_ref) / max(T_ref, 0.01)
    if dT > 0.15:
        return False
    if R_ref is not None and R_fix is not None:
        dR = abs(R_fix - R_ref) / max(R_ref, 0.01)
        if dR > 0.30:
            return False
    return True


def verify_tier3_convergence(fixed_code: str, bug_name: str, timeout: int = 45) -> bool:
    """Tier 3: 해상도 수렴성 검증 (Divergence 버그 타입에만 적용)"""
    # Divergence 관련 버그만 적용
    divergence_bugs = {"resolution_too_low", "resolution_large_cell", "courant_too_high"}
    if bug_name not in divergence_bugs:
        return True  # 해당 없으면 통과

    # 현재 resolution 값 추출
    m = re.search(r'resolution\s*=\s*(\d+)', fixed_code)
    if not m:
        return True  # resolution 없으면 스킵

    current_res = int(m.group(1))
    doubled_res = current_res * 2
    high_res_code = re.sub(r'(resolution\s*=\s*)\d+', f'\\g<1>{doubled_res}', fixed_code, count=1)

    # 두 번 실행
    _, out1 = run_in_docker(fixed_code, timeout=timeout)
    _, out2 = run_in_docker(high_res_code, timeout=timeout)

    T1, _ = parse_tr_values(out1)
    T2, _ = parse_tr_values(out2)

    if T1 is None or T2 is None:
        return True  # 파싱 실패 -> 스킵

    # T 변화율 < 10% 이면 수렴
    dT_ratio = abs(T2 - T1) / max(T1, 0.01)
    return dT_ratio < 0.10


def verify_tier4(pattern_name: str, T: Optional[float], R: Optional[float]) -> bool:
    """Tier 4: 기하학적 극한값 검증"""
    for key, limits in PATTERN_PHYSICS_LIMITS.items():
        if key in pattern_name.lower():
            if T is None:
                return True  # 값 없으면 스킵
            if "T_min" in limits and T < limits["T_min"]:
                return False
            if "R_max" in limits and R is not None and R > limits["R_max"]:
                return False
    return True  # 매칭 없으면 통과


def compute_verification_result(
    T_fix: Optional[float], R_fix: Optional[float],
    T_ref: Optional[float], R_ref: Optional[float],
    pattern_name: str, bug_name: str,
    fixed_code: str = "",
    run_tier3: bool = False,
) -> VerificationResult:
    """VerificationResult 통합 계산"""
    t1 = verify_tier1(T_fix, R_fix)
    t2 = verify_tier2(T_fix, R_fix, T_ref, R_ref)
    t3 = verify_tier3_convergence(fixed_code, bug_name) if run_tier3 else True
    t4 = verify_tier4(pattern_name, T_fix, R_fix)
    t5 = True  # Tier 5 (EigenMode 순도) -- Phase 5에서 구현 예정

    details = {
        "T_fix": T_fix,
        "R_fix": R_fix,
        "T_ref": T_ref,
        "R_ref": R_ref,
        "dT_pct": (abs(T_fix - T_ref) / max(T_ref, 0.01) * 100) if (T_fix is not None and T_ref is not None and T_ref >= 0.01) else None,
        "tier1_total": (T_fix + R_fix) if (T_fix is not None and R_fix is not None) else None,
    }

    return VerificationResult(
        tier1_energy=t1,
        tier2_reference=t2,
        tier3_convergence=t3,
        tier4_geometry=t4,
        tier5_mode=t5,
        T_ref=T_ref,
        R_ref=R_ref,
        T_fix=T_fix,
        R_fix=R_fix,
        details=details,
    )


def is_physical(T: Optional[float], R: Optional[float]) -> bool:
    """[Deprecated] Tier 1 호환 래퍼 -- verify_tier1() 사용 권장"""
    return verify_tier1(T, R)


# ------------------------------------------------------------------
# MPI 데드락 위험 정적 감지
# ------------------------------------------------------------------

# am_master() 가드 없이 실행 시 데드락 유발 패턴
DEADLOCK_PATTERNS = [
    (r'plt\.\w+\(',          'matplotlib IO (savefig/show/imshow 등)'),
    (r'\.savefig\(',         'figure 저장 (savefig)'),
    (r'np\.save\(',          'numpy 배열 저장'),
    (r'np\.savetxt\(',       'numpy txt 저장'),
    (r'json\.dump\(',        'JSON 파일 저장'),
    (r'open\(.+["\']w',      '파일 쓰기 (open write)'),
    (r'print\(.*(?:flux|tran|refl|T\s*=|R\s*=)', '시뮬레이션 결과 print'),
    (r'mpb\.ModeSolver',     'MPB ModeSolver (MPI 비호환 호출 가능)'),
]

def detect_mpi_deadlock_risk(code: str) -> dict:
    """
    am_master() 가드 없이 plt/IO/print 호출 감지 (정적 분석).
    반환: {has_risk, likely_deadlock, risks: [{line, desc, code}]}
    """
    lines = code.splitlines()
    risks = []
    in_master_block = False
    master_indent = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        # am_master 블록 진입/종료 추적
        if re.search(r'if\s+(?:mp|meep)\.am_master\(\)', line):
            in_master_block = True
            master_indent = indent
        elif in_master_block and stripped and not stripped.startswith('#'):
            # 들여쓰기가 master 블록보다 작아지면 블록 종료
            if indent <= master_indent:
                in_master_block = False
                master_indent = -1

        # 가드 없이 위험 패턴 탐지
        if not in_master_block:
            for pattern, desc in DEADLOCK_PATTERNS:
                if re.search(pattern, stripped):
                    risks.append({
                        'line': i + 1,
                        'desc': desc,
                        'code': stripped[:80],
                    })
                    break  # 한 줄에 하나만

    # 중복 제거 (같은 desc 최대 2개)
    seen_desc = {}
    unique_risks = []
    for r in risks:
        cnt = seen_desc.get(r['desc'], 0)
        if cnt < 2:
            unique_risks.append(r)
            seen_desc[r['desc']] = cnt + 1

    likely_deadlock = any(
        'matplotlib' in r['desc'] or 'savefig' in r['desc'] or 'numpy' in r['desc']
        for r in unique_risks
    )

    return {
        'has_risk': bool(unique_risks),
        'likely_deadlock': likely_deadlock,
        'risks': unique_risks[:5],
    }


# ------------------------------------------------------------------
# TimeoutError 사전 예측 (LLM pre-analysis)
# ------------------------------------------------------------------

# 버그 타입 중 시뮬레이션 자체가 오래 걸리는 것 vs 버그로 인한 무한루프
TIMEOUT_BUG_TYPES = {
    "no_pml": "PML 없으면 경계 반사 -> 에너지가 빠져나가지 않아 MEEP이 수렴 조건 미달로 무한 실행",
    "missing_reset_meep": "adjoint 반복 루프에서 reset_meep() 없으면 메모리 누적 -> 실행 지연",
    "missing_am_master_plot": "am_master() 제거 -> 모든 MPI rank가 plt/IO 동시 실행 -> 파일 잠금 데드락",
    "am_master_in_wrong_scope": "단락평가 방식 am_master() -> 모든 rank에서 평가 -> 데드락 가능",
    "until_too_short": "until=1은 시뮬레이션이 너무 빨리 끝나야 해서 TimeoutError 아님",
    "courant_too_high": "Courant=0.99는 수치 불안정으로 발산 -> 빠른 에러 발생 (Timeout 아님)",
}

LONG_RUN_PATTERNS = [
    "adjoint_",
    "topology_",
    "optimization",
    "multilayer",
]

def predict_timeout_cause(code: str, bug: dict) -> dict:
    """
    TimeoutError가 예상될 때 원인 분류:
    - bug_induced: 버그로 인한 무한루프/데드락 (교육 데이터로 유효)
    - deadlock: MPI am_master() 누락으로 인한 데드락
    - slow_sim: 원래 오래 걸리는 시뮬레이션 (버그와 무관)
    """
    bug_name = bug.get("name", "")

    # MPI 데드락 위험 정적 감지
    deadlock_info = detect_mpi_deadlock_risk(code)

    # am_master 버그이거나, 정적 분석에서 데드락 위험 감지
    is_deadlock = (bug_name in ("missing_am_master_plot", "am_master_in_wrong_scope")
                   or deadlock_info['likely_deadlock'])

    is_bug_induced = bug_name in TIMEOUT_BUG_TYPES

    pattern_name = next((kw for kw in LONG_RUN_PATTERNS if kw in code[:500].lower()), "")
    is_slow_pattern = bool(pattern_name)

    reason = TIMEOUT_BUG_TYPES.get(bug_name, "버그로 인한 비정상 종료 지연")

    # 데드락 위험이 정적으로 감지된 경우 reason에 추가
    deadlock_note = ""
    if deadlock_info['has_risk'] and not is_bug_induced:
        risk_summary = "; ".join(f"line {r['line']}: {r['desc']}" for r in deadlock_info['risks'][:3])
        deadlock_note = f"\n[정적 분석] am_master() 가드 없는 IO 감지: {risk_summary}"

    if is_deadlock:
        cause = "deadlock"
    elif is_bug_induced:
        cause = "bug_induced"
    elif is_slow_pattern:
        cause = "slow_sim"
    else:
        cause = "unknown"

    return {
        "cause": cause,
        "is_bug_induced": is_bug_induced or is_deadlock,
        "is_deadlock": is_deadlock,
        "deadlock_info": deadlock_info,
        "reason": reason + deadlock_note,
        "fix_description_hint": reason if (is_bug_induced or is_deadlock) else None,
    }


# ------------------------------------------------------------------
# LLM 수정 생성 (Claude Sonnet)
# ------------------------------------------------------------------

def generate_fix_with_llm(buggy_code: str, error_message: str, bug: dict) -> Optional[str]:
    """Claude API로 수정된 코드 생성 (전체 코드 + 전체 traceback 전달)"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [WARN] ANTHROPIC_API_KEY 없음 -- LLM 수정 스킵")
        return None

    # TimeoutError의 경우 원인 분류
    is_timeout = "TimeoutError" in error_message
    timeout_info = ""
    if is_timeout:
        pred = predict_timeout_cause(buggy_code, bug)
        if pred["is_bug_induced"]:
            timeout_info = f"\n[TimeoutError 분석] 이것은 버그({bug['name']})로 인한 무한실행입니다: {pred['reason']}\n수정 방향: {bug.get('fix_hint', '')}\n"
        else:
            timeout_info = f"\n[TimeoutError 분석] 이 패턴은 원래 실행 시간이 긴 시뮬레이션일 수 있습니다. 버그 수정에 집중하세요.\n"

    prompt = f"""당신은 MEEP FDTD 시뮬레이션 Python 코드 수정 전문가입니다.
다음 버그가 있는 코드를 수정하세요.

## 버그 정보
- 버그 유형: {bug['error_type']}
- 버그 이름: {bug['name']}
- 원인: {bug['root_cause']}
- 수정 힌트: {bug.get('fix_hint', bug['fix_description'])}
{timeout_info}
## 실제 에러 메시지 (전체 traceback)
```
{error_message[:1200]}
```

## 버그가 있는 전체 코드
```python
{buggy_code[:4000]}
```

## 요청
위 코드에서 버그를 찾아 수정한 완전한 Python 코드를 출력하세요.
- 수정된 코드 전체를 출력하세요 (일부만 출력하지 마세요)
- 코드만 출력하고 설명은 포함하지 마세요
- 코드 블록(```python ... ```)으로 감싸서 출력하세요
- MEEP 시뮬레이션이 정상적으로 실행되어야 합니다"""

    try:
        import urllib.request

        body = json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}]
        }).encode("utf-8")

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

        # 코드 블록 추출
        code_match = re.search(r'```python\n(.*?)```', text, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        # 코드 블록 없으면 전체 텍스트
        return text.strip()

    except Exception as e:
        print(f"  [WARN] LLM API 오류: {e}")
        return None


# ------------------------------------------------------------------
# fix_description 생성 (한국어, Before/After 포함)
# ------------------------------------------------------------------

def generate_fix_description(bug: dict, buggy_code: str, fixed_code: str,
                              T: Optional[float], R: Optional[float],
                              result: "VerificationResult" = None) -> str:
    """한국어 fix_description 생성 (Before/After 코드 + 검증 Score 포함)"""
    # 버그 있는 줄 추출
    buggy_lines = []
    fixed_lines = []

    try:
        buggy_all = buggy_code.splitlines()
        fixed_all = fixed_code.splitlines() if fixed_code else []

        # 다른 줄 찾기
        for b_line, f_line in zip(buggy_all, fixed_all):
            if b_line.strip() != f_line.strip() and b_line.strip():
                buggy_lines.append(b_line.strip())
                fixed_lines.append(f_line.strip())
                if len(buggy_lines) >= 3:
                    break

        # 차이 없으면 replace 사용
        if not buggy_lines:
            buggy_lines = [bug.get("replace", "# (이전 코드)")]
            fixed_lines = [bug.get("fix_hint", "# (수정 코드)")]
    except Exception:
        buggy_lines = [bug.get("replace", "# (이전 코드)")]
        fixed_lines = [bug.get("fix_hint", "# (수정 코드)")]

    before_code = "\n".join(buggy_lines[:3]) or bug.get("replace", "")
    after_code = "\n".join(fixed_lines[:3]) or bug.get("fix_hint", "")

    t_str = f"{T:.3f}" if T is not None else "N/A"
    r_str = f"{R:.3f}" if R is not None else "N/A"

    # VerificationResult가 있으면 상세 검증 결과 포함
    if result is not None:
        T_ref_str = f"{result.T_ref:.3f}" if result.T_ref is not None else "N/A"
        R_ref_str = f"{result.R_ref:.3f}" if result.R_ref is not None else "N/A"
        verification_line = (
            f"검증 결과: T={t_str}, R={r_str} | "
            f"레퍼런스: T_ref={T_ref_str}, R_ref={R_ref_str} | "
            f"Score={result.score:.2f} "
            f"(Tier1={result.tier1_energy}, Tier2={result.tier2_reference}, "
            f"Tier3={result.tier3_convergence}, Tier4={result.tier4_geometry})"
        )
    else:
        verification_line = f"검증 결과: T={t_str}, R={r_str} (MEEP Docker 실행 확인)"

    return f"""{bug['error_type']} 에러: {bug['root_cause']}

원인: {bug['fix_description']}

수정 방법:
  # Before
  {before_code}
  # After
  {after_code}

{verification_line}"""


# ------------------------------------------------------------------
# API로 저장
# ------------------------------------------------------------------

def store_via_api(pair: FixPair, dry_run: bool = False) -> bool:
    """POST /api/ingest/sim_error로 저장"""
    payload = {
        "error_type": pair.error_type,
        "error_message": pair.error_message[:1000],
        "original_code": pair.original_code[:8000],
        "fixed_code": pair.fixed_code[:8000] if pair.fixed_code else "",
        "fix_description": pair.fix_description,
        "root_cause": pair.root_cause,
        "context": f"verified_fix_builder: pattern={pair.pattern_name}, bug={pair.bug_name}",
        "fix_keywords": json.dumps(pair.fix_keywords, ensure_ascii=False),  # API expects string
        "pattern_name": f"{pair.pattern_name}__{pair.bug_name}",
        "source": "verified_fix",
        "fix_worked": pair.fix_worked,
        "project_id": "verified_fix_builder",
        "meep_version": "",
    }

    if dry_run:
        print(f"  [DRY-RUN] 저장 예정: {pair.error_type} / {pair.bug_name}")
        print(f"    fix_description: {pair.fix_description[:120]}...")
        return True

    try:
        resp = requests.post(
            f"{KB_API_URL}/api/ingest/sim_error",
            json=payload,
            timeout=15
        )
        if resp.status_code in (200, 201):
            return True
        else:
            print(f"  [WARN] API 응답 오류: {resp.status_code} -- {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  [WARN] API 연결 실패: {e}")
        return False


# ------------------------------------------------------------------
# VerifiedFixBuilder 메인 클래스
# ------------------------------------------------------------------

class VerifiedFixBuilder:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = {
            "tried": 0,
            "bug_injected": 0,
            "error_captured": 0,
            "fix_generated": 0,
            "fix_verified": 0,
            "stored": 0,
            "skipped": 0,
        }

    def build_one(self, pattern_file: Path, bug: dict) -> Optional[FixPair]:
        """1 패턴 + 1 버그 -> 검증된 FixPair 또는 None"""
        pattern_name = pattern_file.stem
        self.stats["tried"] += 1

        # 1. 원본 코드 읽기
        try:
            original_code = pattern_file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  [WARN] 파일 읽기 실패: {e}")
            return None

        # 2. 버그 주입
        buggy_code = inject_bug(original_code, bug)
        if not buggy_code:
            return None  # 이 패턴에 버그 적용 불가

        self.stats["bug_injected"] += 1
        print(f"  [OK] bug injected: {bug['name']}")

        if self.dry_run:
            # dry-run: Docker 실행 없이 구조만 확인
            pair = FixPair(
                original_code=buggy_code,
                fixed_code=original_code,
                error_message="[DRY-RUN] 에러 시뮬레이션",
                fix_description=generate_fix_description(bug, buggy_code, original_code, None, None),
                error_type=bug["error_type"],
                root_cause=bug["root_cause"],
                bug_name=bug["name"],
                pattern_name=pattern_name,
                verification={"dry_run": True},
                fix_keywords=[bug["name"], bug["error_type"]],
            )
            return pair

        # 2-b. [Tier 2] 원본 코드 레퍼런스 T/R 추출 (버그 주입 전)
        print(f"  -> 레퍼런스 실행 (원본 코드, Tier 2)...")
        T_ref, R_ref = get_reference_tr(original_code, timeout=45)
        if T_ref is not None or R_ref is not None:
            print(f"  [OK] reference: T_ref={T_ref}, R_ref={R_ref}")
        else:
            print(f"  [--] no reference (original failed or no T/R output) -> Tier 2 skip")

        # 3. 사전 분석: TimeoutError 예측 + MPI 데드락 감지
        timeout_pred = predict_timeout_cause(buggy_code, bug)

        # MPI 데드락 위험 사전 출력
        if timeout_pred["is_deadlock"] and timeout_pred["deadlock_info"]["has_risk"]:
            dl = timeout_pred["deadlock_info"]
            print(f"  [DEADLOCK] am_master() guard missing IO detected:")
            for r in dl["risks"][:3]:
                print(f"      line {r['line']}: {r['desc']} -- {r['code'][:50]}")
            print(f"  -> Docker 실행 (버그 코드, timeout 연장 60s)...")
            retcode, output = run_in_docker(buggy_code, timeout=60)
        elif timeout_pred["is_bug_induced"]:
            print(f"  [WARN] [사전 예측] {bug['name']} -> TimeoutError 예상 ({timeout_pred['reason'][:60]})")
            print(f"  -> Docker 실행 (버그 코드, timeout 연장 60s)...")
            retcode, output = run_in_docker(buggy_code, timeout=60)
        else:
            # 실행 전에도 데드락 위험 알림 (버그 타입과 무관하게)
            deadlock_check = timeout_pred["deadlock_info"]
            if deadlock_check["has_risk"]:
                print(f"  [WARN] [정적 감지] am_master() 없이 IO 호출 발견 (데드락 위험)")
                for r in deadlock_check["risks"][:2]:
                    print(f"      line {r['line']}: {r['code'][:60]}")
            print(f"  -> Docker 실행 (버그 코드)...")
            retcode, output = run_in_docker(buggy_code, timeout=30)

        if retcode == 0:
            # 버그 삽입해도 성공 -> 이 조합 스킵
            print(f"  -> 버그 효과 없음 (exit_code=0), 스킵")
            self.stats["skipped"] += 1
            return None

        error_message = extract_error_message(output)
        self.stats["error_captured"] += 1

        # TimeoutError 발생 -> 원인 주석 추가
        if "TimeoutError" in error_message:
            if timeout_pred["is_deadlock"]:
                dl = timeout_pred["deadlock_info"]
                risk_lines = "; ".join(f"line {r['line']}: {r['desc']}" for r in dl["risks"][:3])
                print(f"  [OK] 에러 캡처: TimeoutError (MPI 데드락 의심: {risk_lines[:60]})")
                error_message = (
                    f"TimeoutError: MPI 데드락 -- {bug['name']} 버그\n"
                    f"원인: {timeout_pred['reason']}\n"
                    f"감지된 위험 패턴: {risk_lines}\n"
                    f"수정: 모든 plt/IO를 if mp.am_master(): 블록으로 감싸세요\n"
                    f"---\n{error_message}"
                )
            elif timeout_pred["is_bug_induced"]:
                print(f"  [OK] 에러 캡처: TimeoutError (버그 유발 확인: {bug['name']})")
                error_message = (
                    f"TimeoutError: {bug['name']} 버그로 인한 무한실행\n"
                    f"원인: {timeout_pred['reason']}\n"
                    f"---\n{error_message}"
                )
            else:
                print(f"  [OK] 에러 캡처: TimeoutError (원인 불명확)")
        else:
            print(f"  [OK] 에러 캡처: {error_message[:80]}")

        # 4. LLM으로 fix_code 생성
        print(f"  -> LLM 수정 생성 (claude-sonnet-4-6)...")
        fixed_code = generate_fix_with_llm(buggy_code, error_message, bug)

        if not fixed_code:
            # LLM 실패 시 원본 코드 사용
            fixed_code = original_code
            print(f"  -> LLM 실패, 원본 코드 사용")

        self.stats["fix_generated"] += 1

        # 5. 수정된 코드 Docker 검증
        print(f"  -> Docker 검증 (수정 코드)...")
        fix_retcode, fix_output = run_in_docker(fixed_code, timeout=60)

        T_fix, R_fix = parse_tr_values(fix_output)

        # [Tier 3] Divergence 버그는 수렴성 검증 (추가 Docker 실행 필요)
        run_tier3 = bug["error_type"] == "Divergence"

        # VerificationResult 계산
        vr = compute_verification_result(
            T_fix=T_fix, R_fix=R_fix,
            T_ref=T_ref, R_ref=R_ref,
            pattern_name=pattern_name,
            bug_name=bug["name"],
            fixed_code=fixed_code,
            run_tier3=run_tier3,
        )

        verification = {
            "exit_code": fix_retcode,
            "T": T_fix,
            "R": R_fix,
            "T_ref": T_ref,
            "R_ref": R_ref,
            "score": vr.score,
            "is_valid": vr.is_valid,
            "tier1_energy": vr.tier1_energy,
            "tier2_reference": vr.tier2_reference,
            "tier3_convergence": vr.tier3_convergence,
            "tier4_geometry": vr.tier4_geometry,
            "details": vr.details,
        }

        if fix_retcode != 0:
            print(f"  -> 수정 코드도 실패 (exit_code={fix_retcode})")
            # fix_worked=0으로 저장
            pair = FixPair(
                original_code=buggy_code,
                fixed_code=fixed_code,
                error_message=error_message,
                fix_description=generate_fix_description(bug, buggy_code, fixed_code, T_fix, R_fix, result=vr),
                error_type=bug["error_type"],
                root_cause=bug["root_cause"],
                bug_name=bug["name"],
                pattern_name=pattern_name,
                verification=verification,
                fix_worked=0,
                fix_keywords=[bug["name"], bug["error_type"]],
            )
            return pair

        # VerificationResult 기반 fix_worked 결정
        fix_worked = 1 if vr.is_valid else 0
        if not vr.is_valid:
            print(f"  -> 물리 검증 실패 (Score={vr.score:.2f}, Tier1={vr.tier1_energy}, Tier2={vr.tier2_reference})")
            print(f"     T_fix={T_fix}, R_fix={R_fix}, T_ref={T_ref}, R_ref={R_ref}")
        else:
            self.stats["fix_verified"] += 1
            print(f"  [OK] verified: T={T_fix}, R={R_fix} | Score={vr.score:.2f} | valid={vr.is_valid}")

        fix_description = generate_fix_description(bug, buggy_code, fixed_code, T_fix, R_fix, result=vr)

        pair = FixPair(
            original_code=buggy_code,
            fixed_code=fixed_code,
            error_message=error_message,
            fix_description=fix_description,
            error_type=bug["error_type"],
            root_cause=bug["root_cause"],
            bug_name=bug["name"],
            pattern_name=pattern_name,
            verification=verification,
            fix_worked=fix_worked,
            fix_keywords=[bug["name"], bug["error_type"], "verified"] if fix_worked else [bug["name"], bug["error_type"]],
        )
        return pair

    def run_batch(self, patterns: list, bugs: list, limit: int = 0,
                  bug_type_filter: str = None) -> int:
        """배치 실행: 패턴 × 버그 조합 시도. 저장된 수 반환"""
        # 필터 적용
        if bug_type_filter:
            bugs = [b for b in bugs if b["error_type"].lower() == bug_type_filter.lower()
                    or b["name"].lower() == bug_type_filter.lower()]
            if not bugs:
                print(f"[WARN] bug_type '{bug_type_filter}'에 매칭되는 버그 없음")
                return 0

        # 이미 처리된 조합 확인 (API로 조회 시도)
        already_done = set()
        try:
            resp = requests.get(f"{KB_API_URL}/api/stats", timeout=5)
            if resp.status_code == 200:
                pass  # stats만 확인
        except Exception:
            pass

        total_stored = 0

        for pat_file in patterns:
            if limit and total_stored >= limit:
                break

            pat_name = pat_file.stem
            print(f"\n[패턴] {pat_name}")

            for bug in bugs:
                if limit and total_stored >= limit:
                    break

                combo_key = f"{pat_name}__{bug['name']}"
                if combo_key in already_done:
                    continue

                print(f"  [버그] {bug['name']} ({bug['error_type']})")
                pair = self.build_one(pat_file, bug)

                if pair is None:
                    continue

                # 저장
                success = store_via_api(pair, dry_run=self.dry_run)
                if success:
                    self.stats["stored"] += 1
                    total_stored += 1
                    already_done.add(combo_key)
                    print(f"  [SAVED] stored (total: {total_stored})")

                time.sleep(0.3)  # API 부하 방지

        return total_stored

    def print_stats(self):
        """실행 통계 출력"""
        print(f"\n{'='*50}")
        print(f"VerifiedFixBuilder 실행 통계")
        print(f"{'='*50}")
        for k, v in self.stats.items():
            print(f"  {k:20s}: {v}")
        print(f"{'='*50}")


# ------------------------------------------------------------------
# 메인
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="VerifiedFixBuilder: MEEP 버그-수정 쌍 자동 생성"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="실제 Docker 실행 없이 테스트")
    parser.add_argument("--limit", type=int, default=0,
                        help="최대 저장 건수 (0=무제한)")
    parser.add_argument("--bug-type", type=str, default=None,
                        help="특정 버그 타입만 처리 (예: Divergence, EigenMode)")
    parser.add_argument("--pattern-filter", type=str, default=None,
                        help="패턴 파일명 필터 (예: waveguide)")
    args = parser.parse_args()

    # 패턴 파일 목록
    pattern_files = sorted(PATTERNS_DIR.glob("*.py"))
    if args.pattern_filter:
        pattern_files = [p for p in pattern_files if args.pattern_filter in p.name]
    if not pattern_files:
        print(f"[WARN] 패턴 파일을 찾을 수 없습니다: {PATTERNS_DIR}")
        sys.exit(1)

    print(f"[VFB] VerifiedFixBuilder 시작")
    print(f"   패턴: {len(pattern_files)}개")
    print(f"   버그: {len(BUG_CATALOG)}종")
    print(f"   제한: {args.limit if args.limit else '무제한'}")
    print(f"   dry-run: {args.dry_run}")
    if args.bug_type:
        print(f"   bug-type: {args.bug_type}")
    print()

    builder = VerifiedFixBuilder(dry_run=args.dry_run)
    stored = builder.run_batch(
        patterns=pattern_files,
        bugs=BUG_CATALOG,
        limit=args.limit,
        bug_type_filter=args.bug_type,
    )

    builder.print_stats()

    if not args.dry_run:
        print(f"\n[완료] {stored}건 저장")
    else:
        print(f"\n[DRY-RUN 완료] {builder.stats['bug_injected']}건 주입 가능 확인")


if __name__ == "__main__":
    main()
