# -*- coding: utf-8 -*-
"""백업 DB에서 material_grid_adjoint 복원 후 올바르게 fix"""
import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

src = sqlite3.connect('db/knowledge_backup_before_translate.db')
dst = sqlite3.connect('db/knowledge.db')

PNAME = 'material_grid_adjoint'

orig = src.execute('SELECT code_snippet FROM patterns WHERE pattern_name=?', (PNAME,)).fetchone()
if not orig:
    print('NOT FOUND in backup')
    src.close(); dst.close()
    exit()

code = orig[0]
print(f"Backup code: {len(code)} chars")

# Fix 1: design_parameters 제거
code = re.sub(r',\s*design_parameters\s*=\s*\w+', '', code)
print("Fix 1: design_parameters removed")

# Fix 2: except 블록에 freq=0.0 추가
# 원본 구조: try:\n...freq = h.modes[0].freq\n        except:\n            print("No resonant modes found.")
old_except = '        except:\n            print("No resonant modes found.")'
new_except = '        except:\n            freq = 0.0  # no resonant modes found\n            print("No resonant modes found.")'
if old_except in code:
    code = code.replace(old_except, new_except)
    print("Fix 2: freq=0.0 added to except block")
else:
    # 다른 인덴트 확인
    idx = code.find('except:')
    if idx >= 0:
        print(f"Fix 2: except found at {idx}, context:")
        print(repr(code[max(0,idx-10):idx+80]))
    else:
        print("Fix 2: except not found!")

dst.execute('UPDATE patterns SET code_snippet=? WHERE pattern_name=?', (code, PNAME))
dst.commit()
print(f"\nSaved: {len(code)} chars")

# 검증
import ast
try:
    ast.parse(code)
    print("AST parse: OK")
except SyntaxError as e:
    print(f"AST parse: FAIL - {e}")

src.close()
dst.close()
