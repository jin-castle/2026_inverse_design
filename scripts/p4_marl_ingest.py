#!/usr/bin/env python3
"""
P4: MARL → KB 자동 ingest 루틴
marl_orchestrator.py run() 완료 후 결과를 /api/ingest/sim_error 로 자동 POST.
"""
import os, json, requests, hashlib, sqlite3
from pathlib import Path
from datetime import datetime

KB_API  = "http://localhost:8765"
DB_PATH = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge.db")

def _load_ingest_key() -> str:
    env = Path("/mnt/c/Users/user/projects/meep-kb/.env")
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("INGEST_API_KEY") and "=" in line:
                return line.split("=",1)[1].strip().strip('"').strip("'")
    return os.environ.get("INGEST_API_KEY","")

INGEST_KEY = _load_ingest_key()

def ingest_fix(
    error_type: str,
    error_message: str,
    original_code: str,
    fixed_code: str,
    fix_description: str,
    root_cause: str,
    fix_worked: int,
    project_id: str = "",
    pattern_name: str = "",
    meep_version: str = "1.31.0",
    context: str = "",
    fix_keywords: list = None,
    verification_result: dict = None,
) -> dict:
    """
    MARL run() 완료 후 fix 결과를 KB에 저장.
    fix_worked=1 이면 verification_criteria 도 함께 저장.
    """
    payload = {
        "error_type":       error_type[:100],
        "error_message":    error_message[:2000],
        "original_code":    original_code[:5000],
        "fixed_code":       fixed_code[:5000],
        "fix_description":  fix_description[:1000],
        "root_cause":       root_cause[:300],
        "fix_worked":       fix_worked,
        "project_id":       project_id,
        "pattern_name":     pattern_name,
        "meep_version":     meep_version,
        "context":          context[:500],
        "fix_keywords":     json.dumps(fix_keywords or [], ensure_ascii=False),
        "source":           "marl_auto",
    }
    headers = {"Content-Type":"application/json"}
    if INGEST_KEY:
        headers["X-Ingest-Key"] = INGEST_KEY

    try:
        r = requests.post(f"{KB_API}/api/ingest/sim_error",
                          json=payload, headers=headers, timeout=10)
        result = r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    # verification_criteria 추가 저장 (직접 DB 쓰기)
    if fix_worked == 1 and verification_result and result.get("ok"):
        row_id = result.get("id")
        if row_id:
            try:
                conn = sqlite3.connect(str(DB_PATH), timeout=10)
                conn.execute(
                    "UPDATE sim_errors SET symptom_numerical=? WHERE id=?",
                    (json.dumps(verification_result, ensure_ascii=False), row_id)
                )
                conn.commit()
                conn.close()
            except:
                pass

    return result


def ingest_from_marl_result(marl_result: dict) -> list:
    """
    MARLOrchestrator.run() 반환값에서 fix_history 를 추출해 KB 일괄 저장.

    marl_result 구조:
        status: success|fixed|failed|blocked
        fix_history: [{attempt, error, kb_suggestion, original_code, fixed_code, fix_description, fix_worked}]
        sim_id: str
        project_id: str (optional)
    """
    results = []
    fix_history = marl_result.get("fix_history", [])
    project_id  = marl_result.get("project_id", "")
    sim_id      = marl_result.get("sim_id", "")

    for attempt in fix_history:
        error_raw      = attempt.get("error", "")
        error_type     = _guess_error_type(error_raw)
        fix_worked_val = 1 if attempt.get("fix_worked", False) else 0

        r = ingest_fix(
            error_type=error_type,
            error_message=error_raw,
            original_code=attempt.get("original_code",""),
            fixed_code=attempt.get("fixed_code",""),
            fix_description=attempt.get("fix_description",""),
            root_cause=attempt.get("kb_suggestion",""),
            fix_worked=fix_worked_val,
            project_id=project_id,
            pattern_name=sim_id,
            context=f"attempt={attempt.get('attempt',0)}",
        )
        results.append({"attempt": attempt.get("attempt"), "ingest": r})
        print(f"  [ingest] attempt={attempt.get('attempt')} -> ok={r.get('ok')} id={r.get('id')}")

    return results


def _guess_error_type(error_msg: str) -> str:
    """에러 메시지에서 타입 추론"""
    msg = (error_msg or "").lower()
    if "typeerror" in msg:       return "TypeError"
    if "attributeerror" in msg:  return "AttributeError"
    if "valueerror" in msg:      return "ValueError"
    if "importerror" in msg:     return "ImportError"
    if "mpi" in msg:             return "MPIError"
    if "nan" in msg:             return "NumericalDivergence"
    if "diverge" in msg:         return "Divergence"
    if "eigenmode" in msg:       return "EigenmodeError"
    if "pml" in msg:             return "PMLError"
    return "UnknownError"


# ── CLI 테스트 용 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== MARL ingest 단위 테스트 ===")
    fake_result = {
        "status": "fixed",
        "sim_id": "TEST-ingest-001",
        "project_id": "PROJ-TEST",
        "fix_history": [
            {
                "attempt": 1,
                "error": "TypeError: DiffractedPlanewave() got an unexpected keyword argument 'theta'",
                "kb_suggestion": "DiffractedPlanewave의 경사각은 'angle' 파라미터로 전달",
                "original_code": "src=mp.DiffractedPlanewave(theta=30)",
                "fixed_code":    "src=mp.DiffractedPlanewave(angle=30)",
                "fix_description":"theta -> angle 파라미터명 수정",
                "fix_worked": True,
            }
        ]
    }
    results = ingest_from_marl_result(fake_result)
    for r in results:
        print(json.dumps(r, ensure_ascii=False, indent=2))
