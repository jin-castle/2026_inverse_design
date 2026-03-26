# -*- coding: utf-8 -*-
"""
migrate_to_v2.py — sim_errors 구 데이터(error_injector + marl_auto) → sim_errors_v2 마이그레이션

Usage:
    python -X utf8 tools/migrate_to_v2.py [--dry-run] [--no-enrich]

대상: source IN ('error_injector', 'marl_auto') AND fix_worked=1 (53건)
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv

load_dotenv(str(Path(__file__).parent.parent / ".env"))

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"


# ────────────────────────────────────────────────────────────
# Layer 1: 실행 컨텍스트 추론
# ────────────────────────────────────────────────────────────

def infer_run_mode(code: str) -> str:
    """forward | adjoint | normalization | eigenmode_solve | harminv"""
    code_lower = (code or "").lower()
    if "adjoint" in code_lower or "optimizationproblem" in code_lower or "meep_adjoint" in code_lower:
        return "adjoint"
    if "harminv" in code_lower:
        return "harminv"
    if "eigenmode" in code_lower or "eig_band" in code_lower or "eig_parity" in code_lower:
        return "eigenmode_solve"
    if "norm" in code_lower and ("flux" in code_lower or "monitor" in code_lower):
        return "normalization"
    return "forward"


# ────────────────────────────────────────────────────────────
# Layer 2: 물리 파라미터 추론
# ────────────────────────────────────────────────────────────

def extract_physics_context(code: str) -> dict:
    """resolution, pml_thickness, fcen 등 주요 파라미터 추출"""
    result = {}
    if not code:
        return result

    # resolution
    m = re.search(r'resolution\s*=\s*(\d+)', code)
    if m:
        result["resolution"] = int(m.group(1))

    # pml_thickness: mp.PML(thickness) or boundary_layers=[mp.PML(X)]
    m = re.search(r'mp\.PML\s*\(\s*([0-9.]+)', code)
    if m:
        result["pml_thickness"] = float(m.group(1))

    # fcen (center frequency)
    m = re.search(r'fcen\s*=\s*([0-9.e+-]+)', code)
    if m:
        try:
            result["fcen"] = float(m.group(1))
        except ValueError:
            pass

    return result


def infer_dim(code: str) -> int:
    """2 or 3 dimensions"""
    code_lower = (code or "").lower()
    # cylindrical coordinates → 2D equivalent
    if "cylindrical" in code_lower:
        return 2
    # explicit mp.CYLINDRICAL or dimensions=
    m = re.search(r'dimensions\s*=\s*(\d+)', code or "")
    if m:
        return int(m.group(1))
    # 3D 힌트
    if "mp.z" in code_lower or "z_size" in code_lower or re.search(r"sz\s*=", code or ""):
        return 3
    return 2


def infer_device_type(code: str) -> str:
    """waveguide | beamsplitter | grating | ring_resonator | mzi | general"""
    code_lower = (code or "").lower()
    if "beamsplitter" in code_lower or "beam_splitter" in code_lower or "splitter" in code_lower:
        return "beamsplitter"
    if "ring" in code_lower or "resonator" in code_lower:
        return "ring_resonator"
    if "grating" in code_lower:
        return "grating"
    if "mzi" in code_lower or "mach" in code_lower or "interferometer" in code_lower:
        return "mzi"
    if "waveguide" in code_lower or "wg" in code_lower:
        return "waveguide"
    return "general"


def extract_cell_size(code: str) -> str:
    """셀 크기 JSON: {"x": sx, "y": sy, "z": sz}"""
    if not code:
        return ""
    cell = {}
    # sx, sy, sz
    for dim_name in ("sx", "sy", "sz"):
        m = re.search(rf'{dim_name}\s*=\s*([0-9.e+\-]+)', code)
        if m:
            try:
                cell[dim_name[1]] = float(m.group(1))
            except ValueError:
                pass
    # mp.Vector3(x, y, z) in cell_size=
    m = re.search(r'cell_size\s*=\s*mp\.Vector3\s*\(\s*([0-9.e+\-]+)\s*,\s*([0-9.e+\-]+)(?:\s*,\s*([0-9.e+\-]+))?\s*\)', code)
    if m:
        try:
            cell = {"x": float(m.group(1)), "y": float(m.group(2))}
            if m.group(3):
                cell["z"] = float(m.group(3))
        except ValueError:
            pass
    return json.dumps(cell) if cell else ""


# ────────────────────────────────────────────────────────────
# Layer 3: 에러 분류
# ────────────────────────────────────────────────────────────

def infer_error_class(error_type: str, error_message: str) -> str:
    """code_error | physics_error | numerical_error | config_error"""
    et = (error_type or "").lower()
    msg = (error_message or "").lower()

    # numerical errors
    if any(k in et for k in ["diverge", "nan", "overflow", "harminv"]):
        return "numerical_error"
    if "nan" in msg or "diverge" in msg or "overflow" in msg:
        return "numerical_error"

    # physics errors
    if any(k in et for k in ["eigenmode", "pml", "t>100", "eig"]):
        return "physics_error"
    if "t>100" in msg or "t > 100" in msg or "transmission" in msg:
        return "physics_error"
    if "pml" in msg or "eigensource" in msg:
        return "physics_error"

    # config errors
    if any(k in et for k in ["attribute", "type", "value", "key", "import", "module"]):
        return "code_error"
    if "attributeerror" in msg or "typeerror" in msg or "valueerror" in msg:
        return "code_error"

    # MPI / adjoint
    if any(k in et for k in ["mpi", "deadlock", "adjoint"]):
        return "config_error"

    return "code_error"


def infer_symptom(error_message: str, error_type: str) -> str:
    """T>100% | NaN | T=0 | diverged | wrong_mode | crashed | other"""
    msg = (error_message or "").lower()
    et = (error_type or "").lower()

    if "t>100" in msg or "t > 100" in msg or "100%" in msg:
        return "T>100%"
    if "nan" in msg or "nan" in et:
        return "NaN"
    if "t=0" in msg or "zero" in msg and "flux" in msg:
        return "T=0"
    if "diverge" in msg or "diverge" in et or "overflow" in msg:
        return "diverged"
    if "wrong_mode" in et or "wrong mode" in msg or "eig_band" in msg:
        return "wrong_mode"
    if "deadlock" in msg or "deadlock" in et:
        return "deadlock"
    if "attributeerror" in msg or "typeerror" in msg or "valueerror" in msg:
        return "crashed"
    if "assertionerror" in msg or "runtimeerror" in msg:
        return "crashed"
    return "other"


# ────────────────────────────────────────────────────────────
# Layer 4: 원인 코드 스니펫 추출
# ────────────────────────────────────────────────────────────

def extract_trigger_code(code: str, error_message: str) -> str:
    """에러와 관련된 코드 스니펫 (최대 10줄)"""
    if not code:
        return ""

    lines = code.split("\n")
    msg = (error_message or "").lower()

    # traceback에서 line 번호 추출
    line_m = re.search(r'line (\d+)', error_message or "")
    if line_m:
        ln = int(line_m.group(1)) - 1  # 0-indexed
        start = max(0, ln - 2)
        end = min(len(lines), ln + 5)
        return "\n".join(lines[start:end])

    # 키워드 기반 관련 줄 찾기
    keywords = []
    if "pml" in msg:
        keywords = ["PML", "boundary_layer"]
    elif "eigenmode" in msg or "eigensource" in msg:
        keywords = ["EigenmodeSource", "eig_band", "eig_parity"]
    elif "adjoint" in msg or "adjoint" in (error_message or "").lower():
        keywords = ["adjoint", "OptimizationProblem", "reset_meep"]
    elif "harminv" in msg:
        keywords = ["Harminv", "harminv"]

    if keywords:
        for i, line in enumerate(lines):
            if any(kw in line for kw in keywords):
                start = max(0, i - 1)
                end = min(len(lines), i + 6)
                return "\n".join(lines[start:end])

    # 기본: 마지막 의미 있는 코드 10줄
    non_empty = [l for l in lines if l.strip() and not l.strip().startswith("#")]
    return "\n".join(non_empty[-10:]) if non_empty else ""


# ────────────────────────────────────────────────────────────
# Layer 5: Fix 분류
# ────────────────────────────────────────────────────────────

def infer_fix_type(error_type: str, fix_description: str) -> str:
    """code_only | physics_understanding | parameter_tune | structural"""
    et = (error_type or "").lower()
    fd = (fix_description or "").lower()

    if any(k in et for k in ["pml", "eigenmode", "eig", "diverge", "adjoint"]):
        return "physics_understanding"
    if "resolution" in fd or "thickness" in fd or "pml" in fd or "parameter" in fd:
        return "parameter_tune"
    if "refactor" in fd or "restructur" in fd or "rewrite" in fd:
        return "structural"
    return "code_only"


# ────────────────────────────────────────────────────────────
# Diff 생성
# ────────────────────────────────────────────────────────────

def make_diff(original: str, fixed: str) -> str:
    """unified diff 생성"""
    if not original or not fixed:
        return ""
    orig_lines = (original or "").splitlines(keepends=True)
    fixed_lines = (fixed or "").splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines, fixed_lines,
        fromfile="original.py", tofile="fixed.py",
        lineterm=""
    )
    return "".join(diff)[:5000]  # 최대 5000자


# ────────────────────────────────────────────────────────────
# 메인 마이그레이션
# ────────────────────────────────────────────────────────────

def migrate(dry_run: bool = False) -> dict:
    """
    sim_errors (error_injector + marl_auto, fix_worked=1) → sim_errors_v2 마이그레이션

    Returns: {total, inserted, skipped_dup, failed}
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # 소스 레코드 조회
    rows = conn.execute(
        """
        SELECT * FROM sim_errors
        WHERE source IN ('error_injector', 'marl_auto')
          AND fix_worked = 1
        ORDER BY id
        """
    ).fetchall()

    print(f"마이그레이션 대상: {len(rows)}건")

    inserted = 0
    skipped_dup = 0
    failed = 0
    results = []

    for row in rows:
        row = dict(row)
        original_code = row.get("original_code") or ""
        fixed_code = row.get("fixed_code") or ""
        error_type = row.get("error_type") or ""
        error_message = row.get("error_message") or ""

        # code_hash (중복 방지)
        code_hash = hashlib.sha256(original_code.encode()).hexdigest()

        # 이미 v2에 있으면 skip
        existing = conn.execute(
            "SELECT id FROM sim_errors_v2 WHERE code_hash = ?", (code_hash,)
        ).fetchone()
        if existing:
            print(f"  [SKIP-DUP] id={row['id']}, source={row['source']}, hash={code_hash[:12]}...")
            skipped_dup += 1
            continue

        # physics context 추출
        phys_ctx = extract_physics_context(original_code)
        wavelength_um = None
        if phys_ctx.get("fcen"):
            try:
                wavelength_um = round(1.0 / phys_ctx["fcen"], 4)
            except ZeroDivisionError:
                pass

        # 루트 원인 체인 초기값
        root_cause_chain = json.dumps([
            {"level": 1, "cause": error_message or ""},
            {"level": 2, "cause": row.get("root_cause") or ""},
        ], ensure_ascii=False)

        v2_record = {
            # Layer 1
            "run_mode": infer_run_mode(original_code),
            "run_stage": "running",
            "iteration": None,
            "mpi_np": row.get("mpi_np") or 1,

            # Layer 2
            "resolution": phys_ctx.get("resolution"),
            "pml_thickness": phys_ctx.get("pml_thickness"),
            "wavelength_um": wavelength_um,
            "dim": infer_dim(original_code),
            "uses_adjoint": int("adjoint" in original_code.lower()),
            "uses_symmetry": int("Symmetry" in original_code or "Mirror" in original_code),
            "device_type": infer_device_type(original_code),
            "cell_size": extract_cell_size(original_code),

            # Layer 3
            "error_class": infer_error_class(error_type, error_message),
            "error_type": error_type,
            "error_message": error_message,
            "traceback_full": row.get("context") or "",
            "symptom": infer_symptom(error_message, error_type),

            # Layer 4
            "trigger_code": extract_trigger_code(original_code, error_message),
            "trigger_line": "",
            "physics_cause": "",  # physics_enricher로 채울 것
            "code_cause": row.get("root_cause") or "",
            "root_cause_chain": root_cause_chain,

            # Layer 5
            "fix_type": infer_fix_type(error_type, row.get("fix_description")),
            "fix_description": row.get("fix_description") or row.get("fix_applied") or "",
            "original_code": original_code,
            "fixed_code": fixed_code,
            "code_diff": make_diff(original_code, fixed_code),
            "fix_worked": row.get("fix_worked") or 1,

            # 메타
            "source": "error_injector" if row.get("source") == "error_injector" else "marl_auto",
            "meep_version": row.get("meep_version") or "1.28.0",
            "run_time_sec": row.get("run_time_sec"),
            "code_length": row.get("code_length") or len(original_code),
            "code_hash": code_hash,
        }

        if dry_run:
            print(f"  [DRY-RUN] id={row['id']}, source={row['source']}, "
                  f"error_type={error_type}, run_mode={v2_record['run_mode']}, "
                  f"error_class={v2_record['error_class']}")
            inserted += 1
            results.append({"id": row["id"], "status": "would_insert"})
            continue

        try:
            conn.execute(
                """
                INSERT INTO sim_errors_v2 (
                    run_mode, run_stage, iteration, mpi_np,
                    resolution, pml_thickness, wavelength_um, dim,
                    uses_adjoint, uses_symmetry, device_type, cell_size,
                    error_class, error_type, error_message, traceback_full, symptom,
                    trigger_code, trigger_line, physics_cause, code_cause, root_cause_chain,
                    fix_type, fix_description, original_code, fixed_code, code_diff, fix_worked,
                    source, meep_version, run_time_sec, code_length, code_hash
                ) VALUES (
                    :run_mode, :run_stage, :iteration, :mpi_np,
                    :resolution, :pml_thickness, :wavelength_um, :dim,
                    :uses_adjoint, :uses_symmetry, :device_type, :cell_size,
                    :error_class, :error_type, :error_message, :traceback_full, :symptom,
                    :trigger_code, :trigger_line, :physics_cause, :code_cause, :root_cause_chain,
                    :fix_type, :fix_description, :original_code, :fixed_code, :code_diff, :fix_worked,
                    :source, :meep_version, :run_time_sec, :code_length, :code_hash
                )
                """,
                v2_record,
            )
            conn.commit()
            inserted += 1
            print(f"  [OK] id={row['id']}, source={row['source']}, "
                  f"error_type={error_type[:40]}, run_mode={v2_record['run_mode']}")
            results.append({"id": row["id"], "status": "inserted"})
        except Exception as e:
            print(f"  [ERROR] id={row['id']}: {e}", file=sys.stderr)
            failed += 1
            results.append({"id": row["id"], "status": "failed", "error": str(e)})

    conn.close()

    summary = {
        "total": len(rows),
        "inserted": inserted,
        "skipped_dup": skipped_dup,
        "failed": failed,
    }
    print(f"\n완료: {summary}")
    return summary


def update_score_by_source():
    """api/diagnose_engine.py의 error_injector 점수를 0.88 → 0.93으로 업데이트"""
    engine_path = Path(__file__).parent.parent / "api" / "diagnose_engine.py"
    if not engine_path.exists():
        print(f"[WARN] {engine_path} 파일 없음 → 스킵")
        return False

    content = engine_path.read_text(encoding="utf-8")
    old = '"error_injector":    0.88,  # Docker 에러 확인'
    new = '"error_injector":    0.93,  # 0.88→0.93 상향 (v2 구조로 풍부해짐, 2026-03-25)'

    if old in content:
        updated = content.replace(old, new)
        engine_path.write_text(updated, encoding="utf-8")
        print(f"[OK] SCORE_BY_SOURCE error_injector 0.88 → 0.93 업데이트")
        return True
    elif "0.88" in content and "error_injector" in content:
        # 공백 차이로 못 찾을 경우 regex
        import re
        updated = re.sub(
            r'("error_injector"\s*:\s*)0\.88',
            r'\g<1>0.93',
            content
        )
        if updated != content:
            engine_path.write_text(updated, encoding="utf-8")
            print(f"[OK] SCORE_BY_SOURCE error_injector 0.88 → 0.93 업데이트 (regex)")
            return True
    print(f"[WARN] error_injector 0.88 패턴을 찾지 못함 → 수동 수정 필요")
    return False


def main():
    parser = argparse.ArgumentParser(description="sim_errors → sim_errors_v2 마이그레이션")
    parser.add_argument("--dry-run", action="store_true", help="DB 업데이트 없이 출력만")
    parser.add_argument("--no-enrich", action="store_true", help="physics_cause LLM 채우기 스킵")
    args = parser.parse_args()

    print("=" * 60)
    print("sim_errors → sim_errors_v2 마이그레이션")
    print("=" * 60)

    # 1. 마이그레이션
    result = migrate(dry_run=args.dry_run)

    if args.dry_run:
        print("\n[DRY-RUN 완료] 실제 DB 변경 없음")
        return

    # 2. physics_cause LLM 채우기
    if not args.no_enrich and result["inserted"] > 0:
        print("\n" + "=" * 60)
        print("physics_cause LLM 보강 (source='error_injector' OR 'marl_auto')")
        print("=" * 60)
        try:
            from physics_enricher import enrich_pending
            enrich_result = enrich_pending(limit=60, model="haiku")
            print(f"  → 보강 완료: {enrich_result['success']}건 성공, {enrich_result['failed']}건 실패")
        except Exception as e:
            print(f"  [WARN] physics_enricher 호출 실패: {e}")

    # 3. SCORE_BY_SOURCE 업데이트
    print("\n" + "=" * 60)
    print("SCORE_BY_SOURCE 업데이트")
    print("=" * 60)
    update_score_by_source()

    # 4. 최종 확인
    conn = sqlite3.connect(str(DB_PATH))
    total_v2 = conn.execute("SELECT COUNT(*) FROM sim_errors_v2").fetchone()[0]
    fix_worked = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=1").fetchone()[0]
    physics_filled = conn.execute(
        "SELECT COUNT(*) FROM sim_errors_v2 WHERE physics_cause IS NOT NULL AND physics_cause != ''"
    ).fetchone()[0]
    conn.close()

    print(f"\n최종 상태:")
    print(f"  sim_errors_v2 총: {total_v2}건")
    print(f"  fix_worked=1: {fix_worked}건")
    print(f"  physics_cause 채워진 건수: {physics_filled}건")


if __name__ == "__main__":
    main()
