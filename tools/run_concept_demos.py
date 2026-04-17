#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
concepts 테이블의 demo_code를 meep-pilot-worker에서 실행.
성공 시 result_status='success', 실패 시 result_status='error'

사용법:
  python -u -X utf8 tools/run_concept_demos.py --all
  python -u -X utf8 tools/run_concept_demos.py --name PML
  python -u -X utf8 tools/run_concept_demos.py --images-only   # 이미지 없는 것만 재실행
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

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "db" / "knowledge.db"
RESULTS_DIR = PROJECT_ROOT / "db" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DOCKER_WORKER = "meep-pilot-worker"
TIMEOUT = 90


def preprocess_code(code: str, name: str) -> str:
    """데모 코드 전처리: meep import, matplotlib Agg, savefig 경로 통일."""
    lines = code.splitlines()

    # 1. matplotlib.use('Agg') 보장
    has_mpl = any("matplotlib.use" in l for l in lines)
    if not has_mpl:
        lines = ["import matplotlib", "matplotlib.use('Agg')"] + lines

    # 2. import meep as mp 없으면 주입
    has_meep = any(re.match(r'^\s*import meep', l) for l in lines)
    if not has_meep:
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
    code = re.sub(r'\bplt\.show\(\)', 'pass', code)

    # 4. 모든 savefig 경로를 /tmp/concept_{name}.png 로 통일
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    output_path = f"/tmp/concept_{safe_name}.png"

    if "savefig" in code:
        # plt.savefig('경로', ...) → 표준 경로로 교체
        code = re.sub(
            r"plt\.savefig\(['\"][^'\"]*['\"]\s*(?:,\s*[^)]+)?\)",
            f"plt.savefig('{output_path}', dpi=100, bbox_inches='tight')",
            code
        )
        # fig.savefig('경로', ...) 형태
        code = re.sub(
            r"(?:fig\w*|f)\.savefig\(['\"][^'\"]*['\"]\s*(?:,\s*[^)]+)?\)",
            f"plt.savefig('{output_path}', dpi=100, bbox_inches='tight')",
            code
        )
        # 교체 후에도 표준 경로가 없으면 추가
        if output_path not in code:
            code += f"\ntry:\n    import matplotlib.pyplot as plt\n    plt.savefig('{output_path}', dpi=100, bbox_inches='tight')\nexcept Exception:\n    pass\n"
    elif "plt." in code or "matplotlib" in code:
        code += f"\ntry:\n    import matplotlib.pyplot as plt\n    plt.tight_layout()\n    plt.savefig('{output_path}', dpi=100, bbox_inches='tight')\nexcept Exception:\n    pass\n"

    return code


def run_concept(name: str, code: str, dry_run: bool = False) -> dict:
    """단일 개념 demo 코드 실행."""
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    tmp_filename = f"temp_concept_{safe_name}.py"
    tmp_path = Path(tempfile.gettempdir()) / tmp_filename
    output_path = f"/tmp/concept_{safe_name}.png"

    processed = preprocess_code(code, name)

    if dry_run:
        print(f"  [DRY-RUN] {name}: {len(processed)} chars")
        return {"status": "skip", "notes": "dry-run"}

    tmp_path.write_text(processed, encoding="utf-8")
    print(f"  [{name}] docker exec python3 /tmp/{tmp_filename} (timeout={TIMEOUT}s)")

    try:
        subprocess.run(
            ["docker", "cp", str(tmp_path), f"{DOCKER_WORKER}:/tmp/{tmp_filename}"],
            capture_output=True, text=True, timeout=30
        )

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
            # 1차: /tmp/concept_{name}.png
            cp1 = subprocess.run(
                ["docker", "cp", f"{DOCKER_WORKER}:{output_path}", str(img_local)],
                capture_output=True, timeout=15
            )
            if cp1.returncode == 0 and img_local.exists() and img_local.stat().st_size > 500:
                print(f"  [{name}] 🖼️  이미지 저장: {img_local.name} ({img_local.stat().st_size//1024}KB)")
                img_saved = str(img_local)
            else:
                # 2차: 현재 디렉토리 output.png
                cp2 = subprocess.run(
                    ["docker", "exec", DOCKER_WORKER, "sh", "-c", "cat output.png 2>/dev/null | wc -c"],
                    capture_output=True, text=True, timeout=5
                )
                size = int(cp2.stdout.strip()) if cp2.stdout.strip().isdigit() else 0
                if size > 500:
                    subprocess.run(
                        ["docker", "exec", DOCKER_WORKER, "cp", "output.png", output_path],
                        capture_output=True, timeout=5
                    )
                    cp3 = subprocess.run(
                        ["docker", "cp", f"{DOCKER_WORKER}:{output_path}", str(img_local)],
                        capture_output=True, timeout=15
                    )
                    if cp3.returncode == 0 and img_local.stat().st_size > 500:
                        print(f"  [{name}] 🖼️  이미지 저장 (output.png): {img_local.name}")
                        img_saved = str(img_local)
        except Exception as e:
            pass

        return {"status": status, "notes": notes, "image": img_saved}

    except subprocess.TimeoutExpired:
        print(f"  [{name}] ⏱️  타임아웃")
        return {"status": "timeout", "notes": f"timeout after {TIMEOUT}s", "image": None}
    finally:
        tmp_path.unlink(missing_ok=True)


def update_db(name: str, status: str, notes: str, image_path: str = None):
    conn = sqlite3.connect(str(DB_PATH))
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    img_url = f"/static/results/concept_{safe_name}.png" if image_path else None
    conn.execute(
        "UPDATE concepts SET result_status=?, result_stdout=?, result_images=?, "
        "result_executed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE name=?",
        (status, notes, img_url, name)
    )
    conn.commit()
    conn.close()


def load_concepts(skip_existing=True, name_filter=None, images_only=False):
    conn = sqlite3.connect(str(DB_PATH))
    if name_filter:
        rows = conn.execute(
            "SELECT name, demo_code FROM concepts WHERE name=?", (name_filter,)
        ).fetchall()
    elif images_only:
        rows = conn.execute(
            "SELECT name, demo_code FROM concepts "
            "WHERE (result_images IS NULL OR result_images='') "
            "AND demo_code IS NOT NULL AND LENGTH(demo_code) > 20 "
            "ORDER BY difficulty, category, name"
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--name", type=str)
    parser.add_argument("--no-skip", action="store_true")
    parser.add_argument("--images-only", action="store_true", help="이미지 없는 것만 재실행")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.name:
        concepts = load_concepts(skip_existing=False, name_filter=args.name)
    elif args.images_only:
        concepts = load_concepts(images_only=True)
    else:
        concepts = load_concepts(skip_existing=not args.no_skip)

    if not concepts:
        print("실행할 concept demo가 없습니다.")
        return

    print(f"\n{'='*60}")
    print(f"🚀 Concept Demo Runner")
    print(f"대상: {len(concepts)}개 | Worker: {DOCKER_WORKER} | Timeout: {TIMEOUT}s")
    print(f"{'='*60}\n")

    check = subprocess.run(
        ["docker", "inspect", "--format={{.State.Status}}", DOCKER_WORKER],
        capture_output=True, text=True
    )
    if "running" not in check.stdout:
        print(f"❌ {DOCKER_WORKER} 미실행"); sys.exit(1)
    print(f"✅ {DOCKER_WORKER} 확인\n")

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
    print(f"📊 결과: ✅ {results.get('success',0)} | ❌ {results.get('error',0)} | ⏱ {results.get('timeout',0)}")
    print(f"{'='*60}\n")

    if not args.dry_run:
        conn = sqlite3.connect(str(DB_PATH))
        stats = dict(conn.execute("SELECT result_status, COUNT(*) FROM concepts GROUP BY result_status").fetchall())
        n_img = conn.execute("SELECT COUNT(*) FROM concepts WHERE result_images IS NOT NULL AND result_images!=''").fetchone()[0]
        conn.close()
        print(f"DB: {stats} | 이미지: {n_img}개")


if __name__ == "__main__":
    main()
