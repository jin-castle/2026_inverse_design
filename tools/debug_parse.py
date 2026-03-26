import re

text = """SUMMARY:
PML은 완전 흡수 경계 조건입니다.

EXPLANATION:
상세 설명입니다.

PHYSICS_BACKGROUND:
물리 배경입니다.

COMMON_MISTAKES:
["실수1", "실수2"]

RELATED_CONCEPTS:
["resolution", "FluxRegion"]

DEMO_CODE:
```python
import meep as mp
print("test")
```

DEMO_DESCRIPTION:
코드 설명입니다."""

SECTION_TAGS = ['SUMMARY', 'EXPLANATION', 'PHYSICS_BACKGROUND', 'COMMON_MISTAKES', 'RELATED_CONCEPTS', 'DEMO_CODE', 'DEMO_DESCRIPTION']

def extract_section(tag, text):
    next_tags = '|'.join(SECTION_TAGS)
    pattern = rf'(?:^|\n){tag}:\s*\n(.*?)(?=\n(?:{next_tags}):|$)'
    m = re.search(pattern, text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ''

print('SUMMARY:', repr(extract_section('SUMMARY', text)[:100]))
print('EXPLANATION:', repr(extract_section('EXPLANATION', text)[:100]))
print('PHYSICS_BACKGROUND:', repr(extract_section('PHYSICS_BACKGROUND', text)[:100]))
print('DEMO_DESCRIPTION:', repr(extract_section('DEMO_DESCRIPTION', text)[:100]))
