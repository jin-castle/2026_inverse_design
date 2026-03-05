# -*- coding: utf-8 -*-
"""Docker 내부에서 실행: /app/db/knowledge.db SyntaxError 패턴 수정"""
import sqlite3, ast, textwrap, sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = '/app/db/knowledge.db'
conn = sqlite3.connect(DB_PATH)


def try_parse(code):
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def find_last_valid_code(code):
    lines = code.split('\n')
    if try_parse(code):
        return code
    for n in range(len(lines), 0, -1):
        candidate = '\n'.join(lines[:n]).rstrip()
        if not candidate.strip():
            continue
        if try_parse(candidate):
            return candidate + '\n# ... (truncated)'
    return code


rows = conn.execute('SELECT pattern_name, code_snippet FROM patterns').fetchall()
errors_before = [(n, c) for n, c in rows if c and not try_parse(c)]
print(f'Errors before: {len(errors_before)}')

fixed = 0
for name, code in errors_before:
    # try dedent first
    dedented = textwrap.dedent(code)
    if try_parse(dedented):
        conn.execute('UPDATE patterns SET code_snippet=? WHERE pattern_name=?', (dedented, name))
        print(f'[FIXED-dedent] {name}')
        fixed += 1
        continue
    # try truncation
    result = find_last_valid_code(code)
    test_code = result.replace('# ... (truncated)', '').rstrip()
    if try_parse(test_code):
        conn.execute('UPDATE patterns SET code_snippet=? WHERE pattern_name=?', (result, name))
        print(f'[FIXED-trunc]  {name}: {len(code)} -> {len(result)} chars')
        fixed += 1
    else:
        print(f'[FAIL]         {name}')

conn.commit()

# 최종 검증
rows2 = conn.execute('SELECT pattern_name, code_snippet FROM patterns').fetchall()
remaining = [n for n, c in rows2 if c and not try_parse(c)]
print(f'\nResult: fixed={fixed}, remaining_errors={len(remaining)}')
if remaining:
    for n in remaining:
        print(f'  STILL_ERR: {n}')
else:
    print('ALL CLEAR!')
conn.close()
