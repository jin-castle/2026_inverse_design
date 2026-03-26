"""이미지 없는 개념들의 demo_code에서 savefig 패턴 분석."""
import sqlite3, re
from pathlib import Path

conn = sqlite3.connect("db/knowledge.db")
rows = conn.execute(
    "SELECT name, demo_code FROM concepts "
    "WHERE result_images IS NULL OR result_images='' "
    "ORDER BY name"
).fetchall()
conn.close()

patterns = {"no_plt": [], "fig_savefig": [], "var_savefig": [], "no_savefig": [], "other_path": []}

for name, code in rows:
    if not code:
        patterns["no_plt"].append(name)
        continue
    if "plt.savefig" not in code and "savefig" not in code:
        patterns["no_savefig"].append(name)
    elif re.search(r'fig\w*\.savefig', code):
        # fig.savefig(...) 패턴
        m = re.search(r'fig\w*\.savefig\(([^)]+)\)', code)
        patterns["fig_savefig"].append((name, m.group(1) if m else "?"))
    elif re.search(r'plt\.savefig\([^\'"]', code):
        # plt.savefig(variable) 패턴
        m = re.search(r'plt\.savefig\(([^)]+)\)', code)
        patterns["var_savefig"].append((name, m.group(1) if m else "?"))
    else:
        # plt.savefig('...')  — 경로 확인
        m = re.search(r"plt\.savefig\(['\"]([^'\"]+)['\"]", code)
        if m and m.group(1) not in ('/tmp/concept_', 'output.png'):
            patterns["other_path"].append((name, m.group(1)))

print(f"=== 이미지 없는 42개 분석 ===\n")
print(f"plt 없음: {patterns['no_plt']}")
print(f"savefig 없음: {len(patterns['no_savefig'])}개: {patterns['no_savefig'][:5]}...")
print(f"\nfig.savefig() 패턴: {len(patterns['fig_savefig'])}개")
for n, p in patterns['fig_savefig'][:5]:
    print(f"  {n}: {p}")
print(f"\nplt.savefig(variable) 패턴: {len(patterns['var_savefig'])}개")
for n, p in patterns['var_savefig'][:5]:
    print(f"  {n}: {p}")
print(f"\n다른 경로: {len(patterns['other_path'])}개")
for n, p in patterns['other_path'][:10]:
    print(f"  {n}: {p}")
