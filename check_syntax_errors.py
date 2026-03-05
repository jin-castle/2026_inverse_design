"""
SyntaxError 패턴들의 코드 길이와 잘린 위치 확인 (로컬 DB 사용)
컬럼명: pattern_name, code_snippet
"""
import sqlite3

DB_PATH = r"C:\Users\user\projects\meep-kb\db\knowledge.db"
conn = sqlite3.connect(DB_PATH)

syntax_error_patterns = ['EigenModeSource_basic', 'materials_library', 'metasurface_lens', 'waveguide_crossing', 'material_grid_adjoint']

print("=== SyntaxError 패턴 코드 길이 ===")
for name in syntax_error_patterns:
    row = conn.execute('SELECT pattern_name, length(code_snippet) as code_len FROM patterns WHERE pattern_name=?', (name,)).fetchone()
    if row:
        print(f"{row[0]}: {row[1]} chars")
    else:
        print(f"{name}: NOT FOUND")

print()
print("=== undefined variable 패턴들 - 코드에서 변수 찾기 ===")
undefined_vars = {
    'sio2_substrate_pml_geometry': ['cell_x', 'cell_y'],
    'source_monitor_size_substrate': ['source_x'],
    'eig_parity_2d_vs_3d': ['source_x'],
    'solve_cw_steady_state': ['LA'],
    'harmonic_dilation': ['DESIGN_RESOLUTION'],
    'harmonic_erosion': ['DESIGN_RESOLUTION'],
    'EigenModeSource_parameters': ['L'],
    'dft_field_monitor_3d': ['sim'],
    'mode_coeff_phase': ['R_me'],
}

for name, vars_needed in undefined_vars.items():
    row = conn.execute('SELECT code_snippet FROM patterns WHERE pattern_name=?', (name,)).fetchone()
    if row:
        code = row[0]
        print(f"\n[{name}]")
        for var in vars_needed:
            lines = [l.strip() for l in code.split('\n') if var in l][:5]
            print(f"  '{var}' 사용 위치: {lines}")
    else:
        print(f"\n[{name}]: NOT FOUND IN DB")

conn.close()
