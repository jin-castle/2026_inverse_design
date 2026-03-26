import re

text = """# MEEP FDTD: Block

---

## SUMMARY:
MEEP의 Block은 직육면체 형태의 유전체 구조를 정의하는 기하학적 객체입니다.

---

## EXPLANATION:
Block은 meep.Block 클래스로 생성됩니다.

## PHYSICS_BACKGROUND:
맥스웰 방정식에서 유전율 텐서 epsilon 사용.

## COMMON_MISTAKES:
["크기를 음수로 설정", "center 누락", "material 없음"]

## RELATED_CONCEPTS:
["Cylinder", "Medium", "Simulation"]

## DEMO_CODE:
```python
import meep as mp
print('hello')
```

## DEMO_DESCRIPTION:
Block 시각화 결과.
"""

SECTION_TAGS = ['SUMMARY','EXPLANATION','PHYSICS_BACKGROUND','COMMON_MISTAKES','RELATED_CONCEPTS','DEMO_CODE','DEMO_DESCRIPTION']
section_line_starts = {}
section_content_starts = {}
for tag in SECTION_TAGS:
    m = re.search(rf'(?m)^[#\-\s]*{tag}\s*:', text)
    if m:
        section_line_starts[tag] = m.start()
        section_content_starts[tag] = m.end()

def get_section(tag):
    if tag not in section_content_starts: return ''
    start = section_content_starts[tag]
    end = len(text)
    for other_tag, other_ls in section_line_starts.items():
        if other_tag != tag and other_ls > section_line_starts[tag]:
            end = min(end, other_ls)
    return text[start:end].strip()

def clean_section(s):
    s = re.sub(r'^\s*---+\s*\n?', '', s).strip()
    s = re.sub(r'\n?\s*---+\s*$', '', s).strip()
    return s

for tag in SECTION_TAGS:
    val = clean_section(get_section(tag))
    print(f'{tag}: {repr(val[:60])}')
