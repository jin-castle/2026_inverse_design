"""
GitHub Issues 영어 토론 → 구조화된 한국어 해결책 변환
errors 테이블 solution → sim_errors 테이블 structured entries

실행:
  python tools/solution_structurer.py --dry-run --limit 5   # 테스트
  python tools/solution_structurer.py --limit 50            # 배치 실행
  python tools/solution_structurer.py                       # 전체 실행

비용: Claude Haiku 기준 ~$0.001/건 → 500건 = $0.5
"""
import sqlite3, json, re, os, time, argparse
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"

# --------------------------------------------------------------------------
# Claude API 호출
# --------------------------------------------------------------------------

def load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    env = BASE / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


SYSTEM_PROMPT = """당신은 MEEP (MIT Electromagnetic Equation Propagation) 광학 시뮬레이션 전문가입니다.
GitHub Issues의 영어 토론 텍스트에서 핵심 에러 해결책을 추출해 한국어로 구조화하는 역할을 합니다."""

def make_user_prompt(error_msg: str, discussion: str) -> str:
    return f"""다음 MEEP GitHub Issue 토론에서 핵심 해결책을 추출해주세요.

## 에러/문제 제목
{error_msg[:200]}

## 토론 내용
{discussion[:1500]}

## 요청 형식 (JSON으로만 응답)
{{
  "root_cause": "에러의 근본 원인 (한국어, 1-2문장)",
  "fix_description": "해결 방법 설명 (한국어, 구체적으로 3-5문장)",
  "fix_code": "핵심 수정 코드 스니펫 (Python, 없으면 빈 문자열)",
  "keywords": ["검색 키워드 5개 이내, 영어"],
  "error_type": "AttributeError|TypeError|ValueError|RuntimeError|ImportError|Divergence|MPIError|EigenMode|PML|Adjoint|General 중 하나",
  "confidence": 0.0~1.0
}}

해결책이 토론에 명확히 없으면 confidence를 0.3 이하로 설정하세요.
반드시 JSON만 응답하세요."""


def call_claude(api_key: str, error_msg: str, discussion: str) -> dict:
    """Claude Haiku API 호출"""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": make_user_prompt(error_msg, discussion)}],
        )
        text = msg.content[0].text.strip()
        # JSON 파싱
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            return json.loads(m.group())
        return {}
    except Exception as e:
        return {"error": str(e)}


# --------------------------------------------------------------------------
# 메인 처리
# --------------------------------------------------------------------------

def get_candidates(conn, limit: int = 0) -> list:
    """errors 테이블에서 처리 대상 선정"""
    # 이미 sim_errors에 있는 것 제외
    already = set()
    for row in conn.execute(
        "SELECT pattern_name FROM sim_errors WHERE source='github_structured' AND pattern_name IS NOT NULL"
    ).fetchall():
        already.add(row[0])

    query = """
        SELECT id, error_msg, cause, solution, category
        FROM errors
        WHERE source_type = 'github_issue'
          AND solution IS NOT NULL
          AND LENGTH(solution) > 100
        ORDER BY LENGTH(solution) DESC
    """
    if limit:
        query += f" LIMIT {limit * 2}"  # 여유있게 가져와서 필터링

    rows = conn.execute(query).fetchall()

    # 이미 처리된 것 제외
    candidates = []
    for row in rows:
        pat = f"github_issue_{row[0]}"
        if pat not in already:
            candidates.append(row)
        if limit and len(candidates) >= limit:
            break

    return candidates


def save_to_sim_errors(conn, row: tuple, result: dict) -> bool:
    """구조화된 결과를 sim_errors에 저장"""
    eid, error_msg, cause, solution, category = row

    if not result or result.get("confidence", 0) < 0.3:
        return False

    fix_desc = result.get("fix_description", "")
    fix_code = result.get("fix_code", "")
    root_cause = result.get("root_cause", "")
    error_type = result.get("error_type", "General")
    keywords = result.get("keywords", [])

    if not fix_desc:
        return False

    # fix_applied 구성 (짧은 요약)
    fix_applied = fix_desc[:300]

    try:
        conn.execute("""
            INSERT INTO sim_errors
              (run_id, project_id, error_type, error_message, meep_version,
               context, root_cause, fix_applied, fix_worked,
               fix_description, fix_keywords, pattern_name, source,
               original_code, fixed_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"gh_structured_{eid}",
            "github_kb",
            error_type,
            (error_msg or "")[:200],
            "",
            (cause or solution or "")[:500],
            root_cause[:300],
            fix_applied,
            1,  # fix_worked = 1 (GitHub에 해결됐다고 나온 것)
            fix_desc[:1000],
            json.dumps(keywords, ensure_ascii=False),
            f"github_issue_{eid}",
            "github_structured",
            "",
            fix_code[:2000] if fix_code else "",
        ))
        return True
    except Exception as e:
        print(f"    저장 오류: {e}")
        return False


def run(limit: int = 0, dry_run: bool = False, sleep_ms: int = 200):
    api_key = load_api_key()
    if not api_key:
        print("ANTHROPIC_API_KEY 없음. .env 파일 확인")
        return

    conn = sqlite3.connect(DB_PATH)
    candidates = get_candidates(conn, limit)
    print(f"처리 대상: {len(candidates)}개 {'(dry-run)' if dry_run else ''}")

    saved = 0
    skipped = 0
    errors_count = 0

    for i, row in enumerate(candidates):
        eid, error_msg, cause, solution, category = row
        print(f"\n[{i+1}/{len(candidates)}] {error_msg[:60]}")

        # 토론 텍스트 구성 (cause + solution)
        discussion = ""
        if cause and len(cause) > 20:
            discussion += f"[질문/상황]\n{cause[:600]}\n\n"
        if solution:
            discussion += f"[답변/해결]\n{solution[:800]}"

        if len(discussion) < 50:
            print("  → 건너뜀 (내용 부족)")
            skipped += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] 처리 대상 확인됨")
            print(f"  토론: {discussion[:100]}...")
            continue

        # LLM 호출
        result = call_claude(api_key, error_msg, discussion)

        if "error" in result:
            print(f"  → API 오류: {result['error']}")
            errors_count += 1
            time.sleep(1)
            continue

        confidence = result.get("confidence", 0)
        error_type = result.get("error_type", "?")
        fix_desc = result.get("fix_description", "")[:80]
        print(f"  → {error_type} (신뢰도: {confidence:.2f}) | {fix_desc}")

        if confidence < 0.3:
            print("  → 건너뜀 (신뢰도 낮음)")
            skipped += 1
            continue

        if save_to_sim_errors(conn, row, result):
            conn.commit()
            saved += 1
            print(f"  → 저장됨 (sim_errors total: {saved})")
        else:
            skipped += 1

        time.sleep(sleep_ms / 1000.0)  # Rate limiting

    conn.close()

    # 결과 통계
    print(f"\n{'='*50}")
    print(f"완료: {saved}개 저장, {skipped}개 건너뜀, {errors_count}개 오류")

    if not dry_run:
        # 최종 sim_errors 현황
        conn2 = sqlite3.connect(DB_PATH)
        total = conn2.execute("SELECT COUNT(*) FROM sim_errors").fetchone()[0]
        verified = conn2.execute("SELECT COUNT(*) FROM sim_errors WHERE fix_worked=1").fetchone()[0]
        conn2.close()
        print(f"sim_errors 현황: 총 {total}개 (검증됨: {verified}개)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="처리 개수 제한 (0=전체)")
    parser.add_argument("--dry-run", action="store_true", help="실제 저장 없이 미리보기")
    parser.add_argument("--sleep-ms", type=int, default=300, help="API 호출 간격(ms)")
    args = parser.parse_args()
    run(args.limit, args.dry_run, args.sleep_ms)
