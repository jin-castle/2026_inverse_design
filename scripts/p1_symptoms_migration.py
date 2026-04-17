#!/usr/bin/env python3
"""
P1: MEEP-KB symptoms 3분할 + verification_criteria + diagnostic_snippet 마이그레이션
모델: claude-sonnet-4-5

수정사항:
- None 반환 시 크래시 방어
- API timeout 30초 + retry 3회
- 진행 상황 로그 파일 저장 (재개 가능)
- 각 LLM 호출 결과 즉시 커밋 (중단 재개 안전)
"""

import sqlite3, json, os, time, shutil, signal, sys
from pathlib import Path
from datetime import datetime

DB_PATH    = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge.db")
LOG_PATH   = Path("/mnt/c/Users/user/projects/meep-kb/scripts/migration_progress.log")
BACKUP_DIR = Path("/mnt/c/Users/user/projects/meep-kb/db")

# ── API 키 로드 ───────────────────────────────────────────────────────────────
def load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        env_file = Path("/mnt/c/Users/user/projects/meep-kb/.env")
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY") and "=" in line:
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY 없음")
    return key

import anthropic
_client = anthropic.Anthropic(api_key=load_api_key())
MODEL = "claude-sonnet-4-5"

# ── Graceful shutdown ─────────────────────────────────────────────────────────
_shutdown = False
def _sig_handler(sig, frame):
    global _shutdown
    print("\n[interrupt] 현재 레코드 완료 후 종료합니다...")
    _shutdown = True
signal.signal(signal.SIGINT,  _sig_handler)
signal.signal(signal.SIGTERM, _sig_handler)

# ── LLM 호출 (timeout + retry) ───────────────────────────────────────────────
def llm_call(prompt: str, max_tokens: int = 500, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            msg = _client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                timeout=30.0,          # 30초 timeout
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except anthropic.APITimeoutError:
            print(f"  [timeout] attempt {attempt+1}/{retries}", flush=True)
            time.sleep(2 ** attempt)
        except anthropic.RateLimitError:
            print(f"  [rate-limit] 대기 60초...", flush=True)
            time.sleep(60)
        except Exception as e:
            print(f"  [llm-err] {type(e).__name__}: {str(e)[:80]}", flush=True)
            time.sleep(2 ** attempt)
    return None

# ── JSON 파싱 (robust) ────────────────────────────────────────────────────────
def parse_json(text: str | None) -> dict:
    if not text:
        return {}
    # 마크다운 코드블록 제거
    if "```" in text:
        parts = text.split("```")
        for i in range(1, len(parts), 2):
            candidate = parts[i]
            if candidate.startswith("json"):
                candidate = candidate[4:]
            try:
                return json.loads(candidate.strip())
            except:
                pass
    # 중괄호 범위 추출
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end+1])
        except:
            pass
    return {}

# ── 진행 로그 ─────────────────────────────────────────────────────────────────
def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ── 백업 ─────────────────────────────────────────────────────────────────────
def backup_db():
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    dst = BACKUP_DIR / f"knowledge_backup_pre_symptoms_{ts}.db"
    shutil.copy2(DB_PATH, dst)
    log(f"[backup] → {dst.name}")

# ── 컬럼 추가 ─────────────────────────────────────────────────────────────────
COLUMNS = [
    ("sim_errors_v2", "symptom_numerical"),
    ("sim_errors_v2", "symptom_behavioral"),
    ("sim_errors_v2", "symptom_error_pattern"),
    ("sim_errors_v2", "verification_criteria"),
    ("sim_errors_v2", "diagnostic_snippet"),
    ("sim_errors",    "symptom_numerical"),
    ("sim_errors",    "symptom_behavioral"),
    ("sim_errors",    "symptom_error_pattern"),
    ("errors",        "symptom_numerical"),
    ("errors",        "symptom_behavioral"),
    ("errors",        "symptom_error_pattern"),
]

def add_columns(conn):
    for table, col in COLUMNS:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT NULL")
            log(f"[schema] {table}.{col} 추가")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                pass  # 이미 존재
            else:
                log(f"[schema] ERROR {table}.{col}: {e}")
    conn.commit()

# ── 프롬프트 ──────────────────────────────────────────────────────────────────
CLASSIFY_PROMPT = """\
MEEP FDTD 시뮬레이션 에러 케이스를 3가지 symptom 유형으로 분류하세요.

에러 메시지: {error_msg}
원인: {cause}
해결책: {solution}

JSON만 출력 (다른 텍스트 없이):
{{
  "symptom_error_pattern": "Python/MEEP 예외 메시지 패턴 (없으면 null)",
  "symptom_numerical": "정량 패턴: T>1.0, NaN, gradient_ratio≈2, T=0 등 (없으면 null)",
  "symptom_behavioral": "정성 패턴: 수렴 안함, 체커보드, 발산 등 (없으면 null)"
}}"""

VERIFY_PROMPT = """\
MEEP 에러가 수정된 케이스입니다. 수정 성공을 판정할 수치 기준을 JSON으로 추출하세요.

에러 타입: {error_type}
수정 설명: {fix_description}
symptom: {symptom}

JSON만 출력:
{{
  "T_min": null,
  "T_max": null,
  "R_max": null,
  "TR_sum_min": null,
  "TR_sum_max": null,
  "FOM_threshold": null,
  "gradient_ratio_target": null,
  "no_exception": true,
  "description": "한국어로 검증 기준 한 문장"
}}
모르는 필드는 null로 두세요."""

DIAG_PROMPT = """\
MEEP 시뮬레이션 에러 케이스입니다.
이 에러가 현재 코드에도 존재하는지 확인하는 Python 진단 코드를 작성하세요.

에러 타입: {error_type}
에러 메시지: {error_msg}
원인: {cause}

실행 가능한 Python 코드 3~8줄만 작성하세요. 주석 포함.
마크다운 없이 코드만 출력하세요."""

# ── 분류 함수들 ───────────────────────────────────────────────────────────────
def classify_symptoms(error_msg: str, cause: str, solution: str) -> dict:
    text = llm_call(CLASSIFY_PROMPT.format(
        error_msg=(error_msg or "")[:500],
        cause=(cause or "")[:300],
        solution=(solution or "")[:300],
    ))
    result = parse_json(text)
    return {
        "symptom_error_pattern": result.get("symptom_error_pattern"),
        "symptom_numerical":     result.get("symptom_numerical"),
        "symptom_behavioral":    result.get("symptom_behavioral"),
    }

def generate_verification(error_type: str, fix_description: str, symptom: str) -> dict:
    text = llm_call(VERIFY_PROMPT.format(
        error_type=(error_type or "")[:50],
        fix_description=(fix_description or "")[:400],
        symptom=(symptom or "")[:200],
    ))
    result = parse_json(text)
    if not result:
        result = {"description": "수동 확인 필요", "no_exception": True}
    return result

def generate_diagnostic(error_type: str, error_msg: str, cause: str) -> str:
    text = llm_call(DIAG_PROMPT.format(
        error_type=(error_type or "unknown")[:50],
        error_msg=(error_msg or "")[:300],
        cause=(cause or "")[:200],
    ), max_tokens=300)
    if not text:
        return f"# 자동 생성 실패\n# error_type: {error_type}"
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            code = parts[1]
            if code.startswith("python"):
                code = code[6:]
            return code.strip()
    return text

# ── 배치 처리: sim_errors_v2 ─────────────────────────────────────────────────
def migrate_sim_errors_v2(conn, max_rows=None, delay=0.5):
    rows = conn.execute("""
        SELECT id, error_type, error_message, symptom,
               physics_cause, code_cause, fix_description, fixed_code, fix_worked
        FROM sim_errors_v2
        WHERE symptom_numerical IS NULL
        ORDER BY fix_worked DESC, id ASC
    """).fetchall()
    if max_rows:
        rows = rows[:max_rows]

    total = len(rows)
    log(f"\n[sim_errors_v2] {total}건 처리 시작 (model={MODEL})")
    ok = fail = skip = 0

    for i, row in enumerate(rows, 1):
        if _shutdown:
            log(f"[interrupt] {i-1}/{total} 처리 후 중단")
            break

        id_, etype, emsg, symptom, phys, code_c, fix_desc, fixed_code, fix_worked = row
        t0 = time.time()
        print(f"  [{i:3d}/{total}] id={id_:4d} {(etype or '')[:20]:20s}", end=" ", flush=True)

        # 1) symptoms 분류
        cause_text = f"{phys or ''} {code_c or ''}".strip()
        s = classify_symptoms(emsg or "", cause_text, fix_desc or "")

        fields = {
            "symptom_error_pattern": s["symptom_error_pattern"],
            "symptom_numerical":     s["symptom_numerical"],
            "symptom_behavioral":    s["symptom_behavioral"],
        }

        # 2) fix_worked=1 → verification + diagnostic
        if fix_worked == 1:
            v = generate_verification(etype or "", fix_desc or "", symptom or "")
            fields["verification_criteria"] = json.dumps(v, ensure_ascii=False)
            d = generate_diagnostic(etype or "", emsg or "", cause_text)
            fields["diagnostic_snippet"] = d

        # 3) DB 저장
        set_sql = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [id_]
        try:
            conn.execute(f"UPDATE sim_errors_v2 SET {set_sql} WHERE id=?", vals)
            conn.commit()
            elapsed = time.time() - t0
            num_preview = (s["symptom_numerical"] or "")[:25]
            print(f"✓ {elapsed:.1f}s  num={num_preview!r}")
            ok += 1
        except Exception as e:
            print(f"✗ DB: {e}")
            fail += 1

        time.sleep(delay)

    log(f"[sim_errors_v2] 완료: ok={ok} fail={fail} skip={skip}/{total}")
    return ok, fail

# ── 배치 처리: sim_errors ─────────────────────────────────────────────────────
def migrate_sim_errors(conn, max_rows=None, delay=0.3):
    rows = conn.execute("""
        SELECT id, error_type, error_message, root_cause, fix_description
        FROM sim_errors
        WHERE symptom_numerical IS NULL
        ORDER BY fix_worked DESC, id ASC
    """).fetchall()
    if max_rows:
        rows = rows[:max_rows]

    total = len(rows)
    log(f"\n[sim_errors] {total}건 처리 시작")
    ok = fail = 0

    for i, row in enumerate(rows, 1):
        if _shutdown:
            log(f"[interrupt] {i-1}/{total} 처리 후 중단")
            break

        id_, etype, emsg, root_cause, fix_desc = row
        print(f"  [{i:3d}/{total}] id={id_:4d} {(etype or '')[:20]:20s}", end=" ", flush=True)

        s = classify_symptoms(emsg or "", root_cause or "", fix_desc or "")
        try:
            conn.execute("""
                UPDATE sim_errors SET
                  symptom_error_pattern=?, symptom_numerical=?, symptom_behavioral=?
                WHERE id=?
            """, (s["symptom_error_pattern"], s["symptom_numerical"], s["symptom_behavioral"], id_))
            conn.commit()
            print(f"✓ num={( s['symptom_numerical'] or '')[:25]!r}")
            ok += 1
        except Exception as e:
            print(f"✗ DB: {e}")
            fail += 1

        time.sleep(delay)

    log(f"[sim_errors] 완료: ok={ok} fail={fail}/{total}")
    return ok, fail

# ── 배치 처리: errors ─────────────────────────────────────────────────────────
def migrate_errors(conn, max_rows=None, delay=0.3):
    rows = conn.execute("""
        SELECT id, error_msg, cause, solution
        FROM errors
        WHERE symptom_numerical IS NULL
        ORDER BY verified DESC, id ASC
    """).fetchall()
    if max_rows:
        rows = rows[:max_rows]

    total = len(rows)
    log(f"\n[errors] {total}건 처리 시작")
    ok = fail = 0

    for i, row in enumerate(rows, 1):
        if _shutdown:
            log(f"[interrupt] {i-1}/{total} 처리 후 중단")
            break

        id_, emsg, cause, solution = row
        print(f"  [{i:3d}/{total}] id={id_:4d}", end=" ", flush=True)

        s = classify_symptoms(emsg or "", cause or "", solution or "")
        try:
            conn.execute("""
                UPDATE errors SET
                  symptom_error_pattern=?, symptom_numerical=?, symptom_behavioral=?
                WHERE id=?
            """, (s["symptom_error_pattern"], s["symptom_numerical"], s["symptom_behavioral"], id_))
            conn.commit()
            print(f"✓ num={( s['symptom_numerical'] or '')[:25]!r}")
            ok += 1
        except Exception as e:
            print(f"✗ DB: {e}")
            fail += 1

        time.sleep(delay)

    log(f"[errors] 완료: ok={ok} fail={fail}/{total}")
    return ok, fail

# ── 검증 리포트 ───────────────────────────────────────────────────────────────
def verify_migration(conn):
    log("\n=== 마이그레이션 채움률 검증 ===")
    for table in ["sim_errors_v2", "sim_errors", "errors"]:
        try:
            total   = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            n_num   = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE symptom_numerical IS NOT NULL").fetchone()[0]
            n_beh   = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE symptom_behavioral IS NOT NULL").fetchone()[0]
            n_err   = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE symptom_error_pattern IS NOT NULL").fetchone()[0]
            log(f"[{table}] total={total}  numerical={n_num}({n_num/total*100:.0f}%)  "
                f"behavioral={n_beh}({n_beh/total*100:.0f}%)  error_pattern={n_err}({n_err/total*100:.0f}%)")
        except Exception as e:
            log(f"[{table}] 오류: {e}")

    try:
        total_fixed = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=1").fetchone()[0]
        n_v = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE verification_criteria IS NOT NULL").fetchone()[0]
        n_d = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE diagnostic_snippet IS NOT NULL").fetchone()[0]
        log(f"[sim_errors_v2] fix_worked=1: {total_fixed}건  "
            f"verification={n_v}({n_v/max(total_fixed,1)*100:.0f}%)  "
            f"diagnostic={n_d}({n_d/max(total_fixed,1)*100:.0f}%)")
    except Exception as e:
        log(f"[verification check] 오류: {e}")

# ── 메인 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--target",    choices=["all","v2","sim","errors"], default="v2")
    p.add_argument("--max-rows",  type=int, default=None)
    p.add_argument("--no-backup", action="store_true")
    p.add_argument("--delay",     type=float, default=0.5)
    p.add_argument("--verify-only", action="store_true")
    args = p.parse_args()

    conn = sqlite3.connect(str(DB_PATH), timeout=30)

    if args.verify_only:
        verify_migration(conn)
        conn.close()
        sys.exit(0)

    if not args.no_backup:
        backup_db()

    add_columns(conn)

    t_start = time.time()
    if args.target in ("all", "v2"):
        migrate_sim_errors_v2(conn, args.max_rows, args.delay)
    if args.target in ("all", "sim") and not _shutdown:
        migrate_sim_errors(conn, args.max_rows, args.delay)
    if args.target in ("all", "errors") and not _shutdown:
        migrate_errors(conn, args.max_rows, args.delay)

    verify_migration(conn)
    conn.close()
    elapsed = time.time() - t_start
    log(f"\n[완료] 총 소요: {elapsed:.0f}초")
