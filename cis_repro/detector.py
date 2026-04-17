"""
CIS Error Detector — 정밀 탐지 시스템
======================================
설계 원칙:
  1. Context-aware: 버그가 있어야 할 컨텍스트가 존재할 때만 탐지
  2. Mutually exclusive: 하나의 버그가 다른 버그를 오탐하지 않음
  3. Single source of truth: classify + detect + fix 모두 여기서 관리
  4. 3-tier: code_static(정적) → stderr(런타임) → result(결과값) 순서 적용

탐지 함수 시그니처:
  detect_*(code: str, stderr: str, result: dict) -> bool

수정 함수 시그니처:
  fix_*(code: str) -> str
"""

import re
from typing import Optional


# ══════════════════════════════════════════════════════════════════
# RULE 정의 레지스트리
# ══════════════════════════════════════════════════════════════════

class Rule:
    def __init__(self, rule_id, category, error_id, priority,
                 detect_fn, fix_fn, description, tier):
        self.rule_id = rule_id
        self.category = category
        self.error_id = error_id
        self.priority = priority
        self.detect = detect_fn   # (code, stderr, result) -> bool
        self.fix    = fix_fn      # code -> str
        self.description = description
        self.tier   = tier        # "code" | "stderr" | "result"

    def __repr__(self):
        return f"Rule({self.rule_id}, {self.error_id})"


# ══════════════════════════════════════════════════════════════════
# TIER 1: 코드 정적 분석 (실행 없이 탐지 가능)
# ══════════════════════════════════════════════════════════════════

def _has_sim(code):
    """mp.Simulation( 블록이 코드에 존재하는가"""
    return "mp.Simulation(" in code

def _has_pml(code):
    """PML 설정 코드가 있는가"""
    return "mp.PML(" in code

def _has_source(code):
    """mp.Source( 코드가 있는가"""
    return "mp.Source(" in code

def _has_flux_calc(code):
    """효율 계산 코드가 있는가 (tran_flux_p or add_flux 있음)"""
    return "tran_flux_p" in code or "add_flux(" in code

def _has_plt(code):
    """matplotlib pyplot 사용 코드가 있는가"""
    return "plt." in code or "matplotlib" in code


# ── BOUNDARY ──────────────────────────────────────────────────────

def detect_KPoint_Missing(code, stderr="", result={}):
    """k_point가 없는 mp.Simulation() 블록 탐지
    context: mp.Simulation(이 있어야 함
    precise: Simulation 블록 내에 k_point= 키워드가 없는 경우만
    """
    if not _has_sim(code): return False
    # mp.Simulation( 블록 추출 (닫히는 ) 전까지)
    m = re.search(r'mp\.Simulation\((.*?)(?=\n\s*\))', code, re.DOTALL)
    if m:
        sim_block = m.group(1)
        return "k_point" not in sim_block
    # 단순 검사 fallback
    return "k_point" not in code


def fix_KPoint_Missing(code):
    # Simulation 블록의 마지막 인자 뒤에 k_point 추가
    if "k_point" in code:
        return code
    return re.sub(
        r'(eps_averaging\s*=\s*False)',
        r'k_point=mp.Vector3(0,0,0),\n    \1',
        code, count=1
    )


def detect_EpsAveraging_On(code, stderr="", result={}):
    """eps_averaging=True 또는 eps_averaging 미설정인 Simulation 블록
    context: mp.Simulation( + 이산 pillar 사용 (mp.Block으로 geometry 구성)
    exception: MaterialGrid 사용 시 허용
    """
    if not _has_sim(code): return False
    if "MaterialGrid" in code: return False  # exception
    # True로 명시된 경우
    if re.search(r'eps_averaging\s*=\s*True', code): return True
    # 미설정인 경우 (Simulation 블록 있는데 eps_averaging 없음)
    m = re.search(r'mp\.Simulation\((.*?)(?=\n\s*\))', code, re.DOTALL)
    if m:
        return "eps_averaging" not in m.group(1)
    return "eps_averaging" not in code


def fix_EpsAveraging_On(code):
    if re.search(r'eps_averaging\s*=\s*True', code):
        return re.sub(r'eps_averaging\s*=\s*True', 'eps_averaging=False', code)
    # 미설정이면 추가
    if "eps_averaging" not in code:
        return re.sub(
            r'(extra_materials=\[)',
            r'eps_averaging=False,\n    \1',
            code, count=1
        )
    return code


def detect_PML_AllDirections(code, stderr="", result={}):
    """mp.PML(두께) 형태로 direction 미지정 탐지
    context: mp.PML( 존재 + k_point 설정 공존
    precise: direction=mp.Z 없는 mp.PML( 호출만
    """
    if not _has_pml(code): return False
    # direction= 없는 PML 호출
    has_bad_pml = bool(re.search(
        r'mp\.PML\(\s*(?:thickness\s*=\s*)?\w+\s*\)(?!\s*[,\n]*\s*direction)',
        code
    ))
    # 단순화: mp.PML(Lpml) 패턴 (방향 없음)
    has_no_dir = bool(re.search(r'mp\.PML\(\w+\)(?!\s*,)', code))
    return has_bad_pml or has_no_dir


def fix_PML_AllDirections(code):
    return re.sub(
        r'mp\.PML\((\w+)\)(?!\s*,\s*direction)',
        r'mp.PML(thickness=\1, direction=mp.Z)',
        code
    )


# ── GEOMETRY ──────────────────────────────────────────────────────

def detect_Monitor_In_PML(code, stderr="", result={}):
    """z_mon이 PML 안에 있는 수식 탐지
    precise: z_mon = -Sz/2 + Lpml - anything (mon_2_pml 빠진 경우)
    """
    # 잘못된 패턴: -Sz/2 + Lpml 에서 바로 끝남 (mon_2_pml 없음)
    bad = re.search(r'z_mon\s*=.*-Sz/2\s*\+\s*Lpml\s*[-\n]', code)
    # 또는 결과에서 > 1.0 효율
    if result.get("efficiency_over_1"): return True
    return bool(bad)


def fix_Monitor_In_PML(code):
    return re.sub(
        r'z_mon\s*=.*\n',
        'z_mon  = round(-Sz/2 + Lpml + mon_2_pml - 1/resolution, 3)\n',
        code, count=1
    )


def detect_Pillar_OOB(code, stderr="", result={}):
    """pillar 좌표가 셀 경계 초과 - 런타임 체크 결과에서 탐지"""
    if "OOB pillar" in stderr: return True
    if result.get("pillar_oob_count", 0) > 0: return True
    return False


def fix_Pillar_OOB(code):
    # clamp 코드 주입
    clamp = (
        "            _px = float(max(min(_px, Sx/2-w/2), -Sx/2+w/2))\n"
        "            _py = float(max(min(_py, Sy/2-w/2), -Sy/2+w/2))\n"
    )
    return re.sub(
        r'(geometry\.append\(mp\.Block)',
        clamp + r'            \1',
        code, count=1
    )


def detect_ZCoord_Sign_Error(code, stderr="", result={}):
    """z_src가 z_meta보다 작은 (소스가 메타서피스 아래) 상황
    precise: z_src = -Sz/2 + ... 처럼 음수 방향으로 계산된 경우
    """
    # z_src를 음수 방향으로 계산
    bad_src = re.search(r'z_src\s*=.*-Sz/2', code)
    # assert 실패 stderr
    if "z_src" in stderr and "z_meta" in stderr: return True
    return bool(bad_src)


def fix_ZCoord_Sign_Error(code):
    code = re.sub(
        r'z_src\s*=.*\n',
        'z_src  = round(Sz/2 - Lpml - pml_2_src, 3)\n',
        code, count=1
    )
    return code


def detect_Pillar_Coord_Inversion(code, stderr="", result={}):
    """px에 i*w, py에 j*w가 사용되는 반전 패턴
    precise: px 계산식에 i가 포함되고 py 계산식에 j가 포함됨
    """
    # px = ...i*w (i는 row → y방향인데 x에 사용)
    px_has_i = bool(re.search(r'px\s*=\s*round\(.*\bi\b.*\*\s*w', code))
    # py = ...j*w (j는 col → x방향인데 y에 사용)
    py_has_j = bool(re.search(r'py\s*=\s*round\(.*\bj\b.*\*\s*w', code))
    return px_has_i or py_has_j


def fix_Pillar_Coord_Inversion(code):
    """라인별로 px/py 계산식에서 i↔j 교환"""
    lines = code.splitlines()
    result = []
    for line in lines:
        # px 계산 라인에 i*w가 있으면 i→j
        if re.search(r'px\s*=\s*round', line) and re.search(r'\bi\b.*\*\s*w', line):
            line = re.sub(r'\bi\b', '__J__', line)  # i→temp
            line = re.sub(r'\bj\b', 'i', line)       # j→i (먼저 없을 수도 있음)
            line = line.replace('__J__', 'j')           # temp→j
        # py 계산 라인에 j*w가 있으면 j→i
        elif re.search(r'py\s*=\s*round', line) and re.search(r'\bj\b.*\*\s*w', line):
            line = re.sub(r'\bj\b', '__I__', line)
            line = re.sub(r'\bi\b', 'j', line)
            line = line.replace('__I__', 'i')
        result.append(line)
    return "\n".join(result)


def detect_Bayer_Quadrant_Wrong(code, stderr="", result={}):
    """R monitor가 (+x,+y) 위치인 경우 — 라인 단위 정밀 탐지
    표준: tran_r center = (-dx/4, -dy/4)
    버그: tran_r center = (+dx/4, +dy/4)  ← B 위치
    FP 방지: tran_r 정의 라인 하나에서만 검사
    """
    for line in code.splitlines():
        if re.search(r'tran_r\s*=\s*mp\.FluxRegion|tran_r\s*=\s*sim\.add_flux', line):
            # 같은 라인이나 바로 다음 라인(center= 인자가 별도 줄인 경우)
            if re.search(r'\+dx/4.*\+dy/4|\+Sx/4.*\+Sy/4', line):
                return True
    # center=가 다음 줄에 있는 경우
    lines = code.splitlines()
    for idx, line in enumerate(lines):
        if re.search(r'tran_r\s*=', line) and idx + 1 < len(lines):
            next_line = lines[idx + 1]
            if re.search(r'center.*\+dx/4.*\+dy/4', next_line):
                return True
    return False


def fix_Bayer_Quadrant_Wrong(code):
    """tran_r의 +dx/4,+dy/4를 -dx/4,-dy/4로, tran_b의 -dx/4,-dy/4를 +dx/4,+dy/4로"""
    # tran_r 라인에서 좌표 교체
    lines = code.splitlines()
    result_lines = []
    in_tran_r = False
    for line in lines:
        if re.search(r'tran_r\s*=', line):
            in_tran_r = True
        if in_tran_r and re.search(r'\+dx/4.*\+dy/4', line):
            line = line.replace('+dx/4', '-dx/4').replace('+dy/4', '-dy/4')
            in_tran_r = False
        elif in_tran_r and ('FluxRegion' in line or 'add_flux' in line or ')' in line):
            in_tran_r = False
        result_lines.append(line)
    return "\n".join(result_lines)


def detect_Wrong_Focal_Material(code, stderr="", result={}):
    """result에서 효율이 낮을 때 + params와 비교"""
    if result.get("focal_material_mismatch"): return True
    return False


def fix_Wrong_Focal_Material(code):
    # params.json 없이는 자동 수정 불가 → 경고만
    return "# [WARN] focal_material 확인 필요: Air vs SiO2\n" + code


# ── EFFICIENCY ────────────────────────────────────────────────────

def detect_EfficiencyOver100(code, stderr="", result={}):
    """결과값에서 효율 > 1.0"""
    eff = result.get("efficiency_pixel_norm", {})
    return any(v > 1.05 for v in eff.values() if isinstance(v, (int, float)))


def fix_EfficiencyOver100(code):
    # mon_2_pml 증가 + source 일관성 주석
    return re.sub(
        r'mon_2_pml\s*=\s*[\d.]+',
        'mon_2_pml = 0.5  # increased: efficiency>1 fix',
        code, count=1
    )


def detect_NegativeFlux(code, stderr="", result={}):
    """결과값에서 음수 flux"""
    eff = result.get("efficiency_pixel_norm", {})
    return any(v < -0.01 for v in eff.values() if isinstance(v, (int, float)))


def fix_NegativeFlux(code):
    return re.sub(
        r'(red_flux\[d\] / )',
        r'abs(\1',
        code
    ).replace('/ tran_flux_p[d])', '/ tran_flux_p[d])')


def detect_RefNorm_Missing(code, stderr="", result={}):
    """flux 계산이 있는데 load_minus_flux_data 실제 호출이 없는 경우
    context: sim.add_flux()가 있어야 함 (실제 시뮬레이션 코드)
    precise: 주석(#)이 아닌 실제 load_minus_flux_data( 호출 없음
    """
    if not re.search(r'sim\.add_flux\(', code): return False
    # 주석이 아닌 실제 호출 탐지
    real_calls = [
        l for l in code.splitlines()
        if "load_minus_flux_data" in l and not l.lstrip().startswith("#")
    ]
    return len(real_calls) == 0


def fix_RefNorm_Missing(code):
    """실제 sim.load_minus_flux_data() 호출 코드를 삽입
    add_flux 직후, sim.run() 직전에 삽입
    """
    # refl 변수명 탐지
    m = re.search(r'(\w+)\s*=\s*sim\.add_flux\(fcen.*refl_fr', code)
    refl_var = m.group(1) if m else "refl_main"

    snippet = (
        f"\nsim.load_minus_flux_data({refl_var}, straight_refl_data)"
        "  # [AUTO-FIX] RefNorm 참조 시뮬 차감\n"
    )
    # sim.run() 바로 앞에 삽입
    if "sim.run(" in code:
        return re.sub(r'\n(sim\.run\()', snippet + r'\n\1', code, count=1)
    # add_flux 마지막 라인 뒤에 삽입
    if "sim.add_flux(" in code:
        return re.sub(
            r'(sim\.add_flux\([^\n]+\n)(?!.*sim\.add_flux)',
            r'\1' + snippet,
            code
        )
    return code + snippet


def detect_Green_Single_Quadrant(code, stderr="", result={}):
    """Green 효율이 Gr 하나만 사용 (Gb 누락)
    context: tran_gr이 있고 sim.add_flux 같은 실제 flux 코드가 있어야 함
    precise:
      - sim.add_flux(... tran_gr)이 있는데 tran_gb가 없음
      - 실제 mp.get_fluxes가 있어야 함 (더미 코드 제외)
    FP 방지:
      - mp.get_fluxes 없이 더미 greenb_flux = [0]*nfreq만 있으면 탐지 안 함
      - 베이스라인처럼 tran_gb mp.FluxRegion이 있으면 정상
    """
    # 실제 add_flux 기반 Bayer 모니터가 있어야 함
    if not re.search(r'sim\.add_flux\(.*tran_gr|add_flux\(fcen.*tran_gr', code):
        return False
    # tran_gb도 add_flux로 정의되어 있으면 정상
    if re.search(r'sim\.add_flux\(.*tran_gb|add_flux\(fcen.*tran_gb', code):
        return False
    # mp.FluxRegion으로 tran_gb가 정의되어 있으면 정상
    if re.search(r'tran_gb\s*=\s*mp\.FluxRegion', code):
        return False
    # tran_gb 자체가 없으면 버그
    return "tran_gb" not in code


def fix_Green_Single_Quadrant(code):
    """tran_gb FluxRegion + add_flux + greenb_flux 계산 모두 추가"""
    if "tran_gb" not in code:
        # tran_b 정의 직후에 tran_gb 추가
        code = re.sub(
            r'(tran_b\s*=\s*(?:mp\.FluxRegion|sim\.add_flux)[^\n]+\n)',
            r'\1tran_gb = mp.FluxRegion(center=mp.Vector3(+dx/4, -dy/4, z_mon),'
            r' size=mp.Vector3(dx/2, dy/2, 0))\n',
            code, count=1
        )
    if "greenb_flux" not in code:
        code = re.sub(
            r'(blue_flux\s*=\s*mp\.get_fluxes.*\n)',
            r'\1greenb_flux = mp.get_fluxes(tran_gb)\n',
            code, count=1
        )
    return code


# ── SOURCE ────────────────────────────────────────────────────────

def detect_FreqWidth_Too_Narrow(code, stderr="", result={}):
    """fwidth 가 frequency * 0.5 미만인 경우
    precise: fwidth = frequency * N 패턴에서 N < 0.5
             fwidth = frequency / N 패턴에서 N > 2
    FP 방지: fwidth = frequency * 2 (정상)은 탐지 안 함
    """
    # fwidth = frequency * N
    m = re.search(r'fwidth\s*=\s*frequency\s*\*\s*([\d.]+)', code)
    if m:
        n = float(m.group(1))
        return n < 0.5  # 0.5 미만만 탐지 (1.0, 2.0은 정상)
    # fwidth = frequency / N  (역수 표현)
    m2 = re.search(r'fwidth\s*=\s*frequency\s*/\s*([\d.]+)', code)
    if m2:
        return float(m2.group(1)) > 2.0  # 2 초과면 좁음
    return False


def fix_FreqWidth_Too_Narrow(code):
    return re.sub(
        r'fwidth\s*=\s*frequency\s*\*\s*[\d.]+',
        'fwidth = frequency * 2',
        code
    )


def detect_EigenModeSource_Used(code, stderr="", result={}):
    """EigenModeSource가 코드에 있는 경우"""
    return "EigenModeSource" in code


def fix_EigenModeSource_Used(code):
    # EigenModeSource → GaussianSource 교체 안내
    return re.sub(
        r'mp\.EigenModeSource\([^)]*\)',
        'mp.GaussianSource(frequency=frequency, fwidth=fwidth)  # [FIX] EigenMode→Gaussian',
        code
    )


def detect_Single_Polarization(code, stderr="", result={}):
    """Ex만 또는 Ey만 사용 (unpolarized 아님)
    context: mp.Source( 가 2개 이상 있어야 하는데 하나만 있는 경우
    precise: source = [ mp.Source(... Ex) ] 패턴 (Ey 없음)
    FP 방지: mp.Source가 1개만 정의된 코드에서만 탐지
    """
    if not _has_source(code): return False
    # source 리스트 블록 추출
    src_block_m = re.search(r'source\s*=\s*\[(.*?)\]', code, re.DOTALL)
    if src_block_m:
        blk = src_block_m.group(1)
        has_ex = bool(re.search(r'mp\.Ex', blk))
        has_ey = bool(re.search(r'mp\.Ey', blk))
        return has_ex != has_ey  # XOR: 하나만 있으면 버그
    # source 블록 못 찾으면 개별 Source 라인으로 판단
    ex_lines = [l for l in code.splitlines() if re.search(r'mp\.Source.*mp\.Ex', l)]
    ey_lines = [l for l in code.splitlines() if re.search(r'mp\.Source.*mp\.Ey', l)]
    if ex_lines or ey_lines:
        return bool(ex_lines) != bool(ey_lines)
    return False


def fix_Single_Polarization(code):
    """source 리스트에서 Ex만 있으면 Ey 추가"""
    has_ex = bool(re.search(r'mp\.Source\(.*mp\.Ex', code))
    has_ey = bool(re.search(r'mp\.Source\(.*mp\.Ey', code))
    if has_ex and not has_ey:
        # source 리스트의 마지막 mp.Source(...) 뒤 ] 앞에 삽입
        return re.sub(
            r'(mp\.Source\(src,\s*component=mp\.Ex[^\]]*?)(,?\s*\])',
            r'\1,\n    mp.Source(src, component=mp.Ey, size=source_size, center=source_center)\2',
            code, flags=re.DOTALL
        )
    elif has_ey and not has_ex:
        return re.sub(
            r'(\[\s*\n\s*)(mp\.Source\(src,\s*component=mp\.Ey)',
            r'\1mp.Source(src, component=mp.Ex, size=source_size, center=source_center),\n    \2',
            code
        )
    return code


def detect_Resolution_Too_Low(code, stderr="", result={}):
    """resolution이 20 미만인 경우 (fast-check용 5 제외)
    context: mp.Simulation( 블록이 있어야 함
    precise: resolution = 숫자 < 20, 단 fast-check 모드(=5)는 별도 처리
    """
    if not _has_sim(code): return False
    m = re.search(r'\bresolution\s*=\s*(\d+)', code)
    if m:
        val = int(m.group(1))
        return 1 <= val < 20  # 5(fast-check)도 탐지하되 pipeline에서 예외 처리
    return False


def fix_Resolution_Too_Low(code):
    return re.sub(
        r'\bresolution\s*=\s*\d+',
        'resolution = 40',
        code, count=1
    )


def detect_Divergence(code, stderr="", result={}):
    """MEEP 발산: stderr에 NaN/inf/diverged"""
    return bool(re.search(r'diverged|NaN|inf\b|Simulation diverged', stderr, re.IGNORECASE))


def fix_Divergence(code):
    m = re.search(r'\bresolution\s*=\s*(\d+)', code)
    if m:
        new_res = min(int(m.group(1)) * 2, 80)
        code = re.sub(r'\bresolution\s*=\s*\d+', f'resolution = {new_res}', code, count=1)
    return code


def detect_SlowConverge(code, stderr="", result={}):
    """maximum_run_time에 도달해서 강제 종료
    precise: stderr에 "max run time" 또는 결과 시간이 maximum_run_time과 거의 동일
    """
    return bool(re.search(r'max.*run.*time|Reached maximum', stderr, re.IGNORECASE))


def fix_SlowConverge(code):
    return re.sub(
        r'maximum_run_time\s*=\s*(\d+)',
        lambda m: f'maximum_run_time = {int(m.group(1))*2}',
        code, count=1
    )


# ── MPI ───────────────────────────────────────────────────────────

def detect_ProcessLeak(code, stderr="", result={}):
    """MPI 슬롯 부족: stderr에 'not enough slots'"""
    return "not enough slots" in stderr or "There are not enough slots" in stderr


def fix_ProcessLeak(code):
    prepend = (
        "import subprocess, time\n"
        "subprocess.run(['pkill', '-9', '-f', 'mpirun'], capture_output=True)\n"
        "subprocess.run(['pkill', '-9', '-f', 'python.*meep'], capture_output=True)\n"
        "time.sleep(2)\n"
    )
    return prepend + code


def detect_MasterOnly_Missing(code, stderr="", result={}):
    """plt.savefig가 am_master 가드 없이 호출되는 경우
    context: plt.savefig( 가 있어야 함
    precise: plt.savefig가 있는데 해당 라인 앞 5줄 이내에 am_master가 없음
    """
    if "plt.savefig(" not in code: return False
    lines = code.splitlines()
    for idx, line in enumerate(lines):
        if "plt.savefig(" in line:
            # 앞 5줄에 am_master 가드가 없으면 버그
            context_before = "\n".join(lines[max(0, idx-5):idx])
            if "am_master" not in context_before and "am_master" not in line:
                return True
    return False


def fix_MasterOnly_Missing(code):
    """plt.savefig() 라인을 if mp.am_master(): 블록으로 감쌈
    정확한 들여쓰기로 유효한 Python 코드 유지
    """
    lines = code.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        indent = " " * (len(line) - len(stripped))
        # plt.savefig가 최상위 레벨 (들여쓰기 없음 or 4칸)이고 guard 없음
        if "plt.savefig(" in line:
            context = "\n".join(out[-5:]) if len(out) >= 5 else "\n".join(out)
            if "am_master" not in context:
                out.append(indent + "if mp.am_master():")
                out.append(indent + "    " + stripped)
                out.append(indent + "    plt.close()")
                i += 1
                # 다음 plt.close() 라인 중복 방지
                if i < len(lines) and "plt.close()" in lines[i]:
                    i += 1
                continue
        out.append(line)
        i += 1
    return "\n".join(out)


def detect_Matplotlib_Display(code, stderr="", result={}):
    """X server 오류: stderr에서 탐지 (런타임)"""
    return bool(re.search(r'_tkinter|cannot connect to X|No display', stderr, re.IGNORECASE))


def fix_Matplotlib_Display(code):
    if 'matplotlib.use' not in code:
        code = re.sub(
            r'import matplotlib\n',
            'import matplotlib\nmatplotlib.use("Agg")\n',
            code, count=1
        )
    return re.sub(r'plt\.show\(\)', '', code)


def detect_Matplotlib_Agg_Missing(code, stderr="", result={}):
    """matplotlib 사용하는데 Agg 설정 없음 (사전 탐지)
    context: plt. 또는 matplotlib.pyplot 사용
    precise: matplotlib.use('Agg') 없는 경우
    """
    if not _has_plt(code): return False
    has_import  = "import matplotlib" in code
    has_agg     = bool(re.search(r'matplotlib\.use\(["\']Agg["\']\)', code))
    return has_import and not has_agg


def fix_Matplotlib_Agg_Missing(code):
    return re.sub(
        r'import matplotlib\n(?!matplotlib\.use)',
        'import matplotlib\nmatplotlib.use("Agg")\n',
        code, count=1
    )


def detect_Timeout(code, stderr="", result={}):
    """타임아웃: subprocess timeout 또는 런타임 신호"""
    return bool(re.search(r'TimeoutExpired|timed out', stderr, re.IGNORECASE))


def fix_Timeout(code):
    return re.sub(
        r'maximum_run_time\s*=\s*(\d+)',
        lambda m: f'maximum_run_time = {int(m.group(1))*3}',
        code, count=1
    )


# ══════════════════════════════════════════════════════════════════
# 규칙 레지스트리 (우선순위 순 정렬)
# ══════════════════════════════════════════════════════════════════

RULES: list[Rule] = [
    # BOUNDARY (priority 1)
    Rule("CIS-BC-001","BOUNDARY","KPoint_Missing",        1, detect_KPoint_Missing,        fix_KPoint_Missing,        "k_point=(0,0,0) 누락",           "code"),
    Rule("CIS-BC-002","BOUNDARY","EpsAveraging_On",       1, detect_EpsAveraging_On,       fix_EpsAveraging_On,       "eps_averaging=True 또는 미설정", "code"),
    Rule("CIS-BC-003","BOUNDARY","PML_AllDirections",     1, detect_PML_AllDirections,     fix_PML_AllDirections,     "PML direction 미지정",           "code"),

    # GEOMETRY (priority 1 먼저)
    Rule("CIS-GEO-001","GEOMETRY","Monitor_In_PML",       1, detect_Monitor_In_PML,        fix_Monitor_In_PML,        "모니터가 PML 안에 위치",         "code"),
    Rule("CIS-GEO-003","GEOMETRY","ZCoord_Sign_Error",    1, detect_ZCoord_Sign_Error,     fix_ZCoord_Sign_Error,     "z_src 부호 오류",                "code"),
    Rule("CIS-GEO-004","GEOMETRY","Pillar_Coord_Inversion",1,detect_Pillar_Coord_Inversion,fix_Pillar_Coord_Inversion,"pillar i↔j 반전",               "code"),
    Rule("CIS-GEO-002","GEOMETRY","Pillar_OOB",           2, detect_Pillar_OOB,            fix_Pillar_OOB,            "pillar 경계 초과",               "stderr"),
    Rule("CIS-GEO-005","GEOMETRY","Bayer_Quadrant_Wrong", 2, detect_Bayer_Quadrant_Wrong,  fix_Bayer_Quadrant_Wrong,  "Bayer 사분면 배치 오류",         "code"),
    Rule("CIS-MAT-001","GEOMETRY","Wrong_Focal_Material", 2, detect_Wrong_Focal_Material,  fix_Wrong_Focal_Material,  "Focal layer 재료 불일치",        "result"),

    # EFFICIENCY
    Rule("CIS-EFF-001","EFFICIENCY","EfficiencyOver100_PixelNorm",1,detect_EfficiencyOver100,fix_EfficiencyOver100,"효율 > 1.0",                    "result"),
    Rule("CIS-EFF-002","EFFICIENCY","NegativeFlux",       2, detect_NegativeFlux,          fix_NegativeFlux,          "음수 flux",                      "result"),
    Rule("CIS-EFF-003","EFFICIENCY","RefNorm_Missing",    3, detect_RefNorm_Missing,       fix_RefNorm_Missing,       "참조 시뮬 정규화 누락",           "code"),
    Rule("CIS-EFF-004","EFFICIENCY","Green_Single_Quadrant",2,detect_Green_Single_Quadrant,fix_Green_Single_Quadrant, "Green Gb 사분면 누락",           "code"),

    # SOURCE
    Rule("CIS-SRC-002","SOURCE","EigenModeSource_Used",   1, detect_EigenModeSource_Used,  fix_EigenModeSource_Used,  "EigenModeSource 사용",           "code"),
    Rule("CIS-SRC-001","SOURCE","FreqWidth_Too_Narrow",   2, detect_FreqWidth_Too_Narrow,  fix_FreqWidth_Too_Narrow,  "fwidth 너무 좁음",               "code"),
    Rule("CIS-SRC-003","SOURCE","Single_Polarization",    2, detect_Single_Polarization,   fix_Single_Polarization,   "단일 편광만 사용",               "code"),

    # NUMERICAL
    Rule("CIS-NUM-001","NUMERICAL","Resolution_Too_Low",  1, detect_Resolution_Too_Low,    fix_Resolution_Too_Low,    "resolution < 20",                "code"),
    Rule("CIS-NUM-002","NUMERICAL","Divergence",          1, detect_Divergence,            fix_Divergence,            "MEEP 발산",                      "stderr"),
    Rule("CIS-NUM-003","NUMERICAL","SlowConverge",        2, detect_SlowConverge,          fix_SlowConverge,          "maximum_run_time 도달",          "stderr"),

    # MPI
    Rule("CIS-MPI-001","MPI","ProcessLeak",               1, detect_ProcessLeak,           fix_ProcessLeak,           "MPI 슬롯 부족",                  "stderr"),
    Rule("CIS-MPI-002","MPI","MasterOnly_Missing",        2, detect_MasterOnly_Missing,    fix_MasterOnly_Missing,    "am_master() 가드 없음",          "code"),

    # ENVIRONMENT
    Rule("CIS-ENV-003","ENVIRONMENT","Matplotlib_Agg_Missing",1,detect_Matplotlib_Agg_Missing,fix_Matplotlib_Agg_Missing,"matplotlib.use('Agg') 누락",  "code"),
    Rule("CIS-ENV-001","ENVIRONMENT","Matplotlib_Display",1, detect_Matplotlib_Display,    fix_Matplotlib_Display,    "X server 없음(런타임)",          "stderr"),
    Rule("CIS-ENV-002","ENVIRONMENT","Timeout",           2, detect_Timeout,               fix_Timeout,               "실행 타임아웃",                   "stderr"),
]

# 규칙 ID → Rule 매핑
RULE_MAP = {r.rule_id: r for r in RULES}


# ══════════════════════════════════════════════════════════════════
# 공개 API
# ══════════════════════════════════════════════════════════════════

def classify(code: str, stderr: str = "", result: dict = {}) -> Optional[Rule]:
    """최우선 매칭 규칙 반환 (우선순위 순, 정밀 탐지)"""
    for rule in sorted(RULES, key=lambda r: r.priority):
        if rule.detect(code, stderr, result):
            return rule
    return None


def classify_all(code: str, stderr: str = "", result: dict = {}) -> list[Rule]:
    """감지된 모든 규칙 목록 반환"""
    return [r for r in sorted(RULES, key=lambda r: r.priority)
            if r.detect(code, stderr, result)]


def apply_fix(code: str, rule: Rule) -> str:
    """규칙의 fix 함수 적용"""
    return rule.fix(code)


def auto_fix_loop(code: str, stderr: str = "", result: dict = {},
                  max_iter: int = 3) -> tuple[str, list[str]]:
    """탐지→수정 루프. (fixed_code, applied_rule_ids) 반환"""
    applied = []
    for _ in range(max_iter):
        rule = classify(code, stderr, result)
        if rule is None:
            break
        code = apply_fix(code, rule)
        applied.append(rule.rule_id)
    return code, applied


if __name__ == "__main__":
    print(f"CIS Error Detector — {len(RULES)}개 규칙 로드됨")
    for tier in ["code","stderr","result"]:
        cnt = sum(1 for r in RULES if r.tier == tier)
        print(f"  {tier}: {cnt}개")
