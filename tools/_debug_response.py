#!/usr/bin/env python3
"""특정 개념의 raw LLM 응답 확인 및 파서 디버그."""
import os, re
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(Path(__file__).parent.parent / ".env")
api_key = os.environ["ANTHROPIC_API_KEY"]
client = anthropic.Anthropic(api_key=api_key)

concept_name = "Cylinder"
concept_name_ko = "원통형 구조체"

PROMPT = f"""당신은 MEEP FDTD 시뮬레이션 전문가이자 교수입니다.
MEEP의 "{concept_name}" ({concept_name_ko}) 개념을 설명해주세요.

참고 URL: https://meep.readthedocs.io/en/latest/Python_User_Interface/#cylinder
카테고리: geometry
난이도: basic
데모 힌트: Si 기둥(반경 0.2μm) Cylinder 정의. 포토닉 결정 단위 셀에서 필드 분포

반드시 아래 형식 그대로 작성하세요 (## 헤더 없이, 태그만 사용):

SUMMARY:
[1~2문장 핵심 요약]

EXPLANATION:
[상세 설명]

PHYSICS_BACKGROUND:
[물리 배경]

COMMON_MISTAKES:
["실수1", "실수2", "실수3"]

RELATED_CONCEPTS:
["개념1", "개념2"]

DEMO_CODE:
```python
# 코드
import meep as mp
```

DEMO_DESCRIPTION:
[코드 설명]
"""

msg = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2000,
    messages=[{"role": "user", "content": PROMPT}],
)
text = msg.content[0].text

print("=== RAW RESPONSE (first 300 chars) ===")
print(text[:300])
print("\n=== SUMMARY line search ===")
for i, line in enumerate(text.split('\n')[:10]):
    print(f"  line {i}: {repr(line)}")

print("\n=== regex test ===")
m1 = re.search(r'(?m)^[#\-\s]*SUMMARY\s*:', text)
print(f"pattern found: {m1}")
if m1:
    print(f"  matched: {repr(text[m1.start():m1.end()+80])}")
