#!/usr/bin/env python3
"""
실패한 5개 개념 + adjoint 재활성화 후 재생성 + 재실행.
autograd 설치 완료로 meep.adjoint 사용 가능.
"""
import os, sys, re, json, sqlite3, time, subprocess, tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"
RESULTS_DIR = Path(__file__).parent.parent / "db" / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ── MEEP 1.31.0 정확한 API 참고 (검증된 것만) ──────────────────────────────

CONCEPTS = [
    {
        "name": "MPB",
        "name_ko": "포토닉 밴드 구조 계산",
        "hint": """
MPB는 meep.adjoint가 아니라 meep 자체의 run_k_points를 쓰거나, 단순 Harminv로 공진 모드를 찾는 방식 사용.
mp.ModeSolver는 없음. 대신 FDTD로 공진 주파수 찾기:
  sim.run(mp.after_sources(mp.Harminv(mp.Ez, pt, fcen, df)), until_after_sources=300)
  harminv_result: list of mp.Harminv objects → .freq, .Q, .amp
실제 MPB 역할 대신: Harminv로 Si 막대의 공진 모드 주파수와 Q factor를 찾는 데모.
"""
    },
    {
        "name": "phase_velocity",
        "name_ko": "위상 속도 및 군속도",
        "hint": """
GaussianSource 사용 시 source 생성은:
  src_cmpt = mp.EigenModeSource(
      mp.GaussianSource(frequency=fcen, fwidth=df),
      center=src_pt, size=mp.Vector3(0, sy),
      eig_band=1, eig_parity=mp.ODD_Z+mp.EVEN_Y
  )
여러 k_point에서 플럭스를 측정해 분산관계 k(ω) 계산.
단, 여러 시뮬레이션 실행보다 단순하게:
  fcen 범위의 GaussianSource → 투과 스펙트럼 → 주파수 vs 플럭스 플롯으로 대체.
"""
    },
    {
        "name": "LDOS",
        "name_ko": "국소 상태 밀도 (Purcell 인자)",
        "hint": """
LDOS 측정 방법 (MEEP 1.31.0):
  sim.run(mp.dft_ldos(fcen, 0, 1), until_after_sources=mp.stop_when_fields_decayed(50, mp.Ez, pt, 1e-9))
  ldos = mp.get_ldos_data()  # 이건 없음!
  
실제 올바른 방법:
  ldos_freqs, ldos_vals = sim.get_ldos_data()  # 이것도 없음
  
MEEP 1.31.0에서 dft_ldos 결과 접근:
  # dft_ldos는 step function으로 사용, 결과는 sim.run 후 직접 접근 불가
  # 대신: 두 시뮬레이션 (진공 vs 구조물)에서 decay rate 비교로 Purcell factor 계산
  # 또는: FluxRegion으로 점 소스 에너지 방출량 비교

가장 단순한 데모:
  진공에서 점 소스 총 방출 에너지 vs 공진기 내 점 소스 총 방출 에너지를 비교.
  각각 sim.add_flux + sim.run + mp.get_fluxes로 측정.
  Purcell factor = flux_cavity / flux_vacuum
"""
    },
    {
        "name": "ring_resonator",
        "name_ko": "링 공진기",
        "hint": """
ring_resonator 데모 - 올바른 방법:
  # 2D 시뮬레이션: 직선 도파관 + 링 공진기 근접 결합
  # 링은 Cylinder (outer) - Cylinder (inner) 조합 사용
  # FluxRegion은 입출력 포트에 배치
  
  geometry = [
      # 직선 도파관
      mp.Block(size=mp.Vector3(sx, w, 0), center=mp.Vector3(), material=Si),
      # 링 (바깥 원통 - 속 원통)
      mp.Cylinder(radius=r+w/2, material=Si),
      mp.Cylinder(radius=r-w/2, material=mp.air),
  ]
  
  # FluxRegion: 입력/출력 포트
  trans_flux = sim.add_flux(fcen, df, nfreq, mp.FluxRegion(center=mp.Vector3(0.4*sx), size=mp.Vector3(0, 2*w)))
  
  sim.run(until_after_sources=mp.stop_when_fields_decayed(50, mp.Ez, mp.Vector3(0.4*sx), 1e-9))
  
  flux = mp.get_fluxes(trans_flux)
  freqs = mp.get_flux_freqs(trans_flux)
"""
    },
    {
        "name": "add_energy",
        "name_ko": "에너지 밀도 모니터",
        "hint": """
add_energy 올바른 사용법 (MEEP 1.31.0):
  # EnergyRegion으로 영역 지정
  energy_mon = sim.add_energy(fcen, df, nfreq,
      mp.EnergyRegion(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
  
  sim.run(until=200)
  
  # 결과 접근
  e_energy = mp.get_electric_energy(energy_mon)   # 전기장 에너지
  m_energy = mp.get_magnetic_energy(energy_mon)   # 자기장 에너지
  total_energy = mp.get_total_energy(energy_mon)  # 총 에너지
  
  # EnergyRegion의 center와 size는 시뮬레이션 영역 내부여야 함 (PML 밖)
"""
    },
]

SYSTEM_PROMPT = """당신은 MEEP 1.31.0 FDTD 전문가입니다.
아래 힌트에 기반해 완전히 독립 실행 가능한 Python 데모 코드를 작성하세요.

## 절대 규칙
1. 완전히 독립 실행 가능 — 파일 하나만 실행하면 됨
2. meep.adjoint (mpa) 사용 가능 — autograd 설치됨
3. mp.ModeSolver 사용 금지 (MPB 미설치)
4. mp.get_ldos_data() 사용 금지 (없음)
5. 한글 변수명 금지
6. matplotlib.use('Agg') 맨 앞에
7. plt.savefig('output.png') 로 저장
8. resolution=10 이하
9. 100줄 이하
10. try-except로 오류 방지

## 출력 형식
DEMO_CODE:
```python
(코드)
```
DEMO_DESCRIPTION:
(설명)
"""

def generate_code(concept: dict, api_key: str) -> tuple:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""개념: {concept['name']} ({concept['name_ko']})

힌트:
{concept['hint']}

위 힌트를 참고해서 MEEP 1.31.0에서 실제로 실행 가능한 완전한 데모 코드를 작성하세요."""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text

    # 코드 추출
    m = re.search(r'DEMO_CODE:\s*\n```python\n(.*?)```', text, re.DOTALL)
    if not m:
        m = re.search(r'```python\n(.*?)```', text, re.DOTALL)
    code = m.group(1).strip() if m else ""

    m2 = re.search(r'DEMO_DESCRIPTION:\s*\n(.*?)$', text, re.DOTALL)
    desc = m2.group(1).strip()[:500] if m2 else ""

    return code, desc


def preprocess_code(code: str, name: str) -> str:
    lines = code.splitlines()
    # adjoint import 제거 (이제 허용하지만 맨 앞 순서 보장)
    # matplotlib.use('Agg') 보장
    has_mpl = any("matplotlib.use" in l for l in lines)
    if not has_mpl:
        lines = ["import matplotlib", "matplotlib.use('Agg')"] + lines
    # import meep 보장
    has_meep = any(re.match(r'^\s*import meep', l) for l in lines)
    if not has_meep:
        idx = next((i for i, l in enumerate(lines) if "matplotlib.use" in l), 0)
        lines.insert(idx + 1, "import meep as mp")
    code = "\n".join(lines)
    code = re.sub(r'\bplt\.show\(\)', 'pass', code)
    return code


def run_in_docker(name: str, code: str) -> dict:
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    tmp = Path(tempfile.gettempdir()) / f"fix5_{safe}.py"
    tmp.write_text(code, encoding="utf-8")

    subprocess.run(["docker", "cp", str(tmp), f"meep-pilot-worker:/tmp/fix5_{safe}.py"],
                   capture_output=True, timeout=15)
    result = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "python3", f"/tmp/fix5_{safe}.py"],
        capture_output=True, text=True, timeout=120
    )
    tmp.unlink(missing_ok=True)

    if result.returncode == 0:
        # 이미지 회수
        img_local = RESULTS_DIR / f"concept_{safe}.png"
        subprocess.run(["docker", "cp", f"meep-pilot-worker:/tmp/concept_{safe}.png", str(img_local)],
                       capture_output=True, timeout=10)
        return {"status": "success", "notes": "OK"}
    else:
        err = (result.stderr or result.stdout)[-400:]
        return {"status": "error", "notes": err}


def save_to_db(conn, name: str, code: str, desc: str, status: str, notes: str):
    conn.execute(
        "UPDATE concepts SET demo_code=?, demo_description=?, result_status=?, "
        "result_stdout=?, updated_at=CURRENT_TIMESTAMP WHERE name=?",
        (code, desc, status, notes, name)
    )
    conn.commit()


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY 없음"); sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    success = 0

    for concept in CONCEPTS:
        name = concept["name"]
        print(f"\n🔄 {name} ({concept['name_ko']})")
        print(f"  Step 1: sonnet으로 코드 재생성...")

        code, desc = generate_code(concept, api_key)
        if not code or len(code) < 50:
            print(f"  ❌ 코드 생성 실패"); continue

        processed = preprocess_code(code, name)
        print(f"  Step 2: Docker 실행 ({len(processed)}자)...")

        result = run_in_docker(name, processed)
        status = result["status"]
        notes = result["notes"]

        save_to_db(conn, name, processed, desc, status, notes)

        if status == "success":
            print(f"  ✅ 성공!")
            success += 1
        else:
            print(f"  ❌ 실패: {notes[:150]}")
            # 한 번 더 시도 — 에러 메시지를 피드백으로 재생성
            print(f"  🔁 에러 피드백으로 재시도...")
            concept["hint"] += f"\n\n이전 실행 오류:\n{notes[:300]}\n위 오류를 반드시 피해서 작성하세요."
            code2, desc2 = generate_code(concept, api_key)
            if code2 and len(code2) > 50:
                processed2 = preprocess_code(code2, name)
                result2 = run_in_docker(name, processed2)
                save_to_db(conn, name, processed2, desc2, result2["status"], result2["notes"])
                if result2["status"] == "success":
                    print(f"  ✅ 재시도 성공!")
                    success += 1
                else:
                    print(f"  ❌ 재시도도 실패: {result2['notes'][:150]}")
            time.sleep(1)

        time.sleep(1)

    conn.close()
    print(f"\n=== 완료: {success}/{len(CONCEPTS)} ===")

    # 최종 현황
    conn2 = sqlite3.connect(str(DB_PATH))
    stats = dict(conn2.execute("SELECT result_status, COUNT(*) FROM concepts GROUP BY result_status").fetchall())
    conn2.close()
    print(f"DB 최종: {stats}")


if __name__ == "__main__":
    main()
