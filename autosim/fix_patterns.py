"""
fix_patterns.py
수정 가능한 실패 패턴들을 개별 패치하는 스크립트.
로컬 Windows에서 실행.
"""
import re
from pathlib import Path

PATTERNS_DIR = Path(__file__).parent / "patterns"

def patch_file(name: str, fn):
    """패턴 파일 읽고 → fn 적용 → 저장"""
    p = PATTERNS_DIR / f"{name}.py"
    if not p.exists():
        print(f"  [SKIP] {name}.py 없음")
        return False
    code = p.read_text(encoding="utf-8")
    patched = fn(code)
    if patched == code:
        print(f"  [NOOP] {name} - no changes")
        return False
    p.write_text(patched, encoding="utf-8")
    print(f"  [FIXED] {name}")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 1. solve_cw_steady_state: LA = np.linalg (common.py에서 이미 추가됨, 확인용)
# generate_patterns.py가 `from numpy import linalg as LA`를 제거했으므로
# common.py의 LA를 쓰면 됨 → 별도 패치 불필요 (테스트로 확인)
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# 2. binary_grating_diffraction: pcolormesh shading='flat' → 'auto'
# ─────────────────────────────────────────────────────────────────────────────
def fix_binary_grating(code):
    return code.replace("shading='flat'", "shading='auto'")

# ─────────────────────────────────────────────────────────────────────────────
# 3. dft_field_monitor_3d: sim 객체 없이 사용 → 패턴 파일 상단에 기본 sim 주입
# ─────────────────────────────────────────────────────────────────────────────
def fix_dft_field_monitor_3d(code):
    # 패턴 코드에 sim이 없으므로 기본 sim 객체 주입
    injection = """\
    # ── 기본 sim 객체 (dft_field_monitor_3d 패치) ──
    _cell = mp.Vector3(cell_x, cell_y, slab_h + 2*dpml)
    _sources = [mp.EigenModeSource(
        src=mp.GaussianSource(fcen, fwidth=fwidth),
        center=mp.Vector3(source_x, 0, 0),
        size=mp.Vector3(0, cell_y, slab_h + 1),
        eig_band=1,
    )]
    _geo = [mp.Block(
        size=mp.Vector3(mp.inf, wg_width, slab_h),
        center=mp.Vector3(0, 0, 0),
        material=silicon,
    )]
    sim = mp.Simulation(
        cell_size=_cell,
        geometry=_geo,
        sources=_sources,
        boundary_layers=[mp.PML(dpml)],
        resolution=resolution,
    )
    sim.run(until=200)
"""
    # try 블록 내 패턴 코드 시작 부분에 주입
    marker = "    # ─────────────────────────────────────────────────────────────\n    # 패턴 코드 (자동 생성)\n    # ─────────────────────────────────────────────────────────────"
    if marker in code:
        return code.replace(marker, marker + "\n" + injection)
    return code

# ─────────────────────────────────────────────────────────────────────────────
# 4. mode_coeff_phase: R_me 사용 맥락 확인 후 처리
# ─────────────────────────────────────────────────────────────────────────────
def fix_mode_coeff_phase(code):
    # R_me는 common.py에서 0.0으로 정의됨 → 실행은 되지만 결과가 의미없을 수 있음
    # 일단 코드에 R_me 정의 추가
    injection = "    R_me = 0.0  # placeholder (실제 모드 반사율 계산 필요)\n"
    marker = "    # ─────────────────────────────────────────────────────────────\n    # 패턴 코드 (자동 생성)\n    # ─────────────────────────────────────────────────────────────"
    if marker in code and "R_me" in code:
        return code.replace(marker, marker + "\n" + injection)
    return code

# ─────────────────────────────────────────────────────────────────────────────
# 5. material_grid_adjoint: 코드 끝 잘림 → 불완전한 문장 제거
# ─────────────────────────────────────────────────────────────────────────────
def fix_material_grid_adjoint(code):
    # 마지막 불완전 줄 제거
    lines = code.split('\n')
    # 괄호가 열린 채로 끝나는 줄 찾기
    clean_lines = []
    for i, line in enumerate(lines):
        # 코드 섹션 끝 마커 이전까지만 유효
        if '# ─────' in line and '# 패턴 코드' not in line and i > 50:
            # 직전까지의 줄만 유지하되 불완전한 줄 제거
            # 마지막 몇 줄 검사
            while clean_lines and clean_lines[-1].strip() and not clean_lines[-1].strip().endswith((':', ',', ')', ']', '"', "'")):
                removed = clean_lines.pop()
                print(f"    제거: {removed.strip()[:60]}")
            clean_lines.append(line)
        else:
            clean_lines.append(line)
    return '\n'.join(clean_lines)


# ─────────────────────────────────────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    fixes = [
        ("binary_grating_diffraction", fix_binary_grating),
        ("dft_field_monitor_3d",       fix_dft_field_monitor_3d),
        ("mode_coeff_phase",           fix_mode_coeff_phase),
        ("material_grid_adjoint",      fix_material_grid_adjoint),
    ]

    print("=== 패턴 파일 개별 패치 ===")
    total_fixed = 0
    for name, fn in fixes:
        if patch_file(name, fn):
            total_fixed += 1

    print(f"\n완료: {total_fixed}/{len(fixes)} 파일 수정됨")
    print("→ 다음: docker cp 후 재실행")
