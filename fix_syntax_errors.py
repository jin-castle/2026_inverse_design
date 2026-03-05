# -*- coding: utf-8 -*-
"""
meep-kb patterns DB의 SyntaxError 있는 코드 스니펫을 수정:
1. dedent으로 해결 가능한 것 (이미 처리됨)
2. 잘린 코드 → 마지막 완전한 문장까지 잘라서 저장
"""
import sqlite3, ast, sys, textwrap
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'db/knowledge.db'
conn = sqlite3.connect(DB_PATH)


def find_last_valid_code(code: str) -> str:
    """코드를 줄 단위로 줄여가며 파싱 가능한 최대 지점 찾기"""
    lines = code.split('\n')
    # 전체 먼저 시도
    try:
        ast.parse(code)
        return code
    except SyntaxError:
        pass
    
    # 뒤에서 줄여나가기 (빈 줄 제외하고 의미있는 마지막 줄 찾기)
    for n in range(len(lines), 0, -1):
        candidate = '\n'.join(lines[:n]).rstrip()
        if not candidate.strip():
            continue
        try:
            ast.parse(candidate)
            return candidate + '\n# ... (truncated)'
        except SyntaxError:
            continue
    return code  # 못찾으면 원본 반환


# 여전히 SyntaxError인 패턴 목록
error_names = [
    'MsoptBetaScheduler',
    'adjoint_optimization_problem',
    'adjoint_objective_functions',
    'materials_library',
    'adjoint_waveguide_bend_optimization',
    'adjoint_mode_converter_opt',
    'adjoint_multilayer_optimization',
    'metasurface_lens',
    'adjoint_solver_complete',
    'adjoint_jax_integration',
    'waveguide_crossing',
    'EigenModeSource_basic',
    'pipeline_cat6_output_results',
]

print("=== Fixing truncated code snippets ===\n")
fixed_count = 0

for name in error_names:
    row = conn.execute(
        'SELECT code_snippet FROM patterns WHERE pattern_name=?', (name,)
    ).fetchone()
    if not row:
        print(f'[SKIP] {name}: NOT FOUND')
        continue
    
    code = row[0]
    
    # 현재 상태 확인
    try:
        ast.parse(code)
        print(f'[OK]   {name}: already valid ({len(code)} chars)')
        continue
    except SyntaxError as e:
        pass
    
    # 수정 시도
    fixed = find_last_valid_code(code)
    
    # 수정 후 검증
    try:
        # truncated 주석 제거하고 파싱
        test_code = fixed.replace('# ... (truncated)', '').rstrip()
        ast.parse(test_code)
        conn.execute(
            'UPDATE patterns SET code_snippet=? WHERE pattern_name=?', (fixed, name)
        )
        print(f'[FIXED] {name}: {len(code)} -> {len(fixed)} chars')
        fixed_count += 1
    except SyntaxError as e:
        print(f'[FAIL]  {name}: could not fix: {e}')

conn.commit()
conn.close()

print(f"\n총 {fixed_count}개 수정 완료")
