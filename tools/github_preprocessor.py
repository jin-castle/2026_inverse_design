"""
github_preprocessor.py
GitHub Issues에서 실행 가능한 MEEP 코드를 추출하고 분류.
sim_errors의 github_issue(242) + github_structured(151) = 393건 처리.
"""

import sqlite3
import json
import re
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"
OUTPUT_PATH = Path(__file__).parent / "runnable_issues.json"

# === 공통 패치 치환 ===
COMMON_FIXES = {
    "from common import *": (
        "# common.py inline substitution\n"
        "import meep as mp\n"
        "import numpy as np\n"
        "import matplotlib\n"
        "matplotlib.use('Agg')\n"
        "import matplotlib.pyplot as plt\n"
    ),
    "from utils import *": (
        "import numpy as np\n"
        "import matplotlib\n"
        "matplotlib.use('Agg')\n"
    ),
    "plt.show()": "# plt.show() disabled",
    "plt.show(block=True)": "# plt.show() disabled",
    "plt.show(block=False)": "# plt.show() disabled",
}

# 주석 처리할 패턴 (줄 단위)
LINE_DISABLE_PATTERNS = [
    r"mp\.output_png\b",
    r"mp\.output_hdf5\b",
    r"mp\.h5topng\b",
    r"sim\.output_png\b",
]

# 제거할 import 패턴
REMOVE_IMPORT_PATTERNS = [
    r"^import sys$",
    r"^from __future__",
]


def extract_code_blocks(text: str) -> list:
    """텍스트에서 Python 코드 블록을 추출 (우선순위 순)."""
    if not text:
        return []

    blocks = []

    # 1. ```python ... ``` 추출 (최고 우선순위)
    python_blocks = re.findall(r"```python\s*\n(.*?)```", text, re.DOTALL)
    for block in python_blocks:
        block = block.strip()
        if block and len(block) > 30:
            blocks.append(("python_fence", block))

    # 2. ```python3 ... ``` 추출
    python3_blocks = re.findall(r"```python3\s*\n(.*?)```", text, re.DOTALL)
    for block in python3_blocks:
        block = block.strip()
        if block and len(block) > 30:
            blocks.append(("python3_fence", block))

    # 3. ``` ... ``` (meep/import/mp. 포함된 것만)
    generic_blocks = re.findall(r"```\s*\n(.*?)```", text, re.DOTALL)
    for block in generic_blocks:
        block = block.strip()
        if block and len(block) > 30:
            if any(kw in block for kw in ["import meep", "import mp", "mp.Simulation", "mp.Vector3", "meep as mp"]):
                blocks.append(("generic_fence", block))

    # 4. 4-space indent 블록 (최소 5줄 이상)
    indent_lines = []
    in_block = False
    current_block = []
    for line in text.split("\n"):
        if line.startswith("    ") or line.startswith("\t"):
            current_block.append(line[4:] if line.startswith("    ") else line[1:])
            in_block = True
        else:
            if in_block and len(current_block) >= 5:
                block_text = "\n".join(current_block).strip()
                if any(kw in block_text for kw in ["import meep", "mp.Simulation"]):
                    blocks.append(("indent", block_text))
            current_block = []
            in_block = False
    if in_block and len(current_block) >= 5:
        block_text = "\n".join(current_block).strip()
        if any(kw in block_text for kw in ["import meep", "mp.Simulation"]):
            blocks.append(("indent", block_text))

    return blocks


def apply_common_fixes(code: str) -> tuple:
    """COMMON_FIXES 패턴 적용. 반환: (patched_code, patches_applied)"""
    patches = []
    for pattern, replacement in COMMON_FIXES.items():
        if pattern in code:
            code = code.replace(pattern, replacement)
            patches.append(pattern.split()[0] if " " in pattern else pattern)

    # 줄 단위 주석 처리
    lines = code.split("\n")
    new_lines = []
    for line in lines:
        disabled = False
        for pat in LINE_DISABLE_PATTERNS:
            if re.search(pat, line):
                new_lines.append("# " + line + "  # disabled: interactive/output")
                patches.append("output_disable")
                disabled = True
                break
        if not disabled:
            new_lines.append(line)
    code = "\n".join(new_lines)

    return code, list(set(patches))


def patch_code(code: str) -> tuple:
    """최소 실행 가능 코드로 변환. 반환: (patched_code, patches_applied)"""
    patches = []

    # common/utils 치환 먼저
    code, common_patches = apply_common_fixes(code)
    patches.extend(common_patches)

    # import meep as mp 없으면 추가
    if "import meep" not in code and "import mp" not in code:
        code = "import meep as mp\n" + code
        patches.append("add_import_meep")

    # import numpy if missing
    if "numpy" in code and "import numpy" not in code:
        code = "import numpy as np\n" + code
        patches.append("add_import_numpy")

    # matplotlib.use('Agg') - headless 환경 대비
    if "import matplotlib" in code and "matplotlib.use" not in code:
        code = code.replace(
            "import matplotlib.pyplot as plt",
            "import matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.pyplot as plt"
        )
        patches.append("matplotlib_agg")

    # sys.argv 제거
    if "sys.argv" in code:
        lines = code.split("\n")
        new_lines = []
        for line in lines:
            if "sys.argv" in line:
                new_lines.append("# " + line + "  # sys.argv disabled")
                patches.append("sys_argv_disable")
            else:
                new_lines.append(line)
        code = "\n".join(new_lines)

    # argparse 블록 제거 (간단 치환)
    if "argparse" in code:
        code = re.sub(r"import argparse.*?parse_args\(\)", "# argparse removed", code, flags=re.DOTALL)
        patches.append("argparse_remove")

    # 외부 파일 참조 제거 (open("...") 읽기 모드)
    lines = code.split("\n")
    new_lines = []
    for line in lines:
        if re.search(r'open\s*\(\s*["\'][^"\']+["\'],?\s*["\']?r', line):
            new_lines.append("# " + line + "  # external file ref removed")
            patches.append("file_ref_remove")
        else:
            new_lines.append(line)
    code = "\n".join(new_lines)

    return code, list(set(patches))


def runability_score(code: str) -> dict:
    """실행 가능성 점수 계산. 최대 100점."""
    score = 0
    flags = {}

    # +30: import meep
    flags["has_import_meep"] = "import meep" in code or "meep as mp" in code
    if flags["has_import_meep"]:
        score += 30

    # +25: mp.Simulation 정의
    flags["has_simulation"] = "mp.Simulation" in code
    if flags["has_simulation"]:
        score += 25

    # +20: sim.run 또는 .run(
    flags["has_run"] = bool(re.search(r"\.run\(|sim\.run|sim\.meep_run", code))
    if flags["has_run"]:
        score += 20

    # +15: 외부 파일 참조 없음
    flags["no_external_files"] = not bool(re.search(r'open\s*\(\s*["\'][^"\']+["\'],?\s*["\']?r', code))
    if flags["no_external_files"]:
        score += 15

    # +10: 로컬 import 없음
    flags["no_local_imports"] = not bool(re.search(r"from common|from utils|from \.", code))
    if flags["no_local_imports"]:
        score += 10

    return {
        "score": score,
        "flags": flags,
        "runnable": score >= 70
    }


def select_best_code(blocks: list) -> tuple:
    """여러 코드 블록 중 가장 좋은 것 선택. 반환: (code, source_type)"""
    if not blocks:
        return None, None

    # 우선순위: python_fence > python3_fence > generic_fence > indent
    priority = {"python_fence": 0, "python3_fence": 1, "generic_fence": 2, "indent": 3}

    # 정렬: 우선순위 낮을수록(0이 최고), 길이 길수록
    sorted_blocks = sorted(blocks, key=lambda x: (priority.get(x[0], 99), -len(x[1])))
    return sorted_blocks[0][1], sorted_blocks[0][0]


def process_row(row: dict) -> dict | None:
    """단일 sim_errors 행 처리. 반환: 처리 결과 dict 또는 None."""
    # 모든 텍스트 필드에서 코드 블록 추출
    all_blocks = []
    for field in ["context", "root_cause", "fix_applied", "error_message"]:
        text = row.get(field) or ""
        blocks = extract_code_blocks(text)
        all_blocks.extend(blocks)

    if not all_blocks:
        return None

    # 최고 코드 선택
    raw_code, code_source = select_best_code(all_blocks)
    if not raw_code:
        return None

    # 패치 적용
    patched_code, patches = patch_code(raw_code)

    # 점수 계산
    score_result = runability_score(patched_code)
    score = score_result["score"]

    # 분류
    if score >= 70:
        category = "runnable"
    elif score >= 40:
        category = "patchable"
    else:
        category = "not_runnable"

    return {
        "sim_error_id": row["id"],
        "source": row["source"],
        "error_type": row.get("error_type", ""),
        "error_message": (row.get("error_message") or "")[:200],
        "code_source_field": code_source,
        "raw_code_length": len(raw_code),
        "code": patched_code,
        "score": score,
        "flags": score_result["flags"],
        "patches_applied": patches,
        "category": category,
    }


def main():
    print(f"DB: {DB_PATH}")
    print(f"Output: {OUTPUT_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 393건 로드
    cur.execute("""
        SELECT id, source, error_type, error_message, context, root_cause, fix_applied
        FROM sim_errors
        WHERE source IN ('github_issue', 'github_structured')
        ORDER BY id
    """)
    rows = cur.fetchall()
    conn.close()

    print(f"Loaded {len(rows)} rows")

    results = {
        "summary": {
            "total": len(rows),
            "has_code": 0,
            "runnable": 0,
            "patchable": 0,
            "not_runnable": 0
        },
        "runnable": [],
        "patchable": [],
    }

    not_runnable_count = 0

    for row in rows:
        row_dict = dict(row)
        result = process_row(row_dict)

        if result is None:
            not_runnable_count += 1
            continue

        results["summary"]["has_code"] += 1

        if result["category"] == "runnable":
            results["summary"]["runnable"] += 1
            results["runnable"].append({
                "sim_error_id": result["sim_error_id"],
                "source": result["source"],
                "error_type": result["error_type"],
                "code": result["code"],
                "score": result["score"],
                "flags": result["flags"],
                "patches_applied": result["patches_applied"],
            })
        elif result["category"] == "patchable":
            results["summary"]["patchable"] += 1
            results["patchable"].append({
                "sim_error_id": result["sim_error_id"],
                "source": result["source"],
                "error_type": result["error_type"],
                "code": result["code"],
                "score": result["score"],
                "flags": result["flags"],
                "patches_applied": result["patches_applied"],
            })
        else:
            not_runnable_count += 1

    results["summary"]["not_runnable"] = not_runnable_count

    # 출력
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n=== 결과 ===")
    print(f"Total: {results['summary']['total']}")
    print(f"Has code: {results['summary']['has_code']}")
    print(f"Runnable (score≥70): {results['summary']['runnable']}")
    print(f"Patchable (40~69): {results['summary']['patchable']}")
    print(f"Not runnable: {results['summary']['not_runnable']}")
    print(f"\nSaved: {OUTPUT_PATH}")

    if results["runnable"]:
        print("\n--- Runnable 샘플 (첫 번째) ---")
        r = results["runnable"][0]
        print(f"ID={r['sim_error_id']}, score={r['score']}, type={r['error_type']}")
        print(f"Code (첫 200자):\n{r['code'][:200]}")

    return results


if __name__ == "__main__":
    main()
