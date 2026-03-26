#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
concepts 테이블의 demo_code를 meep-pilot-worker에서 실행.
성공 시 result_status='success', 실패 시 result_status='error'

사용법:
  python -u -X utf8 tools/run_concept_demos.py --all
  python -u -X utf8 tools/run_concept_demos.py --name PML
  python -u -X utf8 tools/run_concept_demos.py --skip-existing  # 기본값 True
"""
import sqlite3
import subprocess
import tempfile
import os
import sys
import argparse
import re
import shutil
from pathlib import Path
from datetime import datetime

# ── 경로 설정 ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "db" / "knowledge.db"
RESULTS_DIR = PROJECT_ROOT / "db" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DOCKER_WORKER = "meep-pilot-worker"
TIMEOUT = 90  # seconds


def preprocess_code(code: str, name: str) -> str:
    """데모 코드 전처리: meep import, matplotlib Agg, plt.show() 처리"""
    lines = code.splitlines()

    # 1. matplotlib.use('Agg') 맨 앞에 보장
    has_matplotlib_use = any("matplotlib.use" in l for l in lines)
    if not has_matplotlib_use:
        lines = ["import matplotlib", "matplotlib.use('Agg')"] + lines

    # 2. (autograd 설치됨 — adjoint import 허용)

    # 3. import meep as mp 없으면 주입
    has_meep_import = any(
        re.match(r'^\s*import meep', l) or re.match(r'^\s*from meep', l)
        for l in lines
    )
    if not has_meep_import:
        new_lines = []
        inserted = False
        for line in lines:
            new_lines.append(line)
            if not inserted and "matplotlib.use" in line:
                new_lines.append("import meep as mp")
                inserted = True
        if not inserted:
            new_lines = ["import meep as mp"] + new_lines
        lines = new_lines

    code = "\n".join(lines)

    # 3. plt.show() → pass
    code = re.sub(r'\bplt\.show\(\)', 'pass  # plt.show() disabled', code)

    # 4. plt.savefig 경로를 /tmp/concept_{name}.png 로 통일
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    output_path = f"/tmp/concept_{safe_name}.png"
    if "plt.savefig" in code:
        # 기존 savefig 경로를 표준 경로로 교체
        code = re.sub(r"plt\.savefig\(['\"][^'\"]*['\"]\)", f"plt.savefig('{output_path}')", code)
    elif "plt." in code or "matplotlib" in code:
        code += f"\ntry:\n    import matplotlib.pyplot as plt\n    plt.tight_layout()\n    plt.savefig('{output_path}', dpi=100, bbox_inches='tight')\nexcept Exception:\n    pass\n"

    return code


def run_concept(name: str, code: str, dry_run: bool = False) -> dict:
    """단일 개념 demo 코드 실행. 결과 dict 반환."""
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    tmp_filename = f"temp_concept_{safe_name}.py"
    tmp_path = Path(tempfile.gettempdir()) / tmp_filename
    output_path = f"/tmp/concept_{safe_name}.png"

    processed = preprocess_code(code, name)

    if dry_run:
        print(f"  [DRY-RUN] {name}: {len(processed)} chars")
        return {"status": "skip", "notes": "dry-run"}

    # 로컬 임시 파일 작성
    tmp_path.write_text(processed, encoding="utf-8")
    print(f"  [{name}] 로컬 임시 파일 작성: {tmp_path}")

    try:
        # docker cp → worker
        cp_result = subprocess.run(
            ["docker", "cp", str(tmp_path), f"{DOCKER_WORKER}:/tmp/{tmp_filename}"],
            capture_output=True, text=True, timeout=30
        )
        if cp_result.returncode != 0:
            return {"status": "error", "notes": f"docker cp failed: {cp_result.stderr[:500]}"}

        # docker exec 실행
        print(f"  [{name}] docker exec python3 /tmp/{tmp_filename} (timeout={TIMEOUT}s)")
        exec_result = subprocess.run(
            ["docker", "exec", DOCKER_WORKER, "python3", f"/tmp/{tmp_filename}"],
            capture_output=True, text=True, timeout=TIMEOUT
        )
        stdout = exec_result.stdout[-2000:] if exec_result.stdout else ""
        stderr = exec_result.stderr[-2000:] if exec_result.stderr else ""

        if exec_result.returncode == 0:
            status = "success"
            notes = stdout[:500] if stdout else "OK"
            print(f"  [{name}] ✅ 성공")
        else:
            status = "error"
            notes = (stderr or stdout)[:500]
            print(f"  [{name}] ❌ 실패: {notes[:120]}")

        # 이미지 회수
        img_saved = None
        try:
            img_local = RESULTS_DIR / f"concept_{safe_name}.png"
            img_cp = subprocess.run(
                ["docker", "cp", f"{DOCKER_WORKER}:{output_path}", str(img_local)],
                capture_output=True, timeout=15
            )
            if img_cp.returncode == 0 and img_local.stat().st_size > 500:
                print(f"  [{name}] 🖼️  이미지 저장: {img_local.name} ({img_local.stat().st_size//1024}KB)")
                img_saved = str(img_local)
            else:
                # output.png도 시도 (일부 코드가 output.png로 저장)
                img_cp2 = subprocess.run(
                    ["docker", "cp", f"{DOCKER_WORKER}:/tmp/output.png", str(img_local)],
                    capture_output=True, timeout=10
                )
                if img_cp2.returncode == 0 and img_local.exists() and img_local.stat().st_size > 500:
                    print(f"  [{name}] 🖼️  이미지 저장 (output.png): {img_local.name}")
                    img_saved = str(img_local)
        except Exception:
            pass

        return {"status": status, "notes": notes, "image": img_saved}

    except subprocess.TimeoutExpired:
        print(f"  [{name}] ⏱️  타임아웃")
        return {"status": "timeout", "notes": f"timeout after {TIMEOUT}s"}
    finally:
        tmp_path.unlink(missing_ok=True)


def update_db(name: str, status: str, notes: str, image_path: str = None):
    conn = sqlite3.connect(str(DB_PATH))
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # 이미지 경로: /static/results/concept_{name}.png (웹에서 접근 가능한 경로)
    img_url = f"/static/results/concept_{safe_name}.png" if image_path else None
    conn.execute(
        "UPDATE concepts SET result_status=?, result_stdout=?, result_images=?, "
        "result_executed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE name=?",
        (status, notes, img_url, name)
    )
    conn.commit()
    conn.close()


def load_pending(skip_existing: bool, name_filter: str = None) -> list:
    conn = sqlite3.connect(str(DB_PATH))
    if name_filter:
        rows = conn.execute(
            "SELECT name, demo_code FROM concepts WHERE name=?",
            (name_filter,)
        ).fetchall()
    elif skip_existing:
        rows = conn.execute(
            "SELECT name, demo_code FROM concepts "
            "WHERE demo_code IS NOT NULL AND LENGTH(demo_code) > 20 "
            "AND result_status='pending' "
            "ORDER BY difficulty, category, name"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT name, demo_code FROM concepts "
            "WHERE demo_code IS NOT NULL AND LENGTH(demo_code) > 20 "
            "ORDER BY difficulty, category, name"
        ).fetchall()
    conn.close()
    return [(r[0], r[1]) for r in rows if r[1]]


def main():
    parser = argparse.ArgumentParser(description="Run concept demo codes in meep-pilot-worker")
    parser.add_argument("--all", action="store_true", help="모든 pending demo 실행")
    parser.add_argument("--name", type=str, help="특정 concept 이름만 실행")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="기존 success/error 건너뜀 (기본값 True)")
    parser.add_argument("--no-skip", action="store_true", help="skip-existing 비활성화 (재실행)")
    parser.add_argument("--dry-run", action="store_true", help="실제 실행 없이 확인만")
    args = parser.parse_args()

    skip_existing = not args.no_skip
    
    if args.name:
        concepts = load_pending(skip_existing=False, name_filter=args.name)
    elif args.all or True:  # default
        concepts = load_pending(skip_existing=skip_existing)

    if not concepts:
        print("실행할 concept demo가 없습니다.")
        return

    print(f"\n{'='*60}")
    print(f"🚀 Concept Demo Runner")
    print(f"대상: {len(concepts)}개 | Worker: {DOCKER_WORKER} | Timeout: {TIMEOUT}s")
    print(f"{'='*60}\n")

    # Worker 상태 확인
    check = subprocess.run(
        ["docker", "inspect", "--format={{.State.Status}}", DOCKER_WORKER],
        capture_output=True, text=True
    )
    if "running" not in check.stdout:
        print(f"❌ {DOCKER_WORKER} 컨테이너가 실행 중이지 않습니다!")
        print(f"   상태: {check.stdout.strip()}")
        sys.exit(1)
    print(f"✅ {DOCKER_WORKER} 컨테이너 확인\n")

    results = {"success": 0, "error": 0, "timeout": 0, "skip": 0}

    for i, (name, code) in enumerate(concepts, 1):
        print(f"\n[{i}/{len(concepts)}] {name}")
        result = run_concept(name, code, dry_run=args.dry_run)
        status = result["status"]
        notes = result.get("notes", "")

        if not args.dry_run:
            update_db(name, status, notes, result.get("image"))

        results[status] = results.get(status, 0) + 1

    print(f"\n{'='*60}")
    print(f"📊 실행 결과 요약")
    print(f"  ✅ 성공:    {results.get('success', 0)}")
    print(f"  ❌ 오류:    {results.get('error', 0)}")
    print(f"  ⏱️  타임아웃: {results.get('timeout', 0)}")
    print(f"  ⏭️  스킵:    {results.get('skip', 0)}")
    print(f"{'='*60}\n")

    if not args.dry_run:
        # 최종 DB 상태 확인
        conn = sqlite3.connect(str(DB_PATH))
        stats = dict(conn.execute(
            "SELECT result_status, COUNT(*) FROM concepts GROUP BY result_status"
        ).fetchall())
        conn.close()
        print(f"📦 DB 최종 상태: {stats}")


if __name__ == "__main__":
    main()
