#!/usr/bin/env python3
"""
MEEP-KB Examples 자동 실행 스크립트 (subprocess 격리 + API 기반)

각 예제를 별도 subprocess로 실행 → 크래시해도 상위 프로세스 유지
plt.show() + plt.savefig() 모두 후킹하여 이미지 캡처

실행:
  python3 run_examples.py [--meep-only] [--plt-only] [--only-pending]
                          [--start N] [--end N] [--timeout 60]
"""
import os, sys, json, time, argparse, re, datetime, urllib.request, tempfile
import subprocess
from pathlib import Path

KB_API_URL  = os.environ.get("KB_API_URL", "http://meep-kb-meep-kb-1:7860")
WORKER_SCRIPT = Path("/tmp/_run_single.py")   # 각 예제 실행용 임시 스크립트

# ── 인자 파싱 ─────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--start",        type=int, default=0)
parser.add_argument("--end",          type=int, default=None)
parser.add_argument("--timeout",      type=int, default=60)
parser.add_argument("--batch",        type=int, default=20)
parser.add_argument("--meep-only",    action="store_true")
parser.add_argument("--plt-only",     action="store_true")
parser.add_argument("--retry-failed", action="store_true")
parser.add_argument("--only-pending", action="store_true")
parser.add_argument("--dry-run",      action="store_true")
args = parser.parse_args()

# ── 단일 예제 실행 Worker 스크립트 생성 ──────────────────────────────────────
WORKER_CODE = r'''
import sys, os, json, base64, re, io, contextlib, datetime
from pathlib import Path

# ── matplotlib headless ──
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.pyplot as _plt

RESULTS_DIR = Path(os.environ.get("RESULTS_DIR", "/tmp/kb_results"))
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

example_id = int(sys.argv[1])
out_json   = sys.argv[2]
code       = sys.stdin.read()

_saved_figs = []

# plt.show() 후킹
def _hook_show(*a, **kw):
    for fn in _plt.get_fignums():
        _saved_figs.append(_plt.figure(fn))
_plt.show = _hook_show

# plt.savefig() 후킹 — 원본 저장 + 캡처 목록에도 추가
_orig_savefig = _plt.savefig
def _hook_savefig(fname, *a, **kw):
    # 원본 파일도 저장
    _orig_savefig(fname, *a, **kw)
    # 현재 fig 캡처 목록에 추가 (중복 방지)
    fig = _plt.gcf()
    if fig not in _saved_figs:
        _saved_figs.append(fig)
_plt.savefig = _hook_savefig

# Figure.savefig 후킹
import matplotlib.figure as _mfig
_orig_fig_savefig = _mfig.Figure.savefig
def _hook_fig_savefig(self, fname, *a, **kw):
    _orig_fig_savefig(self, fname, *a, **kw)
    if self not in _saved_figs:
        _saved_figs.append(self)
_mfig.Figure.savefig = _hook_fig_savefig

# IPython magic 제거
code = code.replace("%matplotlib inline",   "# %matplotlib inline")
code = code.replace("%matplotlib notebook", "# %matplotlib notebook")
code = re.sub(r"^%\w.*$", "# magic", code, flags=re.MULTILINE)
code = re.sub(r"^!.*$",   "# shell", code, flags=re.MULTILINE)

ns = {"__name__": "__main__", "plt": plt}
stdout_buf = io.StringIO()
stderr_buf = io.StringIO()
status, tb_str = "success", ""
t0 = datetime.datetime.now().isoformat()

import traceback
try:
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        exec(compile(code, f"<ex{example_id}>", "exec"), ns)
except SystemExit:
    pass  # 예제가 sys.exit() 호출하는 경우
except Exception:
    status  = "failed"
    tb_str  = traceback.format_exc()

# 남은 open figure도 모두 수집
for fn in _plt.get_fignums():
    fig = _plt.figure(fn)
    if fig not in _saved_figs:
        _saved_figs.append(fig)

# 이미지 저장 + base64 인코딩
img_b64_list = []
for i, fig in enumerate(_saved_figs):
    img_name = f"example_{example_id}_{i:02d}.png"
    img_path = RESULTS_DIR / img_name
    try:
        fig.savefig(str(img_path), dpi=100, bbox_inches="tight", facecolor="white")
        with open(img_path, "rb") as f:
            img_b64_list.append(base64.b64encode(f.read()).decode())
    except Exception as e:
        pass
    _plt.close(fig)
_plt.close("all")

combined = stdout_buf.getvalue()
if stderr_buf.getvalue(): combined += "\n--- stderr ---\n" + stderr_buf.getvalue()
if tb_str:                combined += "\n--- traceback ---\n" + tb_str

result = {
    "status":    status,
    "img_b64":   img_b64_list,
    "stdout":    combined[:5000],
    "run_time":  0,
    "executed_at": t0,
}

with open(out_json, "w") as f:
    json.dump(result, f)
'''

WORKER_SCRIPT.write_text(WORKER_CODE)


# ── subprocess 실행 ────────────────────────────────────────────────────────────
def run_example_isolated(code: str, example_id: int) -> dict:
    """별도 프로세스로 코드 실행 → 크래시해도 부모 프로세스 안전"""
    out_file = f"/tmp/kb_result_{example_id}.json"
    t_start  = time.time()

    try:
        proc = subprocess.run(
            [sys.executable, str(WORKER_SCRIPT), str(example_id), out_file],
            input=code, capture_output=True, text=True,
            timeout=args.timeout,
        )
        run_time = time.time() - t_start

        # 결과 파일 읽기
        if Path(out_file).exists():
            with open(out_file) as f:
                result = json.load(f)
            Path(out_file).unlink(missing_ok=True)
            result["run_time"] = run_time
            return result

        # 결과 파일 없음 = 프로세스 크래시
        return {
            "status": "failed",
            "img_b64": [],
            "stdout": (proc.stdout + proc.stderr)[:3000] or "Process crashed (no output)",
            "run_time": run_time,
            "executed_at": datetime.datetime.now().isoformat(),
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "img_b64": [],
            "stdout": f"TimeoutExpired: > {args.timeout}s",
            "run_time": args.timeout,
            "executed_at": datetime.datetime.now().isoformat(),
        }


# ── API로 결과 전송 ────────────────────────────────────────────────────────────
def post_result(example_id: int, result: dict) -> bool:
    payload = json.dumps({
        "example_id":         example_id,
        "result_images_b64":  result["img_b64"],
        "result_stdout":      result["stdout"],
        "result_run_time":    result["run_time"],
        "result_executed_at": result.get("executed_at", ""),
        "result_status":      result["status"],
    }).encode()
    req = urllib.request.Request(
        f"{KB_API_URL}/api/ingest/result",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            r = json.loads(resp.read())
        return r.get("ok", False)
    except Exception as e:
        print(f"    [API ERR] {e}")
        return False


# ── 예제 로드 ─────────────────────────────────────────────────────────────────
def load_examples() -> list:
    req = urllib.request.Request(
        f"{KB_API_URL}/api/examples/list",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"API load failed: {e}"); sys.exit(1)


def should_run(ex: dict) -> bool:
    code   = ex.get("code", "")
    status = ex.get("result_status", "pending")
    if len(code.strip()) < 30:              return False
    if not args.retry_failed and status == "success": return False
    if args.only_pending and status != "pending":     return False
    if args.meep_only and "import meep" not in code:  return False
    if args.plt_only  and "plt." not in code and "matplotlib" not in code: return False
    return True


# ── 메인 ─────────────────────────────────────────────────────────────────────
def main():
    print("예제 목록 로딩...", flush=True)
    examples = load_examples()
    total    = len(examples)
    start    = args.start
    end      = args.end if args.end is not None else total
    to_run   = [ex for ex in examples[start:end] if should_run(ex)]

    print(f"\n{'='*62}")
    print(f"MEEP-KB Examples 자동 실행 (subprocess 격리)")
    print(f"  전체: {total} | 범위: {start}~{end} | 실행: {len(to_run)}")
    print(f"  meep-only={args.meep_only} | plt-only={args.plt_only} | timeout={args.timeout}s")
    print(f"{'='*62}\n")

    if args.dry_run:
        for ex in to_run:
            m = "✅" if "import meep" in ex.get("code","") else "  "
            p = "📊" if "plt."       in ex.get("code","") else "  "
            print(f"  [{ex['id']:4d}] {m}{p} {ex['title'][:65]}")
        return

    ok_cnt = fail_cnt = timeout_cnt = 0

    for idx, ex in enumerate(to_run):
        eid, title, code = ex["id"], ex["title"][:55], ex.get("code","")
        print(f"[{idx+1:3d}/{len(to_run)}] #{eid} {title}", flush=True)

        result  = run_example_isolated(code, eid)
        sym = {"success":"✅","failed":"❌","timeout":"⏱️"}.get(result["status"],"?")
        imgs = len(result["img_b64"])
        print(f"  {sym} {result['status']:8s} | {result['run_time']:5.1f}s | imgs={imgs}", flush=True)

        ok = post_result(eid, result)
        print(f"  API: {'✅ 저장' if ok else '❌ 실패'}", flush=True)

        if   result["status"] == "success": ok_cnt     += 1
        elif result["status"] == "timeout": timeout_cnt += 1
        else:                               fail_cnt   += 1

        if (idx + 1) % args.batch == 0:
            print(f"\n  ── 배치 완료 {idx+1}/{len(to_run)} (✅{ok_cnt} ❌{fail_cnt} ⏱️{timeout_cnt}) ──\n", flush=True)
            time.sleep(0.3)

    print(f"\n{'='*62}")
    print(f"완료! ✅{ok_cnt} ❌{fail_cnt} ⏱️{timeout_cnt}")
    print(f"{'='*62}")


if __name__ == "__main__":
    main()
