#!/usr/bin/env python3
"""
result_status='error'인 concepts의 demo_code를 강화된 프롬프트로 재생성.
Usage: python -u -X utf8 tools/regenerate_demo_codes.py [--name FluxRegion]
"""
import os, sys, re, json, sqlite3, time, argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"

PROMPT_TEMPLATE = """당신은 MEEP 1.31.0 FDTD 전문가입니다.
MEEP의 "{name}" ({name_ko}) 개념의 데모 코드를 작성해주세요.

카테고리: {category} | 난이도: {difficulty}
데모 힌트: {demo_hint}

## MEEP 1.31.0 정확한 API (반드시 이것만 사용)

```python
# 시뮬레이션 생성
sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(w, mp.inf), center=mp.Vector3(), material=mp.Medium(epsilon=12))],
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez, center=mp.Vector3(-0.5*sx+dpml))],
    resolution=10
)

# 플럭스 모니터 (T/R 측정)
trans = sim.add_flux(fcen, df, nfreq, mp.FluxRegion(center=mp.Vector3(x), size=mp.Vector3(0, sy)))

# DFT 필드 모니터
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1, where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx, sy)))

# 시뮬레이션 실행
sim.run(until_after_sources=mp.stop_when_fields_decayed(50, mp.Ez, mp.Vector3(0.5*sx-dpml), 1e-9))
# 또는
sim.run(until=200)
# 또는
sim.run(mp.at_every(10, mp.output_efield_z), until=100)

# 필드 배열 추출
ez_data = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx, sy))

# DFT 필드 추출
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

# 플럭스 데이터
flux_freqs = mp.get_flux_freqs(trans)
trans_flux = mp.get_fluxes(trans)

# 에너지 모니터
energy_mon = sim.add_energy(fcen, df, nfreq, mp.EnergyRegion(center=mp.Vector3(), size=mp.Vector3(sx, sy)))

# 대칭 (symmetries 인자로 전달)
sym = [mp.Mirror(mp.Y)]
sim = mp.Simulation(..., symmetries=sym, ...)

# k_point (주기 경계)
sim = mp.Simulation(..., k_point=mp.Vector3(0.5), ...)

# Harminv (공진 모드 분석)
sim.run(mp.after_sources(mp.Harminv(mp.Ez, mp.Vector3(), fcen, df)), until_after_sources=300)

# near2far
n2f = sim.add_near2far(fcen, 0, 1, mp.Near2FarRegion(center=mp.Vector3(), size=mp.Vector3(0, sy)))
ff = sim.get_farfield(n2f, mp.Vector3(1000, 0))

# LDOS
sim.run(mp.dft_ldos(fcen, 0, 1), until_after_sources=mp.stop_when_fields_decayed(50, mp.Ez, mp.Vector3(), 1e-9))
ldos_data = mp.get_ldos_data()

# EigenModeSource
src = mp.EigenModeSource(mp.GaussianSource(fcen, fwidth=df), center=mp.Vector3(-0.5*sx+dpml),
    size=mp.Vector3(0, sy), eig_band=1, eig_parity=mp.ODD_Z)

# MaterialGrid (adjoint 없이 단독 사용 가능)
design_region = mp.MaterialGrid(mp.Vector3(Nx, Ny), mp.air, mp.Medium(epsilon=12),
    weights=np.ones((Nx*Ny,))*0.5)

# get_eigenmode_coefficients
res = sim.get_eigenmode_coefficients(trans, [1], eig_parity=mp.ODD_Z)
alpha = res.alpha[0, 0, 0]  # 진폭
```

## 절대 규칙
1. **완전히 독립 실행 가능** — import부터 plt.savefig까지 그 자체로 실행 가능
2. **import meep.adjoint 절대 금지** (autograd 없음, ModuleNotFoundError 발생)
3. **mp.ModeSolver 사용 금지** (MPB 미설치)
4. **mp.get_dft_array** 대신 **sim.get_dft_array** 사용
5. **한글 변수명 금지** — 변수명은 모두 영어로
6. **matplotlib.use('Agg')** 반드시 맨 앞에
7. **plt.savefig('output.png')** 로 저장 (plt.show() 금지)
8. **resolution=10** 이하 (빠른 실행)
9. **100줄 이하**
10. **모든 변수를 사용 전 반드시 정의** (NameError 방지)
11. **Simulation(courant=...)** 사용 금지 — courant 파라미터 없음
12. **실제 sim.run()까지 완성** — 중간에 끊기는 코드 금지

## 출력 형식 (이 형식 그대로)

DEMO_CODE:
```python
import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# 완전한 독립 실행 코드

plt.savefig('output.png')
print("Done")
```

DEMO_DESCRIPTION:
[코드가 보여주는 것 한국어로 2~3문장]
"""


def extract_code_and_desc(text: str) -> tuple:
    """raw LLM 응답에서 demo_code와 demo_description 추출."""
    # DEMO_CODE 섹션
    m = re.search(r'DEMO_CODE:\s*\n```python\n(.*?)```', text, re.DOTALL)
    if not m:
        m = re.search(r'```python\n(.*?)```', text, re.DOTALL)
    code = m.group(1).strip() if m else ""

    # DEMO_DESCRIPTION 섹션
    m2 = re.search(r'DEMO_DESCRIPTION:\s*\n(.*?)(?:\n##|\Z)', text, re.DOTALL)
    desc = m2.group(1).strip() if m2 else ""

    return code, desc


def load_targets(name_filter=None):
    conn = sqlite3.connect(str(DB_PATH))
    if name_filter:
        rows = conn.execute(
            "SELECT name, name_ko, category, difficulty, demo_description FROM concepts WHERE name=?",
            (name_filter,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT name, name_ko, category, difficulty, demo_description FROM concepts "
            "WHERE result_status='pending' "
            "ORDER BY difficulty, category, name"
        ).fetchall()
    conn.close()
    return [{"name": r[0], "name_ko": r[1], "category": r[2],
             "difficulty": r[3], "demo_hint": r[4] or r[0] + " 기본 예제"} for r in rows]


def save_demo_code(conn, name, code, desc):
    conn.execute(
        "UPDATE concepts SET demo_code=?, demo_description=?, "
        "result_status='pending', updated_at=CURRENT_TIMESTAMP WHERE name=?",
        (code, desc, name)
    )
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="특정 개념만 재생성")
    parser.add_argument("--all", action="store_true", default=True)
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY 없음"); sys.exit(1)

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    targets = load_targets(args.name)
    print(f"재생성 대상: {len(targets)}개\n")

    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    success = 0

    for i, concept in enumerate(targets, 1):
        name = concept["name"]
        prompt = PROMPT_TEMPLATE.format(**concept)

        print(f"[{i}/{len(targets)}] 🔄 {name} ({concept['name_ko']})...")
        try:
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2500,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text
            code, desc = extract_code_and_desc(text)

            if not code or len(code) < 30:
                print(f"  ⚠️  코드 짧음 ({len(code)}자)")
            elif "import meep" not in code:
                print(f"  ⚠️  meep import 없음")
            else:
                save_demo_code(conn, name, code, desc)
                print(f"  ✅ 저장 ({len(code)}자)")
                success += 1

            time.sleep(0.5)

        except Exception as e:
            print(f"  ❌ 실패: {e}")

    conn.close()
    print(f"\n=== 완료: {success}/{len(targets)} ===")


if __name__ == "__main__":
    main()
