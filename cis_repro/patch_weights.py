import re
code = open('C:/Users/user/projects/meep-kb/cis_repro/start_batch.py', encoding='utf-8').read()

# Freeform Layer1
code = re.sub(
    r"str\(NB_DIR[^)]*Freeform[^)]*Layer1\.txt[^)]*\)\.replace\([^)]+\)",
    "'/tmp/Freeform_Layer1.txt'", code
)
# Multilayer Layer1
code = re.sub(
    r"str\(NB_DIR[^)]*multi_layer[^)]*Layer1\.txt[^)]*\)\.replace\([^)]+\)",
    "'/tmp/Multi_Layer1.txt'", code
)
# Multilayer Layer2
code = re.sub(
    r"str\(NB_DIR[^)]*multi_layer[^)]*Layer2\.txt[^)]*\)\.replace\([^)]+\)",
    "'/tmp/Multi_Layer2.txt'", code
)
# SingleLayer
code = re.sub(
    r"str\(NB_DIR[^)]*Layer_singlelayer\.txt[^)]*\)\.replace\([^)]+\)",
    "'/tmp/Single_Layer_singlelayer.txt'", code
)

open('C:/Users/user/projects/meep-kb/cis_repro/start_batch.py', 'w', encoding='utf-8').write(code)
print('패치 완료')
for line in code.splitlines():
    if 'weights_layer' in line:
        print(' ', line.strip())
