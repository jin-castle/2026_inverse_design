"""
meep-kb DB → Fine-tuning용 JSONL 데이터셋 변환
형식: {"instruction": ..., "input": ..., "output": ...}

실행: python tools/export_finetune_data.py
출력: finetune_data/meep_dataset.jsonl
"""
import sqlite3, json, re, os
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"
OUT_DIR = BASE / "finetune_data"
OUT_DIR.mkdir(exist_ok=True)


DIAGNOSE_INSTRUCTION = (
    "다음 MEEP 시뮬레이션 코드에서 발생한 에러를 진단하고, "
    "원인과 수정 방법을 한국어로 설명해주세요. "
    "수정된 코드 스니펫을 포함해야 합니다."
)

EXPLAIN_INSTRUCTION = (
    "다음 MEEP 코드가 하는 일을 설명하고, "
    "주요 파라미터와 물리적 의미를 한국어로 설명해주세요."
)


def clean_text(t: str, max_len: int = 2000) -> str:
    if not t: return ""
    t = t.strip()[:max_len]
    return t


def format_diagnose_output(cause: str, solution: str, error_type: str = "") -> str:
    """에러 진단 출력 형식 통일"""
    parts = []
    if error_type and error_type not in ("General", ""):
        parts.append(f"## 에러 타입\n**{error_type}**")
    if cause and len(cause.strip()) > 10:
        parts.append(f"## 원인 분석\n{cause.strip()}")
    if solution and len(solution.strip()) > 10:
        # 코드 블록이 없으면 감싸기
        sol = solution.strip()
        parts.append(f"## 해결 방법\n{sol}")
    return "\n\n".join(parts) if parts else solution


def export_from_sim_errors(conn) -> list:
    """sim_errors 테이블 → 진단 데이터"""
    records = []
    rows = conn.execute("""
        SELECT error_type, error_message, context, root_cause,
               fix_description, fix_applied, original_code, fixed_code
        FROM sim_errors
        WHERE fix_worked=1
          AND (fix_description IS NOT NULL OR fix_applied IS NOT NULL)
          AND LENGTH(COALESCE(fix_description, fix_applied, '')) > 30
    """).fetchall()

    for row in rows:
        error_type, error_msg, context, root_cause, fix_desc, fix_applied, orig_code, fixed_code = row

        # 에러 메시지가 너무 짧으면 스킵
        if not error_msg or len(error_msg) < 10:
            continue

        # input 구성
        input_parts = []
        if orig_code and len(orig_code.strip()) > 20:
            input_parts.append(f"**코드:**\n```python\n{orig_code.strip()[:800]}\n```")
        if error_msg:
            input_parts.append(f"**에러 메시지:**\n```\n{error_msg.strip()[:400]}\n```")
        if context and context not in error_msg:
            input_parts.append(f"**컨텍스트:**\n{context.strip()[:200]}")

        if not input_parts:
            continue

        # output 구성
        cause = root_cause or ""
        solution = fix_desc or fix_applied or ""
        # fixed_code 있으면 추가
        if fixed_code and len(fixed_code.strip()) > 20:
            if "```python" not in solution:
                solution += f"\n\n**수정 코드:**\n```python\n{fixed_code.strip()[:600]}\n```"

        output = format_diagnose_output(cause, solution, error_type)
        if len(output) < 20:
            continue

        records.append({
            "instruction": DIAGNOSE_INSTRUCTION,
            "input": "\n\n".join(input_parts),
            "output": output,
            "source": "sim_errors",
            "error_type": error_type,
        })

    print(f"  sim_errors → {len(records)}개")
    return records


def export_from_errors_table(conn) -> list:
    """errors 테이블 (GitHub Issues) → 진단 데이터"""
    records = []
    rows = conn.execute("""
        SELECT error_msg, category, cause, solution
        FROM errors
        WHERE solution IS NOT NULL AND solution != ''
          AND LENGTH(solution) > 50
          AND LENGTH(COALESCE(cause, '')) > 20
    """).fetchall()

    for row in rows:
        error_msg, category, cause, solution = row

        if not solution or len(solution) < 50:
            continue

        # GitHub issue 형식: error_msg는 제목, cause는 질문 내용
        input_text = f"**에러/문제:**\n{error_msg.strip()}"
        if cause and len(cause) > 20:
            # 질문 내용 앞부분만
            cause_short = cause.strip()[:400]
            input_text += f"\n\n**상황 설명:**\n{cause_short}"

        output = f"## 해결 방법\n{solution.strip()[:800]}"

        records.append({
            "instruction": DIAGNOSE_INSTRUCTION,
            "input": input_text,
            "output": output,
            "source": "github_issue",
            "error_type": category,
        })

    print(f"  errors(GitHub) → {len(records)}개")
    return records


def export_from_typee_files() -> list:
    """typee_err_*.txt + typee_fixed_*.py 쌍 → before-after 데이터"""
    records = []
    err_files = list(BASE.glob("typee_err_*.txt")) + list(BASE.glob("typeb_err_*.txt"))

    for f in err_files:
        err_content = f.read_text(encoding="utf-8", errors="replace").strip()
        if not err_content or len(err_content) < 20:
            continue

        m = re.search(r'_(err_)(\d+)', f.name)
        if not m:
            continue
        pat_num = m.group(2)
        prefix = "typee" if "typee" in f.name else "typeb"

        # 대응하는 fixed 파일 찾기
        fixed_file = BASE / f"{prefix}_fixed_{pat_num}.py"
        if not fixed_file.exists():
            continue

        fixed_code = fixed_file.read_text(encoding="utf-8", errors="replace").strip()
        if len(fixed_code) < 50:
            continue

        # 원본 코드 찾기
        orig_code = ""
        for orig_f in BASE.glob(f"code_{pat_num}.py"):
            orig_code = orig_f.read_text(encoding="utf-8", errors="replace").strip()
            break

        input_text = f"**에러 메시지:**\n```\n{err_content[:400]}\n```"
        if orig_code:
            input_text = f"**원본 코드:**\n```python\n{orig_code[:600]}\n```\n\n" + input_text

        output = f"## 수정된 코드\n```python\n{fixed_code[:1000]}\n```"

        records.append({
            "instruction": DIAGNOSE_INSTRUCTION,
            "input": input_text,
            "output": output,
            "source": "typee_fixed",
            "error_type": "SyntaxError",
        })

    print(f"  typee/typeb fixed 파일 → {len(records)}개")
    return records


def export_from_examples(conn) -> list:
    """examples 테이블 → 코드 설명 데이터"""
    records = []
    rows = conn.execute("""
        SELECT title, code, description_ko, description
        FROM examples
        WHERE code IS NOT NULL AND LENGTH(code) > 50
          AND (description_ko IS NOT NULL OR description IS NOT NULL)
    """).fetchall()

    for row in rows:
        title, code, desc_ko, desc_en = row
        desc = desc_ko or desc_en or ""
        if not desc or len(desc) < 30:
            continue

        input_text = f"**코드 제목:** {title}\n\n```python\n{code.strip()[:800]}\n```"
        output = desc.strip()[:1000]

        records.append({
            "instruction": EXPLAIN_INSTRUCTION,
            "input": input_text,
            "output": output,
            "source": "examples",
            "error_type": "N/A",
        })

    print(f"  examples(코드 설명) → {len(records)}개")
    return records


def deduplicate(records: list) -> list:
    """중복 제거 (input 기준 앞 80자 해시)"""
    seen = set()
    unique = []
    for r in records:
        key = r["input"][:80].strip()
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def split_train_test(records: list, test_ratio=0.1):
    import random
    random.seed(42)
    random.shuffle(records)
    n_test = max(50, int(len(records) * test_ratio))
    return records[n_test:], records[:n_test]


def save_jsonl(records, path):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            # fine-tuning용 단순 형식 (source/error_type 제외)
            item = {
                "instruction": r["instruction"],
                "input": r["input"],
                "output": r["output"],
            }
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def save_alpaca_format(records, path):
    """Alpaca 형식 (많은 fine-tuning 프레임워크 지원)"""
    data = []
    for r in records:
        # Alpaca 형식: instruction + input → output
        prompt = r["instruction"]
        if r["input"]:
            prompt += f"\n\n{r['input']}"
        data.append({
            "instruction": r["instruction"],
            "input": r["input"],
            "output": r["output"],
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print(f"DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    print("\n데이터 수출 중...")
    all_records = []
    all_records.extend(export_from_sim_errors(conn))
    all_records.extend(export_from_errors_table(conn))
    all_records.extend(export_from_typee_files())
    all_records.extend(export_from_examples(conn))
    conn.close()

    print(f"\n원본 합계: {len(all_records)}개")

    # 중복 제거
    unique = deduplicate(all_records)
    print(f"중복 제거 후: {len(unique)}개")

    # train/test 분리
    train, test = split_train_test(unique)
    print(f"train: {len(train)}개, test: {len(test)}개")

    # 저장
    save_jsonl(train, OUT_DIR / "train.jsonl")
    save_jsonl(test, OUT_DIR / "test.jsonl")
    save_alpaca_format(train, OUT_DIR / "train_alpaca.json")

    # 통계
    from collections import Counter
    by_source = Counter(r["source"] for r in unique)
    print("\n소스별 분포:")
    for s, c in by_source.most_common():
        print(f"  {s}: {c}개")

    print(f"\n파일 저장 완료:")
    print(f"  {OUT_DIR}/train.jsonl ({len(train)}개)")
    print(f"  {OUT_DIR}/test.jsonl ({len(test)}개)")
    print(f"  {OUT_DIR}/train_alpaca.json ({len(train)}개)")
    print(f"\n다음 단계: python finetune/train_qlora.py --data finetune_data/train.jsonl")
