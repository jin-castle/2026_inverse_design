"""LLM이 실제로 반환하는 형식을 테스트"""
import re

# LLM이 반환하는 실제 형식 시뮬레이션
text = """SUMMARY:
PML은 완전 정합층입니다.

---

## EXPLANATION:

### 상세 설명
전자기파 흡수 원리...

---

## PHYSICS_BACKGROUND:

복소 좌표 변환 $x$ 사용...

---

## COMMON_MISTAKES:
["실수1: PML이 너무 얇음", "실수2: 소스를 PML 내부에"]

## RELATED_CONCEPTS:
["resolution", "FluxRegion"]

## DEMO_CODE:
```python
import meep as mp
print("test")
```

## DEMO_DESCRIPTION:
코드 설명입니다."""

SECTION_TAGS = [
    "SUMMARY", "EXPLANATION", "PHYSICS_BACKGROUND",
    "COMMON_MISTAKES", "RELATED_CONCEPTS", "DEMO_CODE", "DEMO_DESCRIPTION"
]

# 각 섹션의 시작 위치 찾기
section_positions = {}
for tag in SECTION_TAGS:
    m = re.search(rf'(?m)^[#\-]*\s*{tag}\s*:\s*$', text)
    if not m:
        m = re.search(rf'(?m)^[#\-]*\s*{tag}\s*:', text)
    if m:
        section_positions[tag] = m.end()
        print(f"Found {tag} at pos {m.end()}: {repr(text[m.start():m.end()])}")

def get_section(tag: str) -> str:
    if tag not in section_positions:
        return ""
    start = section_positions[tag]
    
    end = len(text)
    for other_tag in SECTION_TAGS:
        if other_tag != tag and other_tag in section_positions:
            pos = section_positions[other_tag]
            header_start = text.rfind(other_tag, 0, pos)
            if header_start > start and header_start < end:
                line_start = text.rfind('\n', 0, header_start)
                if line_start == -1:
                    line_start = 0
                else:
                    line_start += 1
                end = min(end, line_start)
    
    return text[start:end].strip()

print("\n=== RESULTS ===")
print(f"SUMMARY ({len(get_section('SUMMARY'))}): {repr(get_section('SUMMARY')[:100])}")
print(f"EXPLANATION ({len(get_section('EXPLANATION'))}): {repr(get_section('EXPLANATION')[:100])}")
print(f"PHYSICS_BACKGROUND ({len(get_section('PHYSICS_BACKGROUND'))}): {repr(get_section('PHYSICS_BACKGROUND')[:100])}")
print(f"DEMO_DESCRIPTION ({len(get_section('DEMO_DESCRIPTION'))}): {repr(get_section('DEMO_DESCRIPTION')[:100])}")
