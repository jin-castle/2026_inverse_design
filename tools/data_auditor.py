# -*- coding: utf-8 -*-
"""
data_auditor.py — Phase 1: DB 데이터 품질 감사
=====================================================
sim_errors (github_issue + github_structured) 393건에서 실행 가능한 코드 분류,
examples 616건에서 독립 실행 가능 코드 추출.

실행:
  python tools/data_auditor.py
"""
import re, json, sqlite3
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"
REPORT_PATH = Path(__file__).parent / "audit_report.json"


# ──────────────────────────────────────────────────────────────────────────────
# 코드 추출 유틸
# ──────────────────────────────────────────────────────────────────────────────

def extract_code_blocks(text: str) -> list[str]:
    """마크다운 코드블록 또는 들여쓰기 코드 추출"""
    if not text:
        return []
    blocks = re.findall(r'```(?:python)?\n(.*?)```', text, re.DOTALL)
    if blocks:
        return [b.strip() for b in blocks if b.strip()]
    # 코드블록 없으면 전체 텍스트 자체가 코드인지 확인
    if "import meep" in text or "import meep as mp" in text:
        return [text.strip()]
    return []


def has_meep_import(code: str) -> bool:
    return bool(re.search(r'\bimport meep\b|\bimport meep as mp\b', code))

def has_simulation(code: str) -> bool:
    return bool(re.search(r'mp\.Simulation\s*\(|meep\.Simulation\s*\(', code))

def has_sim_run(code: str) -> bool:
    return bool(re.search(r'\bsim\.run\s*\(|\bsim\.run_until\b', code))

def is_independently_runnable(code: str) -> bool:
    """독립 실행 가능: import meep + mp.Simulation + sim.run 3박자"""
    return has_meep_import(code) and has_simulation(code) and has_sim_run(code)

def has_external_dependencies(code: str) -> bool:
    """외부 의존성 체크"""
    patterns = [
        r'from common import',
        r'from utils import',
        r'from helper import',
        r'import common\b',
        r'open\s*\(["\'][^"\']+\.(csv|txt|npy|npz|h5|hdf5)["\']',  # 로컬 파일
        r'sys\.argv\[',
        r'argparse\.ArgumentParser',
        r'np\.load\s*\(',
        r'np\.loadtxt\s*\(',
        r'from \. import',  # 상대 임포트
        r'from \.\.',
    ]
    return any(re.search(p, code) for p in patterns)

def has_security_risk(code: str) -> bool:
    """보안 위험 체크"""
    patterns = [
        r'\bsubprocess\b',
        r'\bshutil\.rmtree\b',
        r'\bos\.system\b',
        r'\bos\.remove\b',
        r'\beval\s*\(',
        r'\bexec\s*\(',
        r'\b__import__\s*\(',
    ]
    return any(re.search(p, code) for p in patterns)

def classify_code(code: str) -> dict:
    """코드 분류 결과 반환"""
    runnable = is_independently_runnable(code)
    ext_dep = has_external_dependencies(code) if runnable else False
    sec_risk = has_security_risk(code)
    return {
        "has_meep_import": has_meep_import(code),
        "has_simulation": has_simulation(code),
        "has_sim_run": has_sim_run(code),
        "independently_runnable": runnable and not ext_dep and not sec_risk,
        "external_dependencies": ext_dep,
        "security_risk": sec_risk,
        "code_length": len(code),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Phase 1-A: sim_errors 감사 (github_issue + github_structured)
# ──────────────────────────────────────────────────────────────────────────────

def audit_sim_errors(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("""
        SELECT id, error_type, error_message, context, original_code, source
        FROM sim_errors
        WHERE source IN ('github_issue', 'github_structured')
    """).fetchall()

    total = len(rows)
    has_code = []
    runnable = []
    no_code = []

    for row in rows:
        id_, err_type, err_msg, context, orig_code, source = row

        # 코드 후보: original_code, context, error_message 순으로 탐색
        code_candidates = [orig_code or "", context or "", err_msg or ""]
        best_code = ""
        best_cls = None

        for candidate in code_candidates:
            blocks = extract_code_blocks(candidate)
            if not blocks:
                if has_meep_import(candidate):
                    blocks = [candidate]
            for block in blocks:
                cls = classify_code(block)
                if cls["independently_runnable"]:
                    best_code = block
                    best_cls = cls
                    break
                elif cls["has_meep_import"] and not best_code:
                    best_code = block
                    best_cls = cls
            if best_cls and best_cls["independently_runnable"]:
                break

        entry = {
            "id": id_,
            "source": source,
            "error_type": err_type,
            "code_snippet": best_code[:200] if best_code else "",
        }

        if best_cls and best_cls["independently_runnable"]:
            runnable.append({**entry, **best_cls, "full_code": best_code})
        elif best_code:
            has_code.append({**entry, **(best_cls or {}), "full_code": best_code})
        else:
            no_code.append(entry)

    return {
        "total": total,
        "runnable_count": len(runnable),
        "has_code_count": len(has_code),
        "no_code_count": len(no_code),
        "runnable": runnable,
        "has_code": has_code,
        "no_code_ids": [x["id"] for x in no_code],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Phase 1-B: examples 감사
# ──────────────────────────────────────────────────────────────────────────────

def audit_examples(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("""
        SELECT id, title, code, tags, source_repo, result_status
        FROM examples
    """).fetchall()

    total = len(rows)
    runnable = []
    not_runnable = []

    for row in rows:
        id_, title, code, tags, source_repo, result_status = row
        if not code:
            not_runnable.append({"id": id_, "title": title, "reason": "no_code"})
            continue

        cls = classify_code(code)

        entry = {
            "id": id_,
            "title": title,
            "source_repo": source_repo,
            "tags": tags,
            "result_status": result_status,
            "code_length": cls["code_length"],
            "has_meep_import": cls["has_meep_import"],
            "has_simulation": cls["has_simulation"],
            "has_sim_run": cls["has_sim_run"],
            "external_dependencies": cls["external_dependencies"],
            "security_risk": cls["security_risk"],
        }

        if cls["independently_runnable"]:
            runnable.append(entry)
        else:
            reasons = []
            if not cls["has_meep_import"]: reasons.append("no_meep_import")
            if not cls["has_simulation"]: reasons.append("no_simulation")
            if not cls["has_sim_run"]: reasons.append("no_sim_run")
            if cls["external_dependencies"]: reasons.append("external_dep")
            if cls["security_risk"]: reasons.append("security_risk")
            not_runnable.append({**entry, "reason": ",".join(reasons) or "unknown"})

    return {
        "total": total,
        "runnable_count": len(runnable),
        "not_runnable_count": len(not_runnable),
        "runnable": runnable,
        "not_runnable_summary": [
            {"id": x["id"], "title": x.get("title",""), "reason": x.get("reason","")}
            for x in not_runnable
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────

def run_audit() -> dict:
    conn = sqlite3.connect(str(DB_PATH))

    print("=" * 60)
    print("Phase 1: DB 데이터 감사 시작")
    print("=" * 60)

    print("\n[1/2] sim_errors (github_issue + github_structured) 감사 중...")
    sim_result = audit_sim_errors(conn)
    print(f"  전체: {sim_result['total']}건")
    print(f"  독립 실행 가능: {sim_result['runnable_count']}건")
    print(f"  코드 있음(의존성 문제 등): {sim_result['has_code_count']}건")
    print(f"  코드 없음: {sim_result['no_code_count']}건")

    print("\n[2/2] examples 감사 중...")
    ex_result = audit_examples(conn)
    print(f"  전체: {ex_result['total']}건")
    print(f"  독립 실행 가능: {ex_result['runnable_count']}건")
    print(f"  실행 불가: {ex_result['not_runnable_count']}건")

    conn.close()

    report = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "sim_errors": {
            "total": sim_result["total"],
            "runnable_count": sim_result["runnable_count"],
            "has_code_count": sim_result["has_code_count"],
            "no_code_count": sim_result["no_code_count"],
            "runnable_ids": [x["id"] for x in sim_result["runnable"]],
            "runnable_items": sim_result["runnable"],
        },
        "examples": {
            "total": ex_result["total"],
            "runnable_count": ex_result["runnable_count"],
            "not_runnable_count": ex_result["not_runnable_count"],
            "runnable_items": ex_result["runnable"],
            "not_runnable_summary": ex_result["not_runnable_summary"],
        },
    }

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\n✅ 감사 완료! 리포트 저장: {REPORT_PATH}")
    return report


if __name__ == "__main__":
    run_audit()
