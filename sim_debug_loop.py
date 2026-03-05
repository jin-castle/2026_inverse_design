#!/usr/bin/env python3
"""
sim_debug_loop.py - MEEP 시뮬레이션 자율 디버깅 루프
===============================================================
사용법:
    python sim_debug_loop.py my_sim.py --stage stage0 --max-iter 5 --procs 4

동작:
    1. 시뮬레이션 실행 (MPI 지원)
    2. 에러 감지 → meep-kb /api/diagnose 검색
    3. KB에 해결책 있으면 적용 / 없으면 LLM 분석
    4. 에러+해결책 meep-kb에 저장 (다음번 활용)
    5. 수정된 코드로 재실행 → 최대 N회 반복
"""

import os, sys, re, subprocess, shutil, json, time, argparse, requests
from pathlib import Path
from datetime import datetime
from typing import Optional

KB_API = os.environ.get("MEEP_KB_API", "http://localhost:8765")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MAX_ITERATIONS = 5
TIMEOUT_SEC = 600  # 시뮬레이션당 최대 10분


# ── 1. 시뮬레이션 실행 ────────────────────────────────────────────────────────

def run_simulation(script_path: str, procs: int = 1, timeout: int = TIMEOUT_SEC) -> dict:
    """MPI로 시뮬레이션 실행, 결과 반환"""
    if procs > 1:
        cmd = ["mpirun", "-np", str(procs), "python3", script_path]
    else:
        cmd = ["python3", script_path]

    print(f"[run] {' '.join(cmd)}")
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=timeout, cwd=str(Path(script_path).parent)
        )
        elapsed = time.time() - t0
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],  # 마지막 4000자
            "stderr": result.stderr[-4000:],
            "elapsed": elapsed,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "returncode": -1,
                "stdout": "", "stderr": f"TIMEOUT after {timeout}s", "elapsed": timeout}
    except Exception as e:
        return {"success": False, "returncode": -1,
                "stdout": "", "stderr": str(e), "elapsed": 0}


# ── 2. 에러 파싱 ─────────────────────────────────────────────────────────────

def extract_error(run_result: dict) -> str:
    """stderr + stdout에서 에러 메시지 추출"""
    stderr = run_result.get("stderr", "")
    stdout = run_result.get("stdout", "")
    combined = stderr + "\n" + stdout

    # Traceback 추출
    tb_match = re.search(r"(Traceback.*?)(?=\n\n|\Z)", combined, re.DOTALL)
    if tb_match:
        return tb_match.group(1)[:2000]

    # 그냥 마지막 에러 줄
    lines = [l for l in combined.split("\n") if "Error" in l or "error" in l or "Exception" in l]
    return "\n".join(lines[-5:]) if lines else combined[-500:]


# ── 3. meep-kb 진단 ──────────────────────────────────────────────────────────

def query_kb_diagnose(code: str, error: str) -> Optional[dict]:
    """meep-kb /api/diagnose 호출 → 알려진 해결책 반환"""
    try:
        resp = requests.post(f"{KB_API}/api/diagnose",
                             json={"code": code[:2000], "error": error[:2000], "n": 5},
                             timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[kb] diagnose 실패: {e}")
    return None


# ── 4. LLM으로 코드 수정 ─────────────────────────────────────────────────────

def llm_fix_code(code: str, error: str, kb_context: str = "") -> Optional[dict]:
    """Claude API로 코드 수정안 생성"""
    if not ANTHROPIC_API_KEY:
        print("[llm] ANTHROPIC_API_KEY 없음, LLM 수정 건너뜀")
        return None

    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    system = """You are an expert MEEP FDTD simulation debugger.
Given buggy MEEP Python code and its error, output a fixed version.
Platform: SOI 220nm, silicon (n=3.48), SiO2 (n=1.44), wavelength 1550nm.
Respond ONLY with JSON: {"fixed_code": "...", "explanation": "...", "cause": "..."}"""

    user_parts = []
    if kb_context:
        user_parts.append(f"Known similar errors from knowledge base:\n{kb_context}\n---")
    user_parts.append(f"Code:\n```python\n{code[:3000]}\n```\n\nError:\n```\n{error[:1500]}\n```")

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": "\n".join(user_parts)}]
        )
        text = msg.content[0].text.strip()
        # JSON 추출
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"[llm] 실패: {e}")
    return None


# ── 5. meep-kb에 에러+해결책 저장 ────────────────────────────────────────────

def store_to_kb(error: str, solution: str, cause: str = "",
                category: str = "runtime", stage: str = "", code: str = ""):
    """에러+해결책을 meep-kb에 저장"""
    try:
        resp = requests.post(f"{KB_API}/api/ingest/error", json={
            "error_msg": error[:2000],
            "solution": solution[:2000],
            "cause": cause[:500],
            "category": category,
            "stage": stage,
            "code": code[:500],
            "source_type": "simulation_log",
        }, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"[kb] 저장 완료: id={data.get('sqlite_id')}, chroma={data.get('chroma_ok')}")
        else:
            print(f"[kb] 저장 실패: {resp.status_code}")
    except Exception as e:
        print(f"[kb] 저장 에러: {e}")


# ── 메인 루프 ─────────────────────────────────────────────────────────────────

def debug_loop(script_path: str, stage: str = "unknown",
               max_iter: int = MAX_ITERATIONS, procs: int = 1):

    script_path = str(Path(script_path).resolve())
    original_code = Path(script_path).read_text()
    current_code = original_code

    print(f"\n{'='*60}")
    print(f"[loop] 시작: {script_path}")
    print(f"[loop] stage={stage}, max_iter={max_iter}, procs={procs}")
    print(f"{'='*60}\n")

    history = []

    for iteration in range(1, max_iter + 1):
        print(f"\n── Iteration {iteration}/{max_iter} ──")

        # 1. 실행
        result = run_simulation(script_path, procs=procs)

        if result["success"]:
            print(f"[loop] ✅ 성공! ({result['elapsed']:.1f}s)")
            # 성공 패턴도 저장 (선택)
            if history:
                last = history[-1]
                store_to_kb(
                    error=last["error"],
                    solution=f"[RESOLVED in {iteration} iterations] " + last.get("fix_explanation", ""),
                    cause=last.get("cause", ""),
                    category=last.get("category", "runtime"),
                    stage=stage,
                    code=last.get("code_snippet", ""),
                )
            return {"success": True, "iterations": iteration, "history": history}

        # 2. 에러 추출
        error_msg = extract_error(result)
        print(f"[error] {error_msg[:300]}")

        # 3. meep-kb 진단
        kb_result = query_kb_diagnose(current_code, error_msg)
        kb_context = ""
        kb_solution = None

        if kb_result:
            # KB에서 관련 해결책 추출
            results = kb_result.get("results", [])
            good_results = [r for r in results if r.get("solution") and r.get("score", 0) > 0.6]
            if good_results:
                best = good_results[0]
                kb_solution = best.get("solution", "")
                kb_context = "\n".join([
                    f"[{r['category']}] Cause: {r.get('cause','?')} → Solution: {r.get('solution','?')}"
                    for r in good_results[:3]
                ])
                print(f"[kb] KB 해결책 발견 (score={best.get('score',0):.2f}): {kb_solution[:100]}")

        # 4. 코드 수정 (LLM)
        fix = llm_fix_code(current_code, error_msg, kb_context=kb_context)

        if fix and fix.get("fixed_code"):
            new_code = fix["fixed_code"]
            explanation = fix.get("explanation", "LLM fix")
            cause = fix.get("cause", "")
            print(f"[llm] 수정 완료: {explanation[:100]}")
        else:
            print("[warn] 코드 수정 실패, 반복 중단")
            break

        # 5. 에러+수정 저장 (다음번 활용)
        # 카테고리 추정
        cat = "runtime"
        if any(k in error_msg for k in ["diverge", "NaN", "inf", "CFL"]): cat = "convergence"
        elif any(k in error_msg for k in ["adjoint", "OptimizationProblem"]): cat = "adjoint"
        elif any(k in error_msg for k in ["EigenMode", "source"]): cat = "source"
        elif any(k in error_msg for k in ["PML", "boundary"]): cat = "geometry"

        store_to_kb(error_msg, explanation, cause=cause,
                    category=cat, stage=stage, code=current_code[:500])

        history.append({
            "iteration": iteration,
            "error": error_msg,
            "fix_explanation": explanation,
            "cause": cause,
            "category": cat,
            "code_snippet": current_code[:200],
        })

        # 6. 수정된 코드 파일에 쓰기
        Path(script_path).write_text(new_code)
        current_code = new_code

    print(f"\n[loop] ❌ 최대 반복({max_iter}) 도달, 마지막 에러 확인 필요")
    return {"success": False, "iterations": max_iter, "history": history}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MEEP 자율 디버깅 루프")
    parser.add_argument("script", help="실행할 MEEP Python 스크립트")
    parser.add_argument("--stage", default="unknown", help="시뮬레이션 단계 (stage0, stage1 ...)")
    parser.add_argument("--max-iter", type=int, default=5, help="최대 반복 횟수")
    parser.add_argument("--procs", type=int, default=1, help="MPI 프로세스 수")
    parser.add_argument("--kb-api", default="http://localhost:8765", help="meep-kb API URL")
    args = parser.parse_args()

    KB_API = args.kb_api
    result = debug_loop(args.script, stage=args.stage,
                        max_iter=args.max_iter, procs=args.procs)

    print(f"\n{'='*60}")
    print(f"결과: {'SUCCESS' if result['success'] else 'FAILED'}")
    print(f"반복: {result['iterations']}회")
    print(f"{'='*60}")
    sys.exit(0 if result["success"] else 1)
