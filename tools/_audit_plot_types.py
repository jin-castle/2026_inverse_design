"""각 개념 demo_code의 플롯 방식 분류."""
import sqlite3, re
from pathlib import Path

conn = sqlite3.connect("db/knowledge.db")
rows = conn.execute("SELECT name, category, demo_code FROM concepts ORDER BY category, name").fetchall()
conn.close()

categories = {
    "get_array_only": [],   # sim.get_array(Ez) imshow만
    "dft_field": [],        # add_dft_fields 사용
    "flux_spectrum": [],    # add_flux + 스펙트럼
    "plot2D": [],           # sim.plot2D()
    "single_plot": [],      # plt.plot 1개 subplot만
    "multi_plot": [],       # subplot 2개 이상
    "snippet": [],          # 실제 sim 없음
}

for name, cat, code in rows:
    if not code:
        categories["snippet"].append(name); continue

    has_sim_run = "sim.run" in code or ".run(" in code
    if not has_sim_run:
        categories["snippet"].append(name); continue

    has_dft = "add_dft_fields" in code or "get_dft_array" in code
    has_flux = "add_flux" in code
    has_plot2d = "plot2D" in code
    has_get_array = "get_array" in code
    n_subplot = len(re.findall(r'subplot\(|add_subplot\(|subplots\(', code))
    n_savefig = len(re.findall(r'savefig', code))

    if has_dft:
        categories["dft_field"].append(name)
    elif has_plot2d and not has_get_array:
        categories["plot2D"].append(name)
    elif has_flux and not has_get_array:
        categories["flux_spectrum"].append(name)
    elif has_get_array and n_subplot <= 1:
        categories["get_array_only"].append(name)
    elif n_subplot >= 2:
        categories["multi_plot"].append(name)
    else:
        categories["single_plot"].append(name)

print("=== 플롯 방식 분류 ===\n")
for k, v in categories.items():
    if v:
        print(f"{k} ({len(v)}개):")
        for n in v:
            print(f"  {n}")
        print()

# get_array_only → DFT 추가 대상
print(f"\n🎯 DFT 추가 우선 대상 (get_array_only): {categories['get_array_only']}")
print(f"🎯 subplot 확장 대상 (single_plot): {categories['single_plot']}")
