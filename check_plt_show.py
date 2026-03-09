# -*- coding: utf-8 -*-
import os

WORKDIR = r"C:\Users\user\projects\meep-kb"
CHECK_IDS = [507, 511, 522, 342, 336, 403, 588, 507, 510, 514, 522]

for eid in sorted(set(CHECK_IDS)):
    path = os.path.join(WORKDIR, f"typee_fixed_{eid}.py")
    if not os.path.exists(path):
        print(f"ID {eid}: FILE NOT FOUND")
        continue
    
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    lines = content.split('\n')
    # Check for plt.show() calls (after the header)
    header_end = content.find('plt.show = _patched_show')
    user_code = content[header_end + 50:]  # skip header
    
    if 'plt.show()' in user_code or 'plt.show(' in user_code:
        print(f"ID {eid}: has plt.show()")
    else:
        print(f"ID {eid}: MISSING plt.show() - last 3 lines: {lines[-3:]}")
        # Add plt.show()
        with open(path, "a", encoding="utf-8") as f:
            f.write("\nplt.show()\n")
        print(f"  -> Added plt.show()")
