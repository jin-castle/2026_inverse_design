#!/usr/bin/env python3
"""
P5-direct: rate limit 없이 ChromaDB/SQLite 직접 검색으로 회귀 테스트
KB API 대신 내부 DB를 직접 쿼리하여 히트레이트 측정
"""
import sqlite3, json, sys
from pathlib import Path

DB_PATH   = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge.db")
TEST_DIR  = Path("/mnt/c/Users/user/projects/meep-kb/tests/kb_regression")

def run_direct_regression():
    """SQLite FTS로 직접 회귀 테스트 (rate limit 없음)"""
    conn = sqlite3.connect(str(DB_PATH), timeout=30)

    # fix_worked=1인 케이스 25건 가져와서 자기 자신을 찾는지 테스트
    cases = conn.execute("""
        SELECT id, error_type, error_message, symptom,
               symptom_numerical, symptom_behavioral, symptom_error_pattern,
               physics_cause, fix_description
        FROM sim_errors_v2
        WHERE fix_worked=1
          AND error_message IS NOT NULL
          AND error_message != ''
        LIMIT 25
    """).fetchall()

    print(f"\n[직접 DB 회귀 테스트] {len(cases)}건 (FTS + symptom 3분할)")
    print("-" * 65)

    pass_total = 0
    fts_pass = 0
    symptom_pass = 0

    for i, (id_, etype, emsg, symptom, sym_num, sym_beh, sym_err, phys, fix_desc) in enumerate(cases):
        # ── FTS 검색 (error_message 키워드) ─────────────────────────────────
        keywords = _extract_keywords_simple(emsg or "")
        fts_hit = False
        if keywords:
            fts_q = " OR ".join(f'"{kw}"' for kw in keywords[:3])
            try:
                rows = conn.execute("""
                    SELECT e.id, e.error_type, e.error_message
                    FROM sim_errors_v2 e
                    JOIN sim_errors_v2_fts f ON e.id = f.rowid
                    WHERE f.sim_errors_v2_fts MATCH ?
                    LIMIT 5
                """, (fts_q,)).fetchall()
                fts_hit = any(r[0] == id_ for r in rows)
            except:
                # FTS 없으면 LIKE 검색
                kw1 = keywords[0] if keywords else ""
                if kw1:
                    rows = conn.execute("""
                        SELECT id FROM sim_errors_v2
                        WHERE error_message LIKE ?
                        LIMIT 5
                    """, (f"%{kw1}%",)).fetchall()
                    fts_hit = any(r[0] == id_ for r in rows)

        # ── symptom_numerical / behavioral 검색 ──────────────────────────────
        sym_hit = False
        if sym_num:
            kw = sym_num[:40]
            rows = conn.execute("""
                SELECT id FROM sim_errors_v2
                WHERE symptom_numerical LIKE ?
                LIMIT 5
            """, (f"%{kw[:15]}%",)).fetchall()
            sym_hit = any(r[0] == id_ for r in rows)
        elif sym_beh:
            kw = sym_beh[:40]
            rows = conn.execute("""
                SELECT id FROM sim_errors_v2
                WHERE symptom_behavioral LIKE ?
                LIMIT 5
            """, (f"%{kw[:15]}%",)).fetchall()
            sym_hit = any(r[0] == id_ for r in rows)
        elif sym_err:
            kw = sym_err[:40]
            rows = conn.execute("""
                SELECT id FROM sim_errors_v2
                WHERE symptom_error_pattern LIKE ?
                LIMIT 5
            """, (f"%{kw[:15]}%",)).fetchall()
            sym_hit = any(r[0] == id_ for r in rows)

        overall = fts_hit or sym_hit
        if fts_hit:   fts_pass += 1
        if sym_hit:   symptom_pass += 1
        if overall:   pass_total += 1

        icon = "✓" if overall else "✗"
        fts_icon = "F" if fts_hit else "-"
        sym_icon = "S" if sym_hit else "-"
        print(f"  {icon} [{fts_icon}{sym_icon}] id={id_:3d} {(etype or 'Unknown')[:20]:20s} | "
              f"num={str(sym_num or '')[:25]:25s}")

    conn.close()
    total = len(cases)
    hit_rate = pass_total / total * 100 if total else 0
    print()
    print("=" * 65)
    print(f"결과: {pass_total}/{total} PASS  ({hit_rate:.0f}%)")
    print(f"  FTS 검색 성공:      {fts_pass}/{total} ({fts_pass/total*100:.0f}%)")
    print(f"  symptom 검색 성공:  {symptom_pass}/{total} ({symptom_pass/total*100:.0f}%)")
    print(f"  [F=FTS hit, S=symptom hit]")
    print("=" * 65)
    return {"total": total, "passed": pass_total, "hit_rate": hit_rate,
            "fts_pass": fts_pass, "symptom_pass": symptom_pass}


def _extract_keywords_simple(text: str) -> list:
    import re
    words = re.findall(r'[A-Za-z_]\w{4,}', text[:300])
    # Python 예외 이름 우선
    exception_words = [w for w in words if any(
        w.endswith(x) for x in ['Error','Warning','Exception','Issue'])]
    others = [w for w in words if w not in exception_words]
    combined = exception_words + others
    # 중복 제거하며 순서 유지
    seen, result = set(), []
    for w in combined:
        if w not in seen:
            seen.add(w)
            result.append(w)
    return result[:5]


def show_migration_stats():
    """P1 마이그레이션 결과 최종 채움률"""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    print("\n=== P1 마이그레이션 최종 채움률 ===")
    for t in ["sim_errors_v2", "sim_errors", "errors"]:
        tot = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        try:
            num = conn.execute(f"SELECT COUNT(*) FROM {t} WHERE symptom_numerical IS NOT NULL AND symptom_numerical != ''").fetchone()[0]
            beh = conn.execute(f"SELECT COUNT(*) FROM {t} WHERE symptom_behavioral IS NOT NULL AND symptom_behavioral != ''").fetchone()[0]
            err = conn.execute(f"SELECT COUNT(*) FROM {t} WHERE symptom_error_pattern IS NOT NULL AND symptom_error_pattern != ''").fetchone()[0]
            print(f"  [{t}] {tot}건")
            print(f"    numerical:     {num:4d} ({num/tot*100:.0f}%)")
            print(f"    behavioral:    {beh:4d} ({beh/tot*100:.0f}%)")
            print(f"    error_pattern: {err:4d} ({err/tot*100:.0f}%)")
        except:
            print(f"  [{t}] 컬럼 없음")
    try:
        fixed = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=1").fetchone()[0]
        vc = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE verification_criteria IS NOT NULL").fetchone()[0]
        ds = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE diagnostic_snippet IS NOT NULL").fetchone()[0]
        print(f"  [sim_errors_v2 fix_worked=1] {fixed}건")
        print(f"    verification_criteria: {vc}/{fixed} ({vc/fixed*100:.0f}%)")
        print(f"    diagnostic_snippet:    {ds}/{fixed} ({ds/fixed*100:.0f}%)")
    except: pass
    conn.close()


if __name__ == "__main__":
    show_migration_stats()
    run_direct_regression()
