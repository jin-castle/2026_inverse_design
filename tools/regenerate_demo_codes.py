#!/usr/bin/env python3
"""
result_status='error'인 concepts의 demo_code를 강화된 프롬프트로 재생성.
Usage: python -u -X utf8 tools/regenerate_demo_codes.py [--name FluxRegion]
"""
import os, sys, re, json, sqlite3, time, argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"

PROMPT_TEMPLATE = """당신은 MEEP FDTD 시뮬레이션 전문가입니다.
MEEP의 "{name}" ({name_ko}) 개념의 데모 코드를 작성해주세요.

카테고리: {category} | 난이도: {difficulty}
데모 힌트: {demo_hint}

## 절대 규칙 (어기면 안 됨)
1. **완전히 독립 실행 가능한 코드** — import부터 마지막 줄까지 그 자체로 실행 가능해야 함
2. **import meep as mp** 반드시 포함 (meep.adjoint는 절대 import 금지 — autograd 없음)
3. **한글 변수명 절대 금지** — 모든 변수명은 영어로
4. **matplotlib.use('Agg')** 반드시 맨 앞에 포함
5. **plt.savefig('output.png')** 로 이미지 저장 (plt.show() 사용 금지)
6. **resolution=10** 이하로 설정 (빠른 실행)
7. **100줄 이하**
8. **SyntaxError 없는 완성된 코드** — 부분 코드, 스니펫 금지
9. **NameError 없도록** — 사용하는 모든 변수는 코드 내에서 정의
10. **mp.adjoint, mpa, OptimizationProblem, MaterialGrid** 등 adjoint 관련 API 사용 금지

## 출력 형식 (이 형식 그대로, 다른 텍스트 없이)

DEMO_CODE:
```python
import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# ... 완전한 독립 실행 코드 ...

plt.savefig('output.png')
print("Done")
```

DEMO_DESCRIPTION:
[코드가 보여주는 것 한국어로 2~3문장]
"""


def extract_code_and_desc(text: str) -> tuple:
    """raw LLM 응답에서 demo_code와 demo_description 추출."""
    # DEMO_CODE 섹션
    m = re.search(r'DEMO_CODE:\s*\n```python\n(.*?)```', text, re.DOTALL)
    if not m:
        m = re.search(r'```python\n(.*?)```', text, re.DOTALL)
    code = m.group(1).strip() if m else ""

    # DEMO_DESCRIPTION 섹션
    m2 = re.search(r'DEMO_DESCRIPTION:\s*\n(.*?)(?:\n##|\Z)', text, re.DOTALL)
    desc = m2.group(1).strip() if m2 else ""

    return code, desc


def load_targets(name_filter=None):
    conn = sqlite3.connect(str(DB_PATH))
    if name_filter:
        rows = conn.execute(
            "SELECT name, name_ko, category, difficulty, demo_description FROM concepts WHERE name=?",
            (name_filter,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT name, name_ko, category, difficulty, demo_description FROM concepts "
            "WHERE result_status='error' ORDER BY difficulty, category, name"
        ).fetchall()
    conn.close()
    return [{"name": r[0], "name_ko": r[1], "category": r[2],
             "difficulty": r[3], "demo_hint": r[4] or r[0] + " 기본 예제"} for r in rows]


def save_demo_code(conn, name, code, desc):
    conn.execute(
        "UPDATE concepts SET demo_code=?, demo_description=?, "
        "result_status='pending', updated_at=CURRENT_TIMESTAMP WHERE name=?",
        (code, desc, name)
    )
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="특정 개념만 재생성")
    parser.add_argument("--all", action="store_true", default=True)
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY 없음"); sys.exit(1)

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    targets = load_targets(args.name)
    print(f"재생성 대상: {len(targets)}개\n")

    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    success = 0

    for i, concept in enumerate(targets, 1):
        name = concept["name"]
        prompt = PROMPT_TEMPLATE.format(**concept)

        print(f"[{i}/{len(targets)}] 🔄 {name} ({concept['name_ko']})...")
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5",  # 빠르고 저렴한 모델
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text
            code, desc = extract_code_and_desc(text)

            if not code or len(code) < 30:
                print(f"  ⚠️  코드 짧음 ({len(code)}자)")
            elif "import meep" not in code:
                print(f"  ⚠️  meep import 없음")
            else:
                save_demo_code(conn, name, code, desc)
                print(f"  ✅ 저장 ({len(code)}자)")
                success += 1

            time.sleep(0.5)

        except Exception as e:
            print(f"  ❌ 실패: {e}")

    conn.close()
    print(f"\n=== 완료: {success}/{len(targets)} ===")


if __name__ == "__main__":
    main()
