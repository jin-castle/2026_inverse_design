"""
generate_patterns.py
DB의 127개 패턴을 읽어 autosim/patterns/*.py 로 생성.
Windows 로컬에서 실행.
"""
import sqlite3, re, textwrap
from pathlib import Path

DB_PATH      = Path(__file__).parent.parent / "db" / "knowledge.db"
PATTERNS_DIR = Path(__file__).parent / "patterns"
PATTERNS_DIR.mkdir(exist_ok=True)

# ── 제거할 import 패턴 ────────────────────────────────────────────────────
REMOVE_IMPORT_RE = re.compile(
    r"^\s*(import meep|import numpy|import matplotlib|import autograd"
    r"|from meep import|from numpy import|from matplotlib|from autograd"
    r"|import json|import os|import sys|from pathlib"
    r"|from __future__)"
    r".*$",
    re.MULTILINE
)

# ── plt.show() 제거 ──────────────────────────────────────────────────────
SHOW_RE = re.compile(r"plt\.show\(\)", re.MULTILINE)

# ── 절대 savefig 경로 패치 ────────────────────────────────────────────────
SAVEFIG_RE = re.compile(r'plt\.savefig\(["\']([^"\']+)["\']\)', re.MULTILINE)

def clean_code(code: str, pattern_name: str) -> str:
    """패턴 코드 정제"""
    # 1. 공통 import 제거
    code = REMOVE_IMPORT_RE.sub("", code)
    # 2. plt.show() 제거
    code = SHOW_RE.sub("# plt.show() suppressed", code)
    # 3. 상대 savefig 경로를 RESULT_DIR 기반으로 패치
    def patch_savefig(m):
        orig_path = m.group(1)
        if orig_path.startswith("/"):
            return m.group(0)  # 절대경로는 그대로
        fname = Path(orig_path).name or "output.png"
        return f'plt.savefig(str(RESULT_DIR / "{pattern_name}" / "{fname}"))'
    code = SAVEFIG_RE.sub(patch_savefig, code)
    # 4. 빈 줄 3개 이상 → 2줄로
    code = re.sub(r"\n{3,}", "\n\n", code)
    # 5. 빈 try 블록 fix: "try:\n\nexcept" → "try:\n    pass\nexcept"
    code = re.sub(r'(try:)\s*\n(\s*except)', r'\1\n    pass\n\2', code)
    return code.strip()


TEMPLATE = '''\
#!/usr/bin/env python3
"""
Pattern: __PATTERN_NAME__
__SUMMARY__
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "__PATTERN_NAME__"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
__INDENTED_CODE__
    # ─────────────────────────────────────────────────────────

    # figure 자동 저장
    _outputs = []
    if plt.get_fignums():
        _out = savefig_safe(_PATTERN)
        if _out:
            _outputs.append("output.png")

    _elapsed = round(_time.time() - _t0, 2)
    save_result(_PATTERN, outputs=_outputs, elapsed=_elapsed)
    if mp.am_master():
        print(f"[OK] {_PATTERN} ({_elapsed}s) outputs={_outputs}")

except Exception as _e:
    _elapsed = round(_time.time() - _t0, 2)
    save_result(_PATTERN, error=_e, elapsed=_elapsed)
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''


def make_pattern_file(pid: int, name: str, description: str, code: str) -> Path:
    summary = (description or "").strip().splitlines()[0][:120] if description else ""
    cleaned = clean_code(code or "", name)
    indented = textwrap.indent(cleaned, "    ")

    content = (
        TEMPLATE
        .replace("__PATTERN_NAME__", name)
        .replace("__SUMMARY__", summary)
        .replace("__INDENTED_CODE__", indented)
    )
    out_path = PATTERNS_DIR / f"{name}.py"
    out_path.write_text(content, encoding="utf-8")
    return out_path


def main():
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT id, pattern_name, description, code_snippet FROM patterns ORDER BY id"
    ).fetchall()
    conn.close()

    print(f"총 {len(rows)}개 패턴 처리 중...")
    ok = err = 0
    for pid, name, desc, code in rows:
        try:
            path = make_pattern_file(pid, name, desc, code or "")
            ok += 1
            print(f"  [{ok:3d}] {name}.py ({path.stat().st_size} bytes)")
        except Exception as e:
            err += 1
            print(f"  [ERR] {name}: {e}")

    print(f"\n완료: {ok} 생성, {err} 실패")
    print(f"출력 폴더: {PATTERNS_DIR}")


if __name__ == "__main__":
    main()
