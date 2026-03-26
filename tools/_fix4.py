#!/usr/bin/env python3
"""summary 미완 4개 재생성 - 단순 파서 사용."""
import os, re, json, sqlite3, time
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(Path(__file__).parent.parent / ".env")
api_key = os.environ["ANTHROPIC_API_KEY"]
client = anthropic.Anthropic(api_key=api_key)

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"

TARGETS = [
    {
        "name": "Cylinder",
        "name_ko": "원통형 구조체",
        "aliases": ["mp.Cylinder", "cylinder", "circular rod", "disk resonator"],
        "category": "geometry",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#cylinder",
        "demo_hint": "Si 기둥(반경 0.2μm) Cylinder 정의. 포토닉 결정 단위 셀에서 필드 분포",
    },
    {
        "name": "add_energy",
        "name_ko": "에너지 밀도 모니터",
        "aliases": ["add_energy", "energy monitor", "electromagnetic energy", "stored energy"],
        "category": "monitor",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#energy-density-spectra",
        "demo_hint": "공진기 내부 저장 에너지 시간 변화 모니터링. 링 공진기 에너지 축적 시각화",
    },
    {
        "name": "output_efield",
        "name_ko": "전기장 HDF5 출력",
        "aliases": ["output_efield_z", "output_hfield", "h5 output", "field dump"],
        "category": "monitor",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#output-functions",
        "demo_hint": "output_efield_z로 Ez 필드를 HDF5에 저장 후 h5py로 읽어서 imshow 시각화",
    },
    {
        "name": "MaterialGrid",
        "name_ko": "재료 격자 (역설계용)",
        "aliases": ["MaterialGrid", "design variable", "topology optimization", "inverse design"],
        "category": "optimization",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#materialgrid",
        "demo_hint": "2D 역설계 기본 구조. MaterialGrid 정의 + 초기 구조 시각화",
    },
]

PROMPT_TEMPLATE = """당신은 MEEP FDTD 전문가입니다.
MEEP의 "{name}" ({name_ko}) 개념을 아래 태그 형식 그대로 작성하세요.
헤더(##, #)나 구분선(---) 없이 태그만 사용하세요.

SUMMARY:
[1~2문장 핵심 요약]

EXPLANATION:
[상세 설명, 마크다운, 한국어]

PHYSICS_BACKGROUND:
[수식 중심 물리 배경, LaTeX: $수식$]

COMMON_MISTAKES:
["실수1", "실수2", "실수3"]

RELATED_CONCEPTS:
["개념1", "개념2"]

DEMO_CODE:
```python
# {demo_hint}
import matplotlib
matplotlib.use('Agg')
import meep as mp
import matplotlib.pyplot as plt
# ... 100줄 이내, resolution=10~20
plt.savefig('output.png')
```

DEMO_DESCRIPTION:
[코드 설명]
"""


def parse_simple(text: str) -> dict:
    """섹션별 정규식으로 직접 추출하는 단순 파서."""
    TAGS = ["SUMMARY", "EXPLANATION", "PHYSICS_BACKGROUND",
            "COMMON_MISTAKES", "RELATED_CONCEPTS", "DEMO_CODE", "DEMO_DESCRIPTION"]

    # 각 태그 위치 찾기 (태그: 로 시작하는 줄)
    positions = {}
    for tag in TAGS:
        m = re.search(rf'(?m)^{tag}:\s*\n?', text)
        if m:
            positions[tag] = (m.start(), m.end())

    def extract(tag):
        if tag not in positions:
            return ""
        content_start = positions[tag][1]
        # 다음 태그까지
        end = len(text)
        for other, (ostart, _) in positions.items():
            if other != tag and ostart > positions[tag][0]:
                end = min(end, ostart)
        return text[content_start:end].strip()

    result = {}
    result["summary"] = extract("SUMMARY")
    result["explanation"] = extract("EXPLANATION")
    result["physics_background"] = extract("PHYSICS_BACKGROUND")
    result["demo_description"] = extract("DEMO_DESCRIPTION")

    # COMMON_MISTAKES JSON
    cm = extract("COMMON_MISTAKES")
    try:
        m = re.search(r'\[[\s\S]*?\]', cm)
        result["common_mistakes"] = json.dumps(json.loads(m.group(0)), ensure_ascii=False) if m else "[]"
    except:
        result["common_mistakes"] = "[]"

    # RELATED_CONCEPTS JSON
    rc = extract("RELATED_CONCEPTS")
    try:
        m = re.search(r'\[[\s\S]*?\]', rc)
        result["related_concepts"] = json.dumps(json.loads(m.group(0)), ensure_ascii=False) if m else "[]"
    except:
        result["related_concepts"] = "[]"

    # DEMO_CODE
    m = re.search(r'```python\n(.*?)```', text, re.DOTALL)
    result["demo_code"] = m.group(1).strip() if m else ""

    return result


conn = sqlite3.connect(str(DB_PATH), timeout=10)
success = 0

for concept in TARGETS:
    name = concept["name"]
    prompt = PROMPT_TEMPLATE.format(**concept)
    print(f"🔄 {name} ({concept['name_ko']}) 재생성...")

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text
        parsed = parse_simple(text)

        summary_len = len(parsed.get("summary", ""))
        code_len = len(parsed.get("demo_code", ""))

        if summary_len < 20:
            print(f"  ⚠️  summary 짧음 ({summary_len}자): {repr(parsed.get('summary',''))[:80]}")
            print(f"  --- raw 앞 200자 ---")
            print(text[:200])

        conn.execute("""
            UPDATE concepts SET
                summary=?, explanation=?, physics_background=?,
                common_mistakes=?, related_concepts=?,
                demo_code=?, demo_description=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE name=?
        """, (
            parsed.get("summary", ""),
            parsed.get("explanation", ""),
            parsed.get("physics_background", ""),
            parsed.get("common_mistakes", "[]"),
            parsed.get("related_concepts", "[]"),
            parsed.get("demo_code", ""),
            parsed.get("demo_description", ""),
            name,
        ))
        conn.commit()
        print(f"  ✅ summary: {summary_len}자, code: {code_len}자")
        success += 1
        time.sleep(1)

    except Exception as e:
        print(f"  ❌ 실패: {e}")

conn.close()
print(f"\n=== 완료: {success}/{len(TARGETS)} ===")

# 최종 확인
conn = sqlite3.connect(str(DB_PATH))
total = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
ok = conn.execute("SELECT COUNT(*) FROM concepts WHERE LENGTH(summary) > 10").fetchone()[0]
print(f"최종 DB: {total}개 총 | {ok}개 summary OK")
conn.close()
