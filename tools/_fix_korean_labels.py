#!/usr/bin/env python3
"""
demo_code 내 matplotlib 텍스트의 한글을 영어로 치환 후 재실행.
title(), xlabel(), ylabel(), label=, text(), annotate(), legend() 등 대상.
"""
import re, sqlite3, subprocess, tempfile
from pathlib import Path
import sys
sys.path.insert(0, 'tools')
from run_concept_demos import preprocess_code

DB_PATH = Path("db/knowledge.db")
RESULTS_DIR = Path("db/results")

# ── 한글 → 영어 치환 사전 ──────────────────────────────────────────────────
KO_TO_EN = {
    # 물리량
    "시간 (MEEP 단위)": "Time (MEEP units)",
    "시간 (meep 단위)": "Time (MEEP units)",
    "시간(MEEP 단위)": "Time (MEEP units)",
    "시간": "Time",
    "|Ez| 진폭 (log 스케일)": "|Ez| amplitude (log scale)",
    "|Ez| 진폭 (log)": "|Ez| amplitude (log)",
    "Ez 진폭": "Ez amplitude",
    "Ez 진폭 (log 스케일)": "Ez amplitude (log scale)",
    "주파수 (MEEP 단위)": "Frequency (MEEP units)",
    "주파수": "Frequency",
    "파장 (μm)": "Wavelength (μm)",
    "파장": "Wavelength",
    "투과율": "Transmittance",
    "반사율": "Reflectance",
    "유전율": "Permittivity",
    "굴절률": "Refractive index",
    "에너지": "Energy",
    "저장 에너지": "Stored energy",
    "전기장 에너지": "Electric energy",
    "자기장 에너지": "Magnetic energy",
    "총 에너지": "Total energy",
    "진폭": "Amplitude",
    "강도": "Intensity",
    "위상": "Phase",

    # 라벨
    "유전율 분포": "Permittivity distribution",
    "구조 (유전율 ε)": "Structure (permittivity ε)",
    "구조": "Structure",
    "Ez 순시 필드": "Ez snapshot",
    "Ez 필드 분포": "Ez field distribution",
    "Ez 필드 스냅샷": "Ez field snapshot",
    "|Ez|² DFT (주파수 도메인)": "|Ez|² DFT (frequency domain)",
    "|Ez|² DFT": "|Ez|² DFT",
    "DFT 필드": "DFT field",
    "시간도메인": "Time domain",
    "주파수도메인": "Frequency domain",
    "공진 주파수": "Resonant frequency",
    "공진": "Resonance",
    "Q factor": "Q factor",
    "모드 프로파일": "Mode profile",
    "TE0 모드": "TE0 mode",
    "TE1 모드": "TE1 mode",

    # 라벨(단위)
    "ε_r": "ε_r",
    "격자 해상도": "Grid resolution",
    "해상도": "Resolution",
    "파워": "Power",
    "모드 파워": "Mode power",

    # 방향/위치
    "중앙": "Center",
    "경계": "Boundary",
    "소스": "Source",
    "점 소스": "Point source",
    "점 소스 위치": "Point source",
    "PML 경계 근처": "Near PML boundary",
    "PML 직전": "Just before PML",
    "PML 흡수층": "PML absorbing layer",
    "PML 흡수\\n→ 빠른 감쇠": "PML absorption\\n→ fast decay",
    "PML이 파동을 반사 없이 흡수하는 것을 보여줌": "PML absorbs wave without reflection",

    # 타이틀
    "시간에 따른 Ez 진폭 감쇠": "Ez amplitude decay over time",
    "시간에 따른 Ez 진폭 감쇠\\nPML이 파동을 반사 없이 흡수": "Ez decay - PML absorbs without reflection",
    "at_every(0.5, record)로 기록한 Ez 시계열 — PML이 파동을 흡수하면 빠르게 감쇠":
        "Ez time series recorded by at_every(0.5) — fast decay as PML absorbs wave",
    "수평+수직 Block으로 L자형": "L-shaped: horizontal + vertical Block",
    "굴곡부를 통한 모드 전파": "Mode propagation through bend",
    "ContinuousSource 정상상태": "ContinuousSource steady state",
    "회색=PML 흡수층, 파동이 사방으로 전파": "Gray=PML, wave propagates outward",
    "공식 MEEP 튜토리얼 기반\\n(ε=12, λ=2√11 μm, ContinuousSource)":
        "Based on official MEEP tutorial (ε=12, λ=2√11 μm, ContinuousSource)",

    # 기타 공통
    "정상상태": "Steady state",
    "수렴": "Convergence",
    "이진화": "Binarization",
    "설계 변수": "Design variable",
    "설계 영역": "Design region",
    "초기 구조": "Initial structure",
    "최적화": "Optimization",
    "수렴 곡선": "Convergence curve",
    "반복 횟수": "Iteration",
    "목적 함수": "Objective function",
    "FOM": "FOM",
    "그래디언트": "Gradient",
    "필터": "Filter",
    "투영": "Projection",
    "파이프라인": "Pipeline",
    "원시 입력": "Raw input",
    "처리 결과": "Processed",
    "비교": "Comparison",
    "전파": "Propagation",
    "흡수": "Absorption",

    # suptitle 패턴들
    "점 소스 펄스 전파 & 흡수 시뮬레이션": "Point source pulse propagation & PML absorption",
    "점 소스에서 퍼지는\\nGaussian pulse의 시간 단계별 Ez 스냅샷":
        "Ez snapshots of Gaussian pulse from point source",
    "시간 단계별 스냅샷": "Time step snapshots",
    "pulse 방출 구간": "Pulse emission period",
    "중앙 Ez(t) — 소스 위치": "Center Ez(t) — source",
    "PML 직전 Ez(t)": "Near PML Ez(t)",
    "|Ez| (log)": "|Ez| (log)",

    # 범례 텍스트
    "수평 구간": "Horizontal section",
    "수직 구간": "Vertical section",
    "굴곡부": "Bend section",
}

def translate(code: str) -> str:
    """matplotlib 문자열 내 한글을 영어로 치환."""
    result = code
    for ko, en in KO_TO_EN.items():
        result = result.replace(ko, en)

    # 남은 한글 문자가 포함된 문자열 리터럴 감지 및 경고
    # (완전 제거보다 주석으로 남기는 방식)
    hangul_in_str = re.findall(r"['\"][^'\"]*[\u3131-\uD7A3][^'\"]*['\"]", result)
    if hangul_in_str:
        # 추가 치환: 남은 한글 포함 짧은 label들을 영어 대체
        for s in hangul_in_str:
            inner = s[1:-1]  # 따옴표 제거
            # 짧으면 그냥 공백 처리
            safe = re.sub(r'[\u3131-\uD7A3]+', '', inner).strip() or inner[:20]
            result = result.replace(s, s[0] + safe + s[-1])

    return result

def has_hangul(text: str) -> bool:
    return bool(re.search(r'[\u3131-\uD7A3\uAC00-\uD7A3]', text))

def run_docker(name, code, timeout=180):
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    processed = preprocess_code(code, name)
    tmp = Path(tempfile.gettempdir()) / f"_ko_{safe}.py"
    tmp.write_text(processed, encoding="utf-8")
    subprocess.run(["docker", "cp", str(tmp), f"meep-pilot-worker:/tmp/_ko_{safe}.py"],
                   capture_output=True)
    r = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "python3", f"/tmp/_ko_{safe}.py"],
        capture_output=True, text=True, timeout=timeout
    )
    tmp.unlink(missing_ok=True)
    return r

def save_img(conn, name, code):
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    output_path = f"/tmp/concept_{safe}.png"
    img_local = RESULTS_DIR / f"concept_{safe}.png"
    cp = subprocess.run(
        ["docker", "cp", f"meep-pilot-worker:{output_path}", str(img_local)],
        capture_output=True, timeout=10
    )
    # output.png 폴백
    if cp.returncode != 0 or not img_local.exists() or img_local.stat().st_size < 3000:
        subprocess.run(
            ["docker", "exec", "meep-pilot-worker", "sh", "-c", f"cp output.png {output_path} 2>/dev/null || true"],
            capture_output=True, timeout=5
        )
        subprocess.run(
            ["docker", "cp", f"meep-pilot-worker:{output_path}", str(img_local)],
            capture_output=True, timeout=10
        )
    size = img_local.stat().st_size // 1024 if img_local.exists() else 0
    if size > 3:
        conn.execute(
            "UPDATE concepts SET demo_code=?, result_images=?, updated_at=CURRENT_TIMESTAMP WHERE name=?",
            (code, f"/static/results/concept_{safe}.png", name)
        )
        conn.commit()
    return size

# ── 메인 ─────────────────────────────────────────────────────────────────────
conn = sqlite3.connect(str(DB_PATH), timeout=15)
rows = conn.execute("SELECT name, demo_code FROM concepts ORDER BY name").fetchall()

needs_fix = [(n, c) for n, c in rows if c and has_hangul(c)]
print(f"한글 포함 개념: {len(needs_fix)}개\n")

db_updated = 0
rerun_needed = []

for name, code in needs_fix:
    new_code = translate(code)
    still_hangul = has_hangul(new_code)
    changed = new_code != code

    if changed:
        conn.execute("UPDATE concepts SET demo_code=? WHERE name=?", (new_code, name))
        conn.commit()
        db_updated += 1
        rerun_needed.append((name, new_code))
        print(f"  {'⚠️' if still_hangul else '✅'} {name}: {'일부 한글 잔존' if still_hangul else '번역 완료'}")

conn.close()
print(f"\nDB 업데이트: {db_updated}개")
print(f"재실행 대상: {len(rerun_needed)}개\n")

# ── 재실행 ────────────────────────────────────────────────────────────────────
conn = sqlite3.connect(str(DB_PATH), timeout=15)
ok = 0
for name, code in rerun_needed:
    print(f"  [{ok+1}/{len(rerun_needed)}] {name}...", end=" ", flush=True)
    try:
        r = run_docker(name, code, timeout=180)
        if r.returncode == 0:
            size = save_img(conn, name, code)
            print(f"✅ {size}KB")
            ok += 1
        else:
            err = (r.stderr or r.stdout).splitlines()[-2:]
            print(f"❌ {err}")
    except Exception as e:
        print(f"❌ timeout/error: {e}")

conn.close()
print(f"\n=== 완료: {ok}/{len(rerun_needed)} ===")
