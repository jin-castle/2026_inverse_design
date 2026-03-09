#!/usr/bin/env python3
"""fig.savefig / plt.savefig 상대경로를 절대경로로 수정"""
import re, os

RESULTS_DIR = "/tmp/kb_results"

fixes = {
    539: [
        ('fig.savefig("disc_simulation_layout.png"', f'fig.savefig("{RESULTS_DIR}/ex_539_00.png"'),
    ],
    562: [
        ('fig.savefig("zone_plate_layout.png"', f'fig.savefig("{RESULTS_DIR}/ex_562_00.png"'),
        ('fig.savefig("zone_plate_farfields.png"', f'fig.savefig("{RESULTS_DIR}/ex_562_01.png"'),
    ],
}

# 539 추가: radiation pattern 함수들도 savefig 추가 (코드 끝에)
SAVE_ALL_FIGS = """
# 모든 열린 figure 저장 (패치)
if mp.am_master():
    import matplotlib.pyplot as _plt_save
    for _i, _fnum in enumerate(_plt_save.get_fignums()):
        _fig_obj = _plt_save.figure(_fnum)
        _save_path = f"{RESULTS_DIR}/ex_{{eid}}_{{_i:02d}}.png"
        if not os.path.exists(_save_path):
            _fig_obj.savefig(_save_path, dpi=100, bbox_inches="tight")
        _plt_save.close(_fig_obj)
"""

base = r"C:\Users\user\projects\meep-kb\patched_codes"

for eid, replacements in fixes.items():
    fpath = os.path.join(base, f"worker_ex_{eid}.py")
    with open(fpath, 'r', encoding='utf-8') as f:
        code = f.read()

    for old, new in replacements:
        if old in code:
            code = code.replace(old, new)
            print(f"  id={eid}: '{old[:40]}' → OK")
        else:
            print(f"  id={eid}: '{old[:40]}' → NOT FOUND")

    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(code)

# 539: plot_radiation_pattern 함수들이 내부에서 savefig를 안 하므로 코드 끝에 추가
fpath539 = os.path.join(base, "worker_ex_539.py")
with open(fpath539, 'r', encoding='utf-8') as f:
    code = f.read()

# 코드 끝에 "모든 figure 저장" 블록 추가
save_code = f"""
# === 추가: 열린 figure 전체 저장 ===
if mp.am_master():
    import matplotlib.pyplot as _plt_
    for _i2, _fn in enumerate(_plt_.get_fignums()):
        _fg = _plt_.figure(_fn)
        _sp = f"{RESULTS_DIR}/ex_539_r{{_i2:02d}}.png"
        if not os.path.exists(_sp):
            _fg.savefig(_sp, dpi=100, bbox_inches="tight")
        _plt_.close(_fg)
"""
code = code + save_code
with open(fpath539, 'w', encoding='utf-8') as f:
    f.write(code)
print(f"  id=539: save-all-figs 블록 추가")

# 592 처리
fpath592 = os.path.join(base, "worker_ex_592.py")
with open(fpath592, 'r', encoding='utf-8') as f:
    code = f.read()

# multiline savefig 패턴 수정
count = [0]
def fix_multiline_savefig(code_in, eid):
    lines = code_in.split('\n')
    result = []
    i = 0
    fig_count = 0
    while i < len(lines):
        line = lines[i]
        # plt.savefig( 가 있고 다음 줄에 파일명이 있는 패턴
        if 'plt.savefig(' in line and '"/tmp/' not in line:
            # 한줄 또는 여러줄 수집
            savefig_block = [line]
            j = i + 1
            # 괄호가 닫힐 때까지 수집
            open_parens = line.count('(') - line.count(')')
            while open_parens > 0 and j < len(lines):
                savefig_block.append(lines[j])
                open_parens += lines[j].count('(') - lines[j].count(')')
                j += 1
            indent = len(line) - len(line.lstrip())
            result.append(' ' * indent + f'plt.savefig("{RESULTS_DIR}/ex_{eid}_{fig_count:02d}.png", dpi=150, bbox_inches="tight")')
            fig_count += 1
            i = j
            print(f"  id={eid}: plt.savefig 블록 → ex_{eid}_{fig_count-1:02d}.png")
        else:
            result.append(line)
            i += 1
    return '\n'.join(result)

code = fix_multiline_savefig(code, 592)
with open(fpath592, 'w', encoding='utf-8') as f:
    f.write(code)

print("\n모든 수정 완료!")
