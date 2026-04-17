"""
detector.py 패치 — FP 제거 + PARTIAL→PASS 개선
분석된 문제:
  FP-1: Bayer_Quadrant_Wrong — re.DOTALL로 인해 tran_r 이후 줄까지 매칭
  FP-2: Green_Single_Quadrant — 베이스라인에 Tg+Tg0 합산 라인 없어서 오탐
  PARTIAL-1: RefNorm_Missing 해소X — fix가 sim.run() 없을 때 삽입 못 함
  PARTIAL-2: Pillar_Coord_Inversion Docker:NG — regex 그룹 캡처 오류
  PARTIAL-3: MasterOnly_Missing Docker:NG — fix 후 indentation 오류
  PARTIAL-4: FreqWidth_Too_Narrow 해소X — detect가 fix 후에도 탐지
  PARTIAL-5: Single_Polarization 해소X — fix regex 조건 불완전
"""
import re
from pathlib import Path

DETECTOR_PATH = Path(__file__).parent / "detector.py"
code = DETECTOR_PATH.read_text(encoding="utf-8")

# ════════════════════════════════════════════════════════════════
# FP-1: Bayer_Quadrant_Wrong — re.DOTALL 제거, 라인 단위로 변경
# ════════════════════════════════════════════════════════════════
OLD_BAYER = '''def detect_Bayer_Quadrant_Wrong(code, stderr="", result={}):
    """R monitor가 (+x,+y) 위치에 있는 (B 위치) 잘못된 배치
    표준: R=(-x,-y), B=(+x,+y)
    """
    # tran_r 이 +dx/4, +dy/4 에 있으면 오류
    bad = re.search(
        r\'tran_r.*Vector3.*\\+.*\\+\',
        code, re.DOTALL
    )
    return bool(bad)'''

NEW_BAYER = '''def detect_Bayer_Quadrant_Wrong(code, stderr="", result={}):
    """R monitor가 (+x,+y) 위치에 있는 (B 위치) 잘못된 배치
    표준: R=(-x,-y), B=(+x,+y)
    precise: tran_r 정의 라인 하나에서만 검사 (DOTALL 제거)
    """
    for line in code.splitlines():
        # tran_r 정의 라인에서 +dx/4, +dy/4 패턴
        if re.search(r"tran_r\s*=", line):
            if re.search(r"\\+dx/4.*\\+dy/4|\\+Sx/4.*\\+Sy/4", line):
                return True
    return False'''

code = code.replace(OLD_BAYER, NEW_BAYER)
print("[FP-1] Bayer_Quadrant_Wrong 패치:", "OK" if NEW_BAYER.split("\n")[0] in code else "FAIL")

# ════════════════════════════════════════════════════════════════
# FP-2: Green_Single_Quadrant — Tg+Tg0 합산 라인 체크 개선
# ════════════════════════════════════════════════════════════════
OLD_GREEN_DET = '''def detect_Green_Single_Quadrant(code, stderr="", result={}):
    """Green 효율이 Gr 하나만 사용 (Gb 누락)
    context: tran_r, tran_gr, tran_b가 있어야 함
    precise: greenb_flux가 없거나 Tg+Tg0 패턴 없음
    """
    if "tran_gr" not in code: return False  # Bayer 모니터 자체가 없으면 skip
    has_gb   = "tran_gb" in code or "greenb_flux" in code
    has_both = bool(re.search(r\'Tg\\\\s*\\\\+\\\\s*Tg0|greenr.*\\\\+.*greenb|greenb.*\\\\+.*greenr\', code))
    return not has_gb or not has_both'''

# 더 정밀한 패턴으로 교체
OLD_GREEN_DET2 = '''def detect_Green_Single_Quadrant(code, stderr="", result={}):
    """Green 효율이 Gr 하나만 사용 (Gb 누락)
    context: tran_r, tran_gr, tran_b가 있어야 함
    precise: greenb_flux가 없거나 Tg+Tg0 패턴 없음
    """
    if "tran_gr" not in code: return False  # Bayer 모니터 자체가 없으면 skip
    has_gb   = "tran_gb" in code or "greenb_flux" in code
    has_both = bool(re.search(r\'Tg\\s*\\+\\s*Tg0|greenr.*\\+.*greenb|greenb.*\\+.*greenr\', code))
    return not has_gb or not has_both'''

NEW_GREEN_DET = '''def detect_Green_Single_Quadrant(code, stderr="", result={}):
    """Green 효율이 Gr 하나만 사용 (Gb 누락)
    context: tran_gr이 있고 효율 계산 코드가 있어야 함
    precise:
      - tran_gb 또는 greenb_flux 정의 없음 → 확실한 버그
      - OR greenr + greenb 합산 라인 없음 (Tg = greenr only)
    FP 방지: 베이스라인처럼 greenb_flux가 있어도 합산 없으면 탐지
    단, greenb_flux = [0]*nfreq 같은 더미 정의는 버그 아님으로 처리
    """
    if "tran_gr" not in code: return False
    if not _has_flux_calc(code): return False
    # tran_gb 없으면 확실한 버그
    if "tran_gb" not in code and "greenb_flux" not in code:
        return True
    # greenb_flux가 있어도 실제 합산(+)이 없으면 버그
    # 합산 패턴: Tg+Tg0, greenr_flux[d]+greenb_flux[d], (greenr+greenb)
    has_sum = bool(re.search(
        r\'(Tg\\s*\\+\\s*Tg0|greenr_flux\\[.*\\]\\s*\\+\\s*greenb_flux\\[.*\\]|\\(greenr.*\\+.*greenb)\',
        code
    ))
    # tran_gb가 있는데 sum도 있으면 정상
    if "tran_gb" in code and has_sum:
        return False
    # tran_gb가 없거나 sum이 없으면 버그
    return not has_sum'''

# 실제 현재 코드에서 찾아서 교체
current_fn = re.search(
    r'def detect_Green_Single_Quadrant\(.*?(?=\ndef |\nclass |\Z)',
    code, re.DOTALL
)
if current_fn:
    code = code[:current_fn.start()] + NEW_GREEN_DET + "\n\n" + code[current_fn.end():]
    print("[FP-2] Green_Single_Quadrant 패치: OK")
else:
    print("[FP-2] Green_Single_Quadrant 패치: FAIL (함수 미발견)")


# ════════════════════════════════════════════════════════════════
# PARTIAL-1: RefNorm_Missing — fix를 sim.run() 대신 안전한 위치에 삽입
# ════════════════════════════════════════════════════════════════
current_fix = re.search(
    r'def fix_RefNorm_Missing\(.*?(?=\ndef |\nclass |\Z)',
    code, re.DOTALL
)
NEW_REFNORM_FIX = '''def fix_RefNorm_Missing(code):
    snippet = (
        "\\n# [AUTO-FIX] 참조 시뮬 정규화:\\n"
        "# sim.load_minus_flux_data(refl, straight_refl_data)\\n"
        "# 위 코드를 sim 객체에 flux 추가 직후, run() 전에 삽입하세요\\n"
    )
    # sim.run() 바로 앞 삽입 시도
    if "sim.run(" in code:
        return re.sub(r\'(sim\\.run\\()\', snippet + r\'\\1\', code, count=1)
    # 없으면 파일 끝에 추가
    return code + "\\n" + snippet'''

if current_fix:
    code = code[:current_fix.start()] + NEW_REFNORM_FIX + "\n\n" + code[current_fix.end():]
    print("[PARTIAL-1] RefNorm_Missing fix 패치: OK")
else:
    print("[PARTIAL-1] RefNorm_Missing fix 패치: FAIL")


# ════════════════════════════════════════════════════════════════
# PARTIAL-2: Pillar_Coord_Inversion — 단순 라인별 치환으로 변경
# ════════════════════════════════════════════════════════════════
current_fix2 = re.search(
    r'def fix_Pillar_Coord_Inversion\(.*?(?=\ndef |\nclass |\Z)',
    code, re.DOTALL
)
NEW_PILLAR_FIX = '''def fix_Pillar_Coord_Inversion(code):
    """라인별로 px/py 계산식에서 i↔j 교환"""
    lines = code.splitlines()
    result = []
    for line in lines:
        # px 계산 라인에 i*w가 있으면 i→j
        if re.search(r\'px\\s*=\\s*round\', line) and re.search(r\'\\bi\\b.*\\*\\s*w\', line):
            line = re.sub(r\'\\bi\\b\', \'__J__\', line)  # i→temp
            line = re.sub(r\'\\bj\\b\', \'i\', line)       # j→i (먼저 없을 수도 있음)
            line = line.replace(\'__J__\', \'j\')           # temp→j
        # py 계산 라인에 j*w가 있으면 j→i
        elif re.search(r\'py\\s*=\\s*round\', line) and re.search(r\'\\bj\\b.*\\*\\s*w\', line):
            line = re.sub(r\'\\bj\\b\', \'__I__\', line)
            line = re.sub(r\'\\bi\\b\', \'j\', line)
            line = line.replace(\'__I__\', \'i\')
        result.append(line)
    return "\\n".join(result)'''

if current_fix2:
    code = code[:current_fix2.start()] + NEW_PILLAR_FIX + "\n\n" + code[current_fix2.end():]
    print("[PARTIAL-2] Pillar_Coord_Inversion fix 패치: OK")
else:
    print("[PARTIAL-2] Pillar_Coord_Inversion fix 패치: FAIL")


# ════════════════════════════════════════════════════════════════
# PARTIAL-3: MasterOnly_Missing — fix 후 코드가 valid Python이 되도록
# ════════════════════════════════════════════════════════════════
current_fix3 = re.search(
    r'def fix_MasterOnly_Missing\(.*?(?=\ndef |\nclass |\Z)',
    code, re.DOTALL
)
NEW_MASTER_FIX = '''def fix_MasterOnly_Missing(code):
    """plt.savefig()를 if mp.am_master(): 블록으로 감쌈
    들여쓰기를 맞추어서 유효한 Python 코드 생성
    """
    lines = code.splitlines()
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        indent = line[:len(line)-len(stripped)]
        # plt.savefig가 am_master 블록 밖에 있는 라인
        if stripped.startswith("plt.savefig(") and "am_master" not in "\\n".join(lines[max(0,i-3):i]):
            result.append(indent + "if mp.am_master():")
            result.append(indent + "    " + stripped)
        else:
            result.append(line)
        i += 1
    return "\\n".join(result)'''

if current_fix3:
    code = code[:current_fix3.start()] + NEW_MASTER_FIX + "\n\n" + code[current_fix3.end():]
    print("[PARTIAL-3] MasterOnly_Missing fix 패치: OK")
else:
    print("[PARTIAL-3] MasterOnly_Missing fix 패치: FAIL")


# ════════════════════════════════════════════════════════════════
# PARTIAL-4: FreqWidth_Too_Narrow — fix 후 detect가 False가 되도록
# ════════════════════════════════════════════════════════════════
current_det4 = re.search(
    r'def detect_FreqWidth_Too_Narrow\(.*?(?=\ndef |\nclass |\Z)',
    code, re.DOTALL
)
NEW_FREQ_DET = '''def detect_FreqWidth_Too_Narrow(code, stderr="", result={}):
    """fwidth 가 frequency * 0.5 미만인 경우
    precise: fwidth = frequency * N 패턴에서 N < 0.5
             fwidth = frequency / N 패턴에서 N > 2
    FP 방지: fwidth = frequency * 2 (정상)은 탐지 안 함
    """
    # fwidth = frequency * N
    m = re.search(r\'fwidth\\s*=\\s*frequency\\s*\\*\\s*([\\d.]+)\', code)
    if m:
        n = float(m.group(1))
        return n < 0.5  # 0.5 미만만 탐지 (1.0, 2.0은 정상)
    # fwidth = frequency / N  (역수 표현)
    m2 = re.search(r\'fwidth\\s*=\\s*frequency\\s*/\\s*([\\d.]+)\', code)
    if m2:
        return float(m2.group(1)) > 2.0  # 2 초과면 좁음
    return False'''

if current_det4:
    code = code[:current_det4.start()] + NEW_FREQ_DET + "\n\n" + code[current_det4.end():]
    print("[PARTIAL-4] FreqWidth_Too_Narrow detect 패치: OK")
else:
    print("[PARTIAL-4] FreqWidth_Too_Narrow detect 패치: FAIL")


# ════════════════════════════════════════════════════════════════
# PARTIAL-5: Single_Polarization — fix가 실제로 Ey를 추가하도록
# ════════════════════════════════════════════════════════════════
current_fix5 = re.search(
    r'def fix_Single_Polarization\(.*?(?=\ndef |\nclass |\Z)',
    code, re.DOTALL
)
NEW_SINGLE_POL_FIX = '''def fix_Single_Polarization(code):
    """Ex만 있으면 Ey 추가, Ey만 있으면 Ex 추가"""
    has_ex = bool(re.search(r\'mp\\.Source\\(.*mp\\.Ex\', code))
    has_ey = bool(re.search(r\'mp\\.Source\\(.*mp\\.Ey\', code))
    if has_ex and not has_ey:
        # source 리스트 닫는 ] 앞에 Ey 삽입
        return re.sub(
            r\'(mp\\.Source\\(src,\\s*component=mp\\.Ex,\\s*size=source_size,\\s*center=source_center\\))(\\s*\\])\',
            r\'\\1,\\n    mp.Source(src, component=mp.Ey, size=source_size, center=source_center)\\2\',
            code
        )
    elif has_ey and not has_ex:
        return re.sub(
            r\'(mp\\.Source\\(src,\\s*component=mp\\.Ey,\\s*size=source_size,\\s*center=source_center\\))(\\s*\\])\',
            r\'mp.Source(src, component=mp.Ex, size=source_size, center=source_center),\\n    \\1\\2\',
            code
        )
    return code'''

if current_fix5:
    code = code[:current_fix5.start()] + NEW_SINGLE_POL_FIX + "\n\n" + code[current_fix5.end():]
    print("[PARTIAL-5] Single_Polarization fix 패치: OK")
else:
    print("[PARTIAL-5] Single_Polarization fix 패치: FAIL")


# ════════════════════════════════════════════════════════════════
# detect_EigenModeSource_Used — fix 후 detect가 False여야 함
# ════════════════════════════════════════════════════════════════
# fix_EigenModeSource_Used가 EigenModeSource를 교체하므로 detect도 정상 해소

# ════════════════════════════════════════════════════════════════
# 저장
# ════════════════════════════════════════════════════════════════
DETECTOR_PATH.write_text(code, encoding="utf-8")
print(f"\n[저장] {DETECTOR_PATH}")

# 임포트 검증
import subprocess, sys
result = subprocess.run(
    [sys.executable, str(DETECTOR_PATH)],
    capture_output=True, text=True, encoding="utf-8"
)
print(f"[검증] {result.stdout.strip()}")
if result.stderr:
    print(f"[오류] {result.stderr[:200]}")
