# -*- coding: utf-8 -*-
"""material_grid_adjoint - except 블록에 freq=0.0 추가"""
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'db/knowledge.db'
conn = sqlite3.connect(DB_PATH)

code = conn.execute(
    "SELECT code_snippet FROM patterns WHERE pattern_name='material_grid_adjoint'"
).fetchone()[0]

# except 블록에 freq = 0.0 추가
# '        except:\n            print("No resonant modes found.")'
# →  '        except:\n            freq = 0.0\n            print(...)'
OLD = '        except:\n            print("No resonant modes found.")'
NEW = '        except:\n            freq = 0.0  # no resonant modes found\n            print("No resonant modes found.")'

fixed = code.replace(OLD, NEW)
if fixed != code:
    conn.execute("UPDATE patterns SET code_snippet=? WHERE pattern_name='material_grid_adjoint'", (fixed,))
    conn.commit()
    print("[FIXED] material_grid_adjoint: except에 freq=0.0 추가")
    # 확인
    for i, line in enumerate(fixed.split('\n')[54:65], start=55):
        print(f"  {i}: {line}")
else:
    print("[WARN] 패턴 매칭 실패")
    # 직접 확인
    idx = code.find('except:')
    print(f"  except: 위치: {idx}")
    print(f"  주변: {repr(code[idx-5:idx+60])}")

conn.close()
