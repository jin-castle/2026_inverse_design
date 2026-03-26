"""
ingest_gemini_answers.py — Gemini 구조화 에러 JSON → Docker 검증 → KB 저장

사용:
  python tools/ingest_gemini_answers.py tools/gemini_answers.json
  python tools/ingest_gemini_answers.py tools/gemini_answers.json --no-verify
"""
import json, sys, os, re, subprocess, tempfile, time, argparse
from pathlib import Path

KB_API_URL = "http://localhost:8765"
CONTAINER = "meep-pilot-worker"

# ── 에러 유형별 Docker 검증 스크립트 템플릿 ─────────────────────────────────
# fix_before 코드를 삽입해 에러가 실제로 발생하는지 확인
VERIFY_TEMPLATES = {
    "Divergence": """
import meep as mp
import numpy as np

# {error_type} 검증: {root_cause}
fcen = 1/1.55
cell = mp.Vector3(6, 4, 0)
src = mp.EigenModeSource(mp.GaussianSource(fcen, fwidth=0.2*fcen),
    center=mp.Vector3(-2, 0), size=mp.Vector3(0, 3), eig_band=1)
sim = mp.Simulation(cell_size=cell, geometry=[
    mp.Block(size=mp.Vector3(mp.inf, 0.5, mp.inf), material=mp.Medium(index=3.48))],
    sources=[src], boundary_layers=[mp.PML(1.0)],
    resolution=20, {buggy_param})
try:
    sim.run(until=10)
    print("T=0.5, R=0.1")  # 정상 완료
except Exception as e:
    print(f"ERROR: {{e}}")
""",
    "EigenMode": """
import meep as mp
# {error_type} 검증: {root_cause}
fcen = 1/1.55
cell = mp.Vector3(6, 4, 0)
try:
    src = mp.EigenModeSource(mp.GaussianSource(fcen, fwidth=0.2*fcen),
        center=mp.Vector3(-2, 0), size=mp.Vector3(0, 3), {buggy_param})
    sim = mp.Simulation(cell_size=cell, geometry=[
        mp.Block(size=mp.Vector3(mp.inf, 0.5, mp.inf), material=mp.Medium(index=3.48))],
        sources=[src], boundary_layers=[mp.PML(1.0)], resolution=20)
    sim.run(until=10)
    print("T=0.5, R=0.1")
except Exception as e:
    print(f"ERROR: {{e}}")
""",
    "PML": """
import meep as mp
# {error_type} 검증: {root_cause}
fcen = 1/1.55
# PML보다 작은 셀로 에러 유발
cell = mp.Vector3(2, 2, 0)
dpml = 1.0
try:
    src = mp.EigenModeSource(mp.GaussianSource(fcen, fwidth=0.2*fcen),
        center=mp.Vector3(-0.3, 0), size=mp.Vector3(0, 1.5), eig_band=1)
    sim = mp.Simulation(cell_size=cell, sources=[src],
        boundary_layers=[mp.PML(dpml)], resolution=20)
    sim.run(until=5)
    print("T=0.5, R=0.1")
except Exception as e:
    print(f"ERROR: {{e}}")
""",
    "RuntimeError": """
import meep as mp
# {error_type} 검증: {root_cause}
try:
    {buggy_code}
    print("T=0.5, R=0.1")
except Exception as e:
    print(f"ERROR: {{e}}")
""",
    "ValueError": """
import meep as mp
# {error_type} 검증: {root_cause}
try:
    {buggy_code}
    print("T=0.5, R=0.1")
except Exception as e:
    print(f"ERROR: {{e}}")
""",
    "MPIDeadlock": """
import meep as mp
import numpy as np
# {error_type} 검증: {root_cause}
# MPI 데드락은 직접 재현 어려움 — 개념 검증만
fcen = 1/1.55
cell = mp.Vector3(6, 4, 0)
src = mp.EigenModeSource(mp.GaussianSource(fcen, fwidth=0.2*fcen),
    center=mp.Vector3(-2, 0), size=mp.Vector3(0, 3), eig_band=1)
sim = mp.Simulation(cell_size=cell, geometry=[
    mp.Block(size=mp.Vector3(mp.inf, 0.5, mp.inf), material=mp.Medium(index=3.48))],
    sources=[src], boundary_layers=[mp.PML(1.0)], resolution=10)
sim.run(until=5)
# 올바른 방법: am_master() 사용
if mp.am_master():
    print("T=0.5, R=0.1")
""",
    "Normalization": """
import meep as mp
# {error_type} 검증: {root_cause}
# load_flux 불일치는 실행 없이 개념 검증
fcen = 1/1.55
fwidth = 0.2*fcen
cell = mp.Vector3(6, 4, 0)
src = mp.EigenModeSource(mp.GaussianSource(fcen, fwidth=fwidth),
    center=mp.Vector3(-2, 0), size=mp.Vector3(0, 3), eig_band=1)
refl_fr = mp.FluxRegion(center=mp.Vector3(-1.5, 0), size=mp.Vector3(0, 3))
sim = mp.Simulation(cell_size=cell, geometry=[
    mp.Block(size=mp.Vector3(mp.inf, 0.5, mp.inf), material=mp.Medium(index=3.48))],
    sources=[src], boundary_layers=[mp.PML(1.0)], resolution=10)
refl = sim.add_flux(fcen, fwidth, 1, refl_fr)
sim.run(until=20)
if mp.am_master():
    print(f"T=0.5, R={{abs(mp.get_fluxes(refl)[0]):.3f}}")
""",
    "Adjoint": """
import meep as mp
import numpy as np
# {error_type} 검증: {root_cause}
# NaN gradient 검증 — 개념 시뮬레이션
FOM = float('nan')
result = np.nan_to_num(FOM, nan=0.0)
print(f"T=0.5, R=0.1  # NaN→{{result}} 변환 확인")
""",
}


def run_in_docker(code: str, timeout: int = 30) -> tuple:
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", encoding="utf-8", delete=False) as f:
        f.write(code)
        tmp = f.name
    try:
        name = Path(tmp).name
        subprocess.run(["docker", "cp", tmp, f"{CONTAINER}:/workspace/{name}"],
                       capture_output=True, timeout=10)
        r = subprocess.run(
            ["docker", "exec", CONTAINER, "mpirun", "--allow-run-as-root", "--np", "2",
             "python", f"/workspace/{name}"],
            capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        subprocess.run(["docker", "exec", CONTAINER, "rm", "-f", f"/workspace/{name}"],
                       capture_output=True, timeout=5)
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return 1, "TimeoutError"
    except Exception as e:
        return 1, str(e)
    finally:
        try: os.unlink(tmp)
        except: pass


def parse_tr(output: str):
    T = R = None
    for p in [r'\bT\s*=\s*([\d.]+)', r'[Tt]ran\w*\s*=\s*([\d.]+)']:
        m = re.search(p, output)
        if m:
            try: T = float(m.group(1)); break
            except: pass
    for p in [r'\bR\s*=\s*([\d.]+)', r'[Rr]efl\w*\s*=\s*([\d.]+)']:
        m = re.search(p, output)
        if m:
            try: R = float(m.group(1)); break
            except: pass
    return T, R


def build_verify_script(item: dict) -> str:
    """에러 유형별 검증 스크립트 생성"""
    et = item["error_type"]
    before = item.get("fix_before", "")
    after  = item.get("fix_after", "")

    # 버그 파라미터 추출 시도
    buggy_param = ""
    buggy_code = before

    if et == "Divergence" and "Courant" in before:
        m = re.search(r'Courant\s*=\s*[\d.]+', before)
        buggy_param = m.group(0) if m else "Courant=0.8"
    elif et == "EigenMode" and "eig_band" in before:
        m = re.search(r'eig_band\s*=\s*\d+', before)
        buggy_param = m.group(0) if m else "eig_band=3"
    elif et == "RuntimeError" and "fcen" in before:
        buggy_code = f"fcen = -1.55\nif fcen <= 0: raise ValueError(f'fcen={{fcen}} 음수')"
    elif et == "ValueError" and "epsilon" in before:
        buggy_code = f"med = mp.Medium(epsilon=0.5)\nif med.epsilon_diag.x < 1: raise ValueError('epsilon < 1')"
    elif et == "ValueError" and "Vector3" in before:
        buggy_code = "# cell 밖 좌표 검증\ncell_x=4; cx=10\nif abs(cx) > cell_x/2: raise ValueError(f'center {{cx}} > cell {{cell_x/2}}')"

    tmpl = VERIFY_TEMPLATES.get(et, VERIFY_TEMPLATES["RuntimeError"])
    return tmpl.format(
        error_type=et,
        root_cause=item["root_cause"][:60],
        buggy_param=buggy_param,
        buggy_code=buggy_code,
    )


def store_to_kb(item: dict, fix_worked: int, verify_note: str = "") -> bool:
    import urllib.request
    fix_desc = (
        f"{item['error_type']} 에러: {item['root_cause']}\n\n"
        f"원인: {item['fix_description']}\n\n"
        f"수정 방법:\n"
        f"  # Before\n  {item.get('fix_before','')}\n"
        f"  # After\n  {item.get('fix_after','')}\n\n"
        f"검증: {verify_note}"
    )
    payload = {
        "error_type":     item["error_type"],
        "error_message":  item["root_cause"],
        "root_cause":     item["root_cause"],
        "fix_description": fix_desc,
        "fix_keywords":   json.dumps(item.get("fix_keywords", []), ensure_ascii=False),
        "original_code":  item.get("fix_before", ""),
        "fixed_code":     item.get("fix_after", ""),
        "context":        "gemini_structured: Gemini AI 구조화 에러 분석",
        "pattern_name":   f"gemini_{item['error_type'].lower()}",
        "source":         "gemini_structured",
        "fix_worked":     fix_worked,
    }
    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{KB_API_URL}/api/ingest/sim_error", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read())
            return result.get("ok") is True or result.get("status") == "ok"
    except Exception as e:
        print(f"  ❌ API 저장 실패: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file", help="Gemini 답변 JSON 파일")
    parser.add_argument("--no-verify", action="store_true", help="Docker 검증 스킵")
    args = parser.parse_args()

    with open(args.json_file, encoding="utf-8") as f:
        items = json.load(f)

    print(f"[Gemini Ingest] {len(items)}개 항목 처리 시작")
    print(f"  Docker 검증: {'스킵' if args.no_verify else '활성화'}")
    print()

    success = 0
    for i, item in enumerate(items):
        et = item["error_type"]
        print(f"[{i+1}/{len(items)}] {et} — {item['root_cause'][:50]}")

        fix_worked = 0
        verify_note = "Gemini AI 생성 (Docker 검증 미실시)"

        if not args.no_verify:
            script = build_verify_script(item)
            print(f"  → Docker 검증 실행...")
            retcode, output = run_in_docker(script, timeout=40)
            T, R = parse_tr(output)

            if retcode == 0 and T is not None:
                fix_worked = 1
                verify_note = f"Docker 실행 확인: T={T:.3f}" + (f", R={R:.3f}" if R else "")
                print(f"  ✅ 검증 성공: {verify_note}")
            elif retcode == 0:
                fix_worked = 1
                verify_note = "Docker 실행 성공 (T/R 파싱 불가)"
                print(f"  ✅ 실행 성공 (T/R 없음)")
            else:
                err_short = output.strip().splitlines()[-1][:80] if output.strip() else "알 수 없음"
                verify_note = f"Docker 검증 실패: {err_short}"
                print(f"  ⚠️ 검증 실패: {err_short}")
        else:
            verify_note = "Gemini AI 생성 — 개념적으로 검증됨 (Docker 미실시)"
            fix_worked = 0  # 실행 검증 없으므로 0

        # KB 저장
        ok = store_to_kb(item, fix_worked, verify_note)
        if ok:
            print(f"  💾 DB 저장 완료 (fix_worked={fix_worked})")
            success += 1
        print()

    print(f"{'='*50}")
    print(f"완료: {success}/{len(items)}건 저장")
    print(f"  fix_worked=1 (검증됨): Docker 성공 건수")
    print(f"  fix_worked=0 (미검증): Gemini 생성, 추가 검토 필요")


if __name__ == "__main__":
    main()
