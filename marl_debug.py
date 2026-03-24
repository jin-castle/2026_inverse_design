#!/usr/bin/env python3
"""
MARL (MEEP Autonomous Research Loop) Debugger
=============================================
흐름: 실행 → 오류 파싱 → 카테고리 분류 → meep-kb 검색 → 해결책 제안

사용법:
  python marl_debug.py script.py
  python marl_debug.py script.py --procs 10 --max-iter 3 --auto-fix
  python marl_debug.py script.py --output report.json
"""

import os, sys, re, json, time, subprocess, argparse
from pathlib import Path
from typing import Optional
import requests

KB_API = os.environ.get("MEEP_KB_API", "http://localhost:8765")
DEFAULT_PYTHON = os.environ.get("MEEP_PYTHON", "python3")
DEFAULT_MPIRUN = os.environ.get("MEEP_MPIRUN", "mpirun")
TIMEOUT_SEC = 600

# ── 오류 카테고리 분류표 (Jin 요청) ────────────────────────────────────────
MARL_CATEGORIES = {
    "env_setup": {
        "label": "환경 설정 문제",
        "keywords": ["ImportError", "ModuleNotFoundError", "conda", "mpirun", "No module named",
                     "command not found", "Permission denied", "FileNotFoundError"],
    },
    "source_config": {
        "label": "소스 설정 문제",
        "keywords": ["EigenModeSource", "GaussianSource", "ContinuousSource", "eigenmode",
                     "kpoint", "eig_band", "eig_parity", "add_source", "component",
                     "fwidth", "wavelength", "frequency"],
    },
    "geometry": {
        "label": "구조(Geometry) 문제",
        "keywords": ["Block", "Cylinder", "Prism", "geometry", "overlap", "center", "size",
                     "material", "epsilon", "index", "Medium", "out of cell"],
    },
    "boundary": {
        "label": "경계 조건 문제",
        "keywords": ["PML", "boundary_layers", "k_point", "periodic", "Bloch",
                     "perfectly matched layer", "absorbing"],
    },
    "numerics": {
        "label": "수치 설정 문제",
        "keywords": ["Divergence", "diverged", "NaN", "nan", "inf", "Inf",
                     "blowing up", "resolution", "timestep", "courant", "unstable"],
    },
    "monitor": {
        "label": "모니터/측정 문제",
        "keywords": ["FluxRegion", "add_flux", "get_fluxes", "DFT", "add_dft_fields",
                     "add_mode_monitor", "EigenmodeCoefficient", "monitor", "flux"],
    },
    "adjoint": {
        "label": "Adjoint 최적화 문제",
        "keywords": ["adjoint", "OptimizationProblem", "MaterialGrid", "gradient",
                     "mpa.", "autograd", "nlopt", "DesignRegion"],
    },
    "normalization": {
        "label": "정규화/기준값 문제",
        "keywords": ["normalization", "reference", "input_flux", "S11", "S21",
                     "efficiency", "transmittance", "negative", "> 1.0", "< 0"],
    },
    "mpi": {
        "label": "MPI 병렬 처리 문제",
        "keywords": ["MPIError", "MPI_Abort", "mpi4py", "rank", "comm",
                     "OMP_NUM_THREADS", "btl_vader", "slot"],
    },
}


def classify_error(error_msg: str, code: str = "") -> dict:
    """오류 메시지 + 코드로 카테고리 분류"""
    combined = (error_msg + "\n" + code).lower()

    scores = {}
    for cat, info in MARL_CATEGORIES.items():
        score = sum(1 for kw in info["keywords"] if kw.lower() in combined)
        if score > 0:
            scores[cat] = score

    if scores:
        best_cat = max(scores, key=scores.get)
        return {
            "category": best_cat,
            "category_label": MARL_CATEGORIES[best_cat]["label"],
            "all_matches": scores,
        }
    return {"category": "unknown", "category_label": "기타/미분류", "all_matches": {}}


def parse_error(stderr: str, stdout: str) -> dict:
    """stderr+stdout에서 오류 정보 추출"""
    combined = stderr + "\n" + stdout

    # 에러 타입 분류
    ERROR_PATTERNS = [
        (r"Simulation diverged|diverged|blowing up", "Divergence"),
        (r"PML|perfectly matched layer", "PML"),
        (r"EigenMode|eigenmode|add_eigenmode", "EigenMode"),
        (r"Adjoint|adjoint|OptimizationProblem", "Adjoint"),
        (r"MPI_Abort|MPIError|mpi4py", "MPIError"),
        (r"NaN|nan(?!\w)|inf(?!\w)", "NumericalError"),
        (r"ValueError: (.*)", "ValueError"),
        (r"RuntimeError: (.*)", "RuntimeError"),
        (r"ImportError|ModuleNotFoundError", "ImportError"),
        (r"AttributeError: (.*)", "AttributeError"),
        (r"MemoryError|out of memory", "MemoryError"),
        (r"segmentation fault", "SegFault"),
    ]

    error_type = "Unknown"
    for pattern, etype in ERROR_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            error_type = etype
            break

    # Traceback 추출
    tb_match = re.search(r"(Traceback \(most recent call last\).*?)(?=\n\n|\Z)", combined, re.DOTALL)
    traceback_str = tb_match.group(1)[:2000] if tb_match else ""

    # 마지막 에러 라인
    error_lines = [l for l in combined.split("\n")
                   if any(x in l for x in ["Error", "error", "Exception", "diverged", "Abort", "NaN", "inf"])]
    last_error = error_lines[-1] if error_lines else combined[-300:]

    # MEEP 키워드
    meep_kws = re.findall(r'mp\.\w+|meep\.\w+|mpirun|mpiexec', combined)

    return {
        "error_type": error_type,
        "last_error": last_error.strip()[:300],
        "traceback": traceback_str,
        "meep_keywords": list(set(meep_kws))[:10],
        "raw": combined[-2000:],
    }


def run_simulation(script_path: str, procs: int = 1,
                   python_path: str = DEFAULT_PYTHON,
                   mpirun_path: str = DEFAULT_MPIRUN) -> dict:
    """시뮬레이션 실행"""
    if procs > 1:
        cmd = [mpirun_path, "-np", str(procs), python_path, script_path]
    else:
        cmd = [python_path, script_path]

    print(f"  실행: {' '.join(cmd)}")
    t0 = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=TIMEOUT_SEC,
                                cwd=str(Path(script_path).parent))
        elapsed = time.time() - t0
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-5000:],
            "stderr": result.stderr[-5000:],
            "elapsed": round(elapsed, 1),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "returncode": -1,
                "stdout": "", "stderr": f"TIMEOUT ({TIMEOUT_SEC}s 초과)", "elapsed": TIMEOUT_SEC}
    except FileNotFoundError as e:
        return {"success": False, "returncode": -1,
                "stdout": "", "stderr": f"실행 파일 없음: {e}", "elapsed": 0}


def search_kb(error_msg: str, code: str, error_type: str) -> list:
    """meep-kb /api/diagnose 호출"""
    try:
        resp = requests.post(f"{KB_API}/api/diagnose",
                             json={"code": code[:2000], "error": error_msg[:2000], "n": 5},
                             timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("suggestions", [])
    except Exception as e:
        print(f"  [KB] 연결 실패: {e}")
    return []


def auto_fix_simple(code: str, error_type: str, category: str):
    """규칙 기반 간단 자동 수정 (LLM 없이)"""
    fixed = code
    changes = []

    if category == "numerics" or error_type == "Divergence":
        # resolution 낮으면 올리기
        m = re.search(r'resolution\s*=\s*(\d+)', fixed)
        if m and int(m.group(1)) < 10:
            fixed = re.sub(r'resolution\s*=\s*\d+', f'resolution={int(m.group(1))*4}', fixed)
            changes.append(f"resolution {m.group(1)} → {int(m.group(1))*4}")
        # PML 두께 너무 작으면 올리기
        m2 = re.search(r'PML\s*\(\s*([0-9.]+)\s*\)', fixed)
        if m2 and float(m2.group(1)) < 0.5:
            fixed = re.sub(r'PML\s*\(\s*[0-9.]+\s*\)', 'PML(1.0)', fixed)
            changes.append(f"PML {m2.group(1)} → 1.0")

    if category == "boundary" or error_type == "PML":
        m = re.search(r'PML\s*\(\s*([0-9.]+)\s*\)', fixed)
        if m and float(m.group(1)) < 1.0:
            fixed = re.sub(r'PML\s*\(\s*[0-9.]+\s*\)', 'PML(1.5)', fixed)
            changes.append(f"PML {m.group(1)} → 1.5")

    if changes:
        return fixed, changes
    return None, []


def format_report(iteration: int, parsed: dict, classified: dict, suggestions: list) -> str:
    """진단 리포트 포맷"""
    lines = [
        "",
        "━" * 55,
        f"🔍 Iteration {iteration} — 오류 감지",
        "━" * 55,
        f"[오류 유형]  {parsed['error_type']}",
        f"[카테고리]   {classified['category_label']} ({classified['category']})",
        f"[오류 메시지] {parsed['last_error'][:200]}",
    ]

    if parsed.get("traceback"):
        lines += ["", "[Traceback]", parsed["traceback"][-500:]]

    lines += ["", f"📚 meep-kb 검색 결과 ({len(suggestions)}건)", "─" * 45]

    if not suggestions:
        lines.append("  관련 항목 없음 — meep-kb에 데이터 부족")
    else:
        for i, s in enumerate(suggestions[:5], 1):
            title = s.get("title", "")[:60]
            score = s.get("score", 0)
            source = s.get("source", "")
            verified = "✅ 검증됨" if "verified_fix" in source else "📋"
            lines.append(f"\n  {i}. {verified} [{score:.2f}] {title}")
            if s.get("cause"):
                lines.append(f"     원인: {str(s['cause'])[:100]}")
            if s.get("solution"):
                lines.append(f"     해결: {str(s['solution'])[:120]}")

    lines.append("━" * 55)
    return "\n".join(lines)


class MARLDebugger:
    def __init__(self, kb_api: str = KB_API,
                 python_path: str = DEFAULT_PYTHON,
                 mpirun_path: str = DEFAULT_MPIRUN):
        self.kb_api = kb_api
        self.python_path = python_path
        self.mpirun_path = mpirun_path

    def run(self, script_path: str, max_iter: int = 3,
            procs: int = 1, auto_fix: bool = False,
            output_path: Optional[str] = None) -> dict:

        script_path = str(Path(script_path).resolve())
        original_code = Path(script_path).read_text(encoding="utf-8")
        current_code = original_code
        history = []

        print(f"\n{'='*55}")
        print(f"  MARL Debugger — {Path(script_path).name}")
        print(f"  max_iter={max_iter}  procs={procs}  auto_fix={auto_fix}")
        print(f"{'='*55}")

        for iteration in range(1, max_iter + 1):
            print(f"\n[Iter {iteration}/{max_iter}] 시뮬레이션 실행 중...")

            result = run_simulation(script_path, procs=procs,
                                    python_path=self.python_path,
                                    mpirun_path=self.mpirun_path)

            if result["success"]:
                print(f"\n✅ 시뮬레이션 성공! ({result['elapsed']}s)")
                record = {"iteration": iteration, "status": "success",
                          "elapsed": result["elapsed"]}
                history.append(record)
                break

            # 오류 파싱
            parsed = parse_error(result["stderr"], result["stdout"])
            classified = classify_error(parsed["raw"], current_code)

            # KB 검색
            print(f"  → 오류: {parsed['error_type']} / {classified['category_label']}")
            print(f"  → meep-kb 검색 중...")
            suggestions = search_kb(parsed["raw"], current_code, parsed["error_type"])

            # 리포트 출력
            report = format_report(iteration, parsed, classified, suggestions)
            print(report)

            record = {
                "iteration": iteration,
                "status": "error",
                "error_type": parsed["error_type"],
                "category": classified["category"],
                "category_label": classified["category_label"],
                "suggestions_count": len(suggestions),
                "elapsed": result["elapsed"],
            }

            # 자동 수정 시도
            if auto_fix and iteration < max_iter:
                fixed_code, changes = auto_fix_simple(
                    current_code, parsed["error_type"], classified["category"])
                if fixed_code and changes:
                    print(f"\n🔧 자동 수정 적용:")
                    for c in changes:
                        print(f"   - {c}")
                    current_code = fixed_code
                    Path(script_path).write_text(current_code, encoding="utf-8")
                    record["auto_fix"] = changes
                else:
                    print(f"\n⚠️  규칙 기반 자동 수정 없음. 수동 수정 필요.")
                    break
            else:
                if iteration == max_iter:
                    print(f"\n⚠️  max_iter 도달. 디버깅 종료.")
                break

            history.append(record)

        final = {
            "script": script_path,
            "iterations": len(history),
            "final_status": history[-1]["status"] if history else "unknown",
            "history": history,
        }

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(final, f, ensure_ascii=False, indent=2)
            print(f"\n📄 리포트 저장: {output_path}")

        return final


def main():
    parser = argparse.ArgumentParser(description="MARL MEEP Debugger")
    parser.add_argument("script", help="MEEP 스크립트 경로")
    parser.add_argument("--procs", type=int, default=1, help="MPI 프로세스 수")
    parser.add_argument("--max-iter", type=int, default=3, help="최대 반복 횟수")
    parser.add_argument("--auto-fix", action="store_true", help="규칙 기반 자동 수정 활성화")
    parser.add_argument("--output", help="결과 JSON 저장 경로")
    parser.add_argument("--kb-api", default=KB_API, help="meep-kb API URL")
    parser.add_argument("--python", default=DEFAULT_PYTHON, help="Python 실행 경로")
    parser.add_argument("--mpirun", default=DEFAULT_MPIRUN, help="mpirun 경로")
    args = parser.parse_args()

    debugger = MARLDebugger(
        kb_api=args.kb_api,
        python_path=args.python,
        mpirun_path=args.mpirun,
    )
    result = debugger.run(
        script_path=args.script,
        max_iter=args.max_iter,
        procs=args.procs,
        auto_fix=args.auto_fix,
        output_path=args.output,
    )

    status = result["final_status"]
    icon = "✅" if status == "success" else "❌"
    print(f"\n{icon} 최종 상태: {status} ({result['iterations']}회 시도)")


if __name__ == "__main__":
    main()
