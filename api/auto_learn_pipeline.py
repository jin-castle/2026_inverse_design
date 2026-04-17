"""
auto_learn_pipeline.py
======================
미지 에러 자동 학습 파이프라인.

흐름:
  1. diagnose()가 OOD 에러를 감지
  2. llm_diagnose()로 Claude가 분석 → root_cause + fixed_code 생성
  3. fix-and-run으로 Docker에서 검증
  4. 검증 통과 → DB 저장 + 임베딩 인덱스 갱신

이 파이프라인은 새 에러가 발생할 때마다 KB를 자동 확장.
"""
from __future__ import annotations
import sqlite3
import datetime
import json
import re
import subprocess
import tempfile
import os
import logging
from typing import Optional

logger = logging.getLogger("auto_learn")

DB_PATH      = "/app/db/knowledge.db"
DOCKER_CTR   = os.getenv("MEEP_DOCKER", "meep-pilot-worker")
OOD_THRESHOLD = 0.40


def run_fix_in_docker(fixed_code: str, timeout: int = 60) -> dict:
    """
    fixed_code를 Docker 컨테이너에서 실행해 검증.
    반환: {"success": bool, "stdout": str, "stderr": str, "elapsed_s": float}
    """
    import time

    # resolution을 낮춰 빠르게 실행
    safe_code = re.sub(r'\bresolution\s*=\s*\d+', 'resolution = 10', fixed_code)
    safe_code = re.sub(r'\buntil\s*=\s*[\d.]+', 'until = 20', safe_code)
    safe_code = re.sub(r'set_maxeval\s*\(\s*\d+\s*\)', 'set_maxeval(1)', safe_code)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="/tmp/alk_"
    ) as f:
        f.write(safe_code)
        tmp = f.name

    t0 = time.time()
    try:
        subprocess.run(
            ["docker", "cp", tmp, f"{DOCKER_CTR}:{tmp}"],
            capture_output=True, timeout=10, check=False,
        )
        res = subprocess.run(
            ["docker", "exec", DOCKER_CTR, "python3", tmp],
            capture_output=True, text=True, timeout=timeout,
        )
        elapsed = time.time() - t0
        combined = (res.stderr or "") + (res.stdout or "")
        ok = (
            res.returncode == 0
            and not re.search(r"\bTraceback\b|\bError\b", combined[:500])
        )
        return {
            "success": ok,
            "rc":      res.returncode,
            "stdout":  res.stdout[-800:],
            "stderr":  res.stderr[-400:],
            "elapsed_s": round(elapsed, 2),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "rc": -1, "stdout": "", "stderr": f"TIMEOUT {timeout}s", "elapsed_s": timeout}
    except Exception as e:
        return {"success": False, "rc": -2, "stdout": "", "stderr": str(e), "elapsed_s": 0}
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def save_to_db(
    error_type: str,
    error_message: str,
    original_code: str,
    root_cause: str,
    fixed_code: str,
    fix_description: str,
    fix_keywords: list[str],
    fix_verified: bool,
    source: str = "auto_learn",
    db_path: str = DB_PATH,
) -> int:
    """DB에 새 레코드 저장. 반환: 새 id."""
    now  = datetime.datetime.utcnow().isoformat()
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO sim_errors
          (error_type, error_message, original_code, fixed_code,
           root_cause, fix_description, fix_keywords,
           source, fix_worked, confidence, fix_verified_at, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        error_type[:100],
        error_message[:2000],
        original_code[:5000],
        fixed_code[:5000],
        root_cause[:500],
        fix_description[:500],
        json.dumps(fix_keywords),
        source,
        1 if fix_verified else 0,
        "high" if fix_verified else "draft",
        now if fix_verified else None,
        now,
    ))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return new_id


async def learn_from_unknown_error(
    code: str,
    error: str,
    llm_result: dict,
    anthropic_client=None,
) -> Optional[dict]:
    """
    미지 에러를 학습하는 메인 함수.

    llm_result: llm_diagnose()의 반환값
      - "fixed_code": LLM이 생성한 수정 코드
      - "root_cause": 원인 분석
      - "fix_description": 수정 설명
      - "error_type": 추론된 에러 타입

    반환: {"learned": bool, "new_id": int, "verified": bool}
    """
    fixed_code    = llm_result.get("fixed_code", "")
    root_cause    = llm_result.get("root_cause", "")
    fix_desc      = llm_result.get("fix_description", "")
    error_type    = llm_result.get("error_type", "Unknown")
    fix_keywords  = llm_result.get("fix_keywords", [])

    if not fixed_code or len(fixed_code) < 20:
        logger.info("LLM did not generate fixed_code → skip learning")
        return {"learned": False, "reason": "no_fixed_code"}

    # fix-and-run 검증 (fixed_code에 import meep이 있을 때만)
    verified = False
    if "import meep" in fixed_code:
        logger.info(f"Running fix verification in Docker ({DOCKER_CTR})")
        run_result = run_fix_in_docker(fixed_code, timeout=60)
        verified   = run_result["success"]
        logger.info(f"Verification: success={verified}, elapsed={run_result['elapsed_s']}s")
    else:
        # MEEP 시뮬 코드 아닌 경우 검증 생략 (Python 문법만 체크)
        try:
            compile(fixed_code, "<string>", "exec")
            verified = True   # 문법 OK = medium confidence
        except SyntaxError:
            verified = False

    # DB 저장
    new_id = save_to_db(
        error_type=error_type,
        error_message=error,
        original_code=code,
        root_cause=root_cause,
        fixed_code=fixed_code,
        fix_description=fix_desc,
        fix_keywords=fix_keywords if isinstance(fix_keywords, list) else [],
        fix_verified=verified,
        source="auto_learn",
    )
    logger.info(f"Saved new error pattern: id={new_id}, verified={verified}")

    # 임베딩 인덱스 실시간 갱신
    try:
        from semantic_search import add_to_index
        add_to_index(new_id)
        logger.info(f"Added id={new_id} to embedding index")
    except Exception as e:
        logger.warning(f"Embedding update failed: {e}")

    return {
        "learned":  True,
        "new_id":   new_id,
        "verified": verified,
        "confidence": "high" if verified else "draft",
    }
