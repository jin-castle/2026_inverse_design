"""
patterns 테이블의 한국어 description/use_case → 영어 일괄 변환
- 한국어 감지: 한글 유니코드 범위 (0xAC00~0xD7A3, 0x3131~0x314E)
- Anthropic Claude API로 번역
- 백업 먼저, 그 다음 업데이트
"""

import sqlite3
import re
import os
import time
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

DB_PATH = "db/knowledge.db"

def has_korean(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r'[\uAC00-\uD7A3\u3131-\u314E\u314F-\u3163]', text))

def translate_to_english(text: str, field_type: str) -> str:
    """Claude로 기술 문서 번역"""
    if field_type == "description":
        instruction = (
            "Translate the following MEEP/photonics simulation pattern description to English. "
            "Keep technical terms (MEEP, FDTD, SOI, TE, TM, adjoint, etc.) as-is. "
            "Be concise and precise. Output ONLY the translated text, nothing else."
        )
    else:  # use_case
        instruction = (
            "Translate the following MEEP/photonics use_case field to English. "
            "This field is used as a search query guide — keep it as natural English search phrases. "
            "Keep technical terms as-is. Output ONLY the translated text, nothing else."
        )
    
    msg = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"{instruction}\n\nText:\n{text}"
        }]
    )
    return msg.content[0].text.strip()

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 백업
    import shutil
    backup_path = DB_PATH.replace('.db', '_backup_before_translate.db')
    shutil.copy2(DB_PATH, backup_path)
    print(f"[OK] Backup: {backup_path}")

    # 한국어 포함 패턴 조회
    cur.execute("SELECT id, pattern_name, description, use_case FROM patterns")
    rows = cur.fetchall()

    to_translate = []
    for row in rows:
        pid, name, desc, use_case = row
        needs_desc = has_korean(desc)
        needs_use = has_korean(use_case)
        if needs_desc or needs_use:
            to_translate.append((pid, name, desc, use_case, needs_desc, needs_use))

    print(f"\n[STAT] Total: {len(rows)} | Korean: {len(to_translate)}\n")

    updated = 0
    errors = 0

    for i, (pid, name, desc, use_case, needs_desc, needs_use) in enumerate(to_translate):
        print(f"[{i+1}/{len(to_translate)}] id={pid} | {name}")
        
        new_desc = desc
        new_use = use_case

        try:
            if needs_desc and desc:
                new_desc = translate_to_english(desc, "description")
                print(f"  description: {desc[:60]}...")
                print(f"           → {new_desc[:60]}...")

            if needs_use and use_case:
                new_use = translate_to_english(use_case, "use_case")
                print(f"  use_case: {use_case[:60]}...")
                print(f"         → {new_use[:60]}...")

            cur.execute(
                "UPDATE patterns SET description=?, use_case=? WHERE id=?",
                (new_desc, new_use, pid)
            )
            updated += 1
            time.sleep(0.3)  # rate limit 방지

        except Exception as e:
            print(f"  [ERR] {e}")
            errors += 1
            continue

    conn.commit()
    conn.close()

    print(f"\n[DONE] Updated: {updated} | Errors: {errors}")

if __name__ == "__main__":
    main()
