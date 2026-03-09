"""
knowledge.db errors 테이블 → sim_errors 테이블로 이관
기존 sim_errors 스키마에 맞게 적응 + 필요 컬럼 추가

기존 컬럼: id, run_id, project_id, error_type, error_message, meep_version,
           context, root_cause, fix_applied, fix_worked, created_at
추가 컬럼: fix_description, fix_keywords, pattern_name, source, original_code

실행: python tools/ingest_errors_to_sim.py
"""
import sqlite3, json, re, os
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"


def add_missing_columns(conn):
    """기존 sim_errors 테이블에 필요한 컬럼 추가"""
    existing_cols = set()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(sim_errors)")
    for row in cur.fetchall():
        existing_cols.add(row[1])

    new_cols = {
        "fix_description": "TEXT",
        "fix_keywords": "TEXT",
        "pattern_name": "TEXT",
        "source": "TEXT DEFAULT 'github_issue'",
        "original_code": "TEXT",
        "fixed_code": "TEXT",
    }

    added = []
    for col, col_def in new_cols.items():
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE sim_errors ADD COLUMN {col} {col_def}")
            added.append(col)

    # 인덱스 추가
    conn.execute("CREATE INDEX IF NOT EXISTS idx_se_type ON sim_errors(error_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_se_fix_worked ON sim_errors(fix_worked)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_se_source ON sim_errors(source)")
    conn.commit()

    if added:
        print(f"✅ 컬럼 추가: {added}")
    else:
        print("✅ 기존 컬럼 그대로 사용")


def classify_error_type(text: str) -> str:
    text_l = text.lower()
    if "attributeerror" in text_l: return "AttributeError"
    if "typeerror" in text_l: return "TypeError"
    if "valueerror" in text_l: return "ValueError"
    if "importerror" in text_l or "no module" in text_l: return "ImportError"
    if "runtimeerror" in text_l: return "RuntimeError"
    if "syntaxerror" in text_l: return "SyntaxError"
    if "nameerror" in text_l: return "NameError"
    if "zerodivision" in text_l: return "ZeroDivisionError"
    if "diverge" in text_l or ("nan" in text_l and "meep" in text_l): return "Divergence"
    if "mpi" in text_l or "mpierror" in text_l: return "MPIError"
    if "eigenmode" in text_l or "eigenmodes" in text_l: return "EigenMode"
    if "pml" in text_l and "error" in text_l: return "PML"
    if "adjoint" in text_l or "optimizer" in text_l: return "Adjoint"
    if "memory" in text_l or "oom" in text_l: return "MemoryError"
    if "segfault" in text_l or "segmentation" in text_l: return "SegFault"
    if "materialgrid" in text_l: return "MaterialGrid"
    if "harminv" in text_l: return "Harminv"
    return "General"


def extract_keywords(text: str) -> list:
    meep_kws = re.findall(
        r'\b(EigenModeSource|PML|FluxRegion|Simulation|adjoint|MPI|MaterialGrid|'
        r'Harminv|OptimizationProblem|eig_parity|eig_band|add_flux|run_until|'
        r'resolution|force_complex_fields|near2far|dft_monitor|mp\.Vector3|'
        r'add_source|add_monitor|sim\.run|ContinuousSource|GaussianSource)\b',
        text
    )
    err_kws = re.findall(
        r'\b(AttributeError|TypeError|ValueError|RuntimeError|ImportError|'
        r'SyntaxError|NameError|diverge|NaN|overflow|segfault|memory|warning)\b',
        text, re.IGNORECASE
    )
    return list(set(meep_kws + err_kws))[:8]


def ingest_from_errors_table(conn, limit=300):
    """errors 테이블에서 solution 있는 항목 이관"""
    cur = conn.cursor()

    # 이미 이관된 것 확인
    cur.execute("SELECT pattern_name FROM sim_errors WHERE source='github_issue' AND pattern_name IS NOT NULL")
    already = set(r[0] for r in cur.fetchall())

    cur.execute("""
        SELECT id, error_msg, category, cause, solution, source_url
        FROM errors
        WHERE solution IS NOT NULL AND solution != ''
          AND LENGTH(solution) > 20
        ORDER BY id
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()

    inserted = 0
    for row in rows:
        eid, error_msg, category, cause, solution, source_url = row
        pat_name = f"github_issue_{eid}"

        if pat_name in already:
            continue

        text = (error_msg or "") + " " + (cause or "")
        error_type = classify_error_type(text)
        keywords = extract_keywords(text + " " + (solution or ""))

        fix_desc = (solution or "")[:500]
        context_text = f"카테고리: {category}\n원인: {(cause or '')[:400]}"

        cur.execute("""
            INSERT INTO sim_errors
              (run_id, project_id, error_type, error_message, meep_version,
               context, root_cause, fix_applied, fix_worked,
               fix_description, fix_keywords, pattern_name, source, original_code, fixed_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"kb_import_{eid}",
            "meep_kb",
            error_type,
            (error_msg or "")[:200],
            "",
            context_text,
            (cause or "")[:300],
            fix_desc[:300],
            1,  # fix_worked=True (GitHub에 해결책이 있음)
            fix_desc,
            json.dumps(keywords, ensure_ascii=False),
            pat_name,
            "github_issue",
            "",
            "",
        ))
        inserted += 1

    conn.commit()
    print(f"✅ GitHub issues → sim_errors: {inserted}개 삽입")
    return inserted


def ingest_from_typee_err_files(conn):
    """typee_err_*.txt, typeb_err_*.txt 파일 수집"""
    cur = conn.cursor()

    cur.execute("SELECT pattern_name FROM sim_errors WHERE source='err_file' AND pattern_name IS NOT NULL")
    already = set(r[0] for r in cur.fetchall())

    err_files = list(BASE.glob("typee_err_*.txt")) + list(BASE.glob("typeb_err_*.txt"))

    inserted = 0
    for f in err_files:
        content = f.read_text(encoding="utf-8", errors="replace").strip()
        if not content:
            continue

        m = re.search(r'_(err_)(\d+)', f.name)
        pat_num = m.group(2) if m else "unknown"
        prefix = "typee" if "typee" in f.name else "typeb"
        pat_name = f"{prefix}_{pat_num}"

        if pat_name in already:
            continue

        # 대응하는 fixed 파일 확인
        fixed_code = ""
        fix_worked = 0
        for ext in ["py"]:
            fixed_file = BASE / f"{prefix}_fixed_{pat_num}.{ext}"
            if fixed_file.exists():
                fixed_code = fixed_file.read_text(encoding="utf-8", errors="replace")[:3000]
                fix_worked = 1
                break

        # 원본 코드
        orig_code = ""
        for code_f in BASE.glob(f"code_{pat_num}.py"):
            orig_code = code_f.read_text(encoding="utf-8", errors="replace")[:3000]
            break

        error_type = classify_error_type(content)
        keywords = extract_keywords(content)

        cur.execute("""
            INSERT INTO sim_errors
              (run_id, project_id, error_type, error_message, meep_version,
               context, root_cause, fix_applied, fix_worked,
               fix_description, fix_keywords, pattern_name, source,
               original_code, fixed_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"typee_run_{pat_num}",
            "meep_kb",
            error_type,
            content[:200],
            "",
            content[:1000],
            error_type,
            fixed_code[:300] if fixed_code else "",
            fix_worked,
            f"{'수정 완료' if fix_worked else '수정 코드 없음'} (패턴 {pat_name})",
            json.dumps(keywords, ensure_ascii=False),
            pat_name,
            "err_file",
            orig_code,
            fixed_code,
        ))
        inserted += 1

    conn.commit()
    print(f"✅ 에러 파일(typee/typeb): {inserted}개 삽입")
    return inserted


def ingest_from_agent2_failed(conn):
    """agent2_failed.json 수집"""
    failed_path = BASE / "agent2_failed.json"
    if not failed_path.exists():
        return 0

    try:
        data = json.load(open(failed_path, encoding="utf-8-sig"))
    except Exception as e:
        print(f"⚠️  agent2_failed.json 읽기 실패: {e}")
        return 0

    cur = conn.cursor()
    cur.execute("SELECT pattern_name FROM sim_errors WHERE source='agent2' AND pattern_name IS NOT NULL")
    already = set(r[0] for r in cur.fetchall())

    inserted = 0
    for item in data:
        err = item.get("error", "") or item.get("stderr", "") or item.get("error_msg", "") or ""
        code = item.get("code", "") or item.get("script", "") or ""
        pat = str(item.get("pattern", "") or item.get("id", "") or item.get("example_id", "agent2"))

        if not err or pat in already:
            continue

        error_type = classify_error_type(err)
        keywords = extract_keywords(err + " " + code[:300])

        cur.execute("""
            INSERT INTO sim_errors
              (run_id, project_id, error_type, error_message, meep_version,
               context, root_cause, fix_applied, fix_worked,
               fix_description, fix_keywords, pattern_name, source,
               original_code, fixed_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"agent2_{pat}",
            "meep_kb",
            error_type,
            err[:200],
            "",
            err[:1000],
            error_type,
            "",
            0,
            "",
            json.dumps(keywords, ensure_ascii=False),
            pat,
            "agent2",
            code[:3000],
            "",
        ))
        inserted += 1

    conn.commit()
    print(f"✅ agent2_failed.json: {inserted}개 삽입")
    return inserted


def show_stats(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sim_errors")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM sim_errors WHERE fix_worked=1")
    verified = cur.fetchone()[0]
    print(f"\n📊 sim_errors 현황: 총 {total}개 (fix_worked=1: {verified}개)")
    cur.execute("SELECT error_type, COUNT(*) FROM sim_errors GROUP BY error_type ORDER BY COUNT(*) DESC LIMIT 12")
    print("에러 타입별:")
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]}개")
    cur.execute("SELECT source, COUNT(*) FROM sim_errors GROUP BY source")
    print("소스별:")
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]}개")


if __name__ == "__main__":
    print(f"DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    add_missing_columns(conn)
    ingest_from_errors_table(conn, limit=300)
    ingest_from_typee_err_files(conn)
    ingest_from_agent2_failed(conn)
    show_stats(conn)
    conn.close()
    print("\n✅ 완료!")
