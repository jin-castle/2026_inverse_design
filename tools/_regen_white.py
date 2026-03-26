#!/usr/bin/env python3
"""하얀 이미지 10개 — 완전한 실행 코드로 재생성 후 실행."""
import os, sys, re, sqlite3, time, subprocess, tempfile
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"
RESULTS_DIR = Path(__file__).parent.parent / "db" / "results"

WHITE_NAMES = [
    "Block", "Cylinder", "PML", "Medium", "mpi", "taper",
    "eig_band", "eig_parity", "LorentzianSusceptibility", "OptimizationProblem"
]

SYSTEM = """당신은 MEEP 1.31.0 FDTD 전문가입니다.
아래 개념의 완전한 독립 실행 데모 코드를 작성하세요.

핵심 요구사항:
- 실제 MEEP 시뮬레이션을 실행하고 그 결과(유전율 분포, 필드, 스펙트럼, 구조도 등)를 시각화
- plt.figure() → 데이터 플롯 → plt.savefig('/tmp/concept_NAME.png') 순서로 반드시 실행
- sim.plot2D() 또는 sim.get_array() + imshow 또는 plt.plot()으로 의미있는 그래프 생성
- 빈 흰색 캔버스가 되면 안 됨 — 반드시 눈에 보이는 내용이 있어야 함
- matplotlib.use('Agg'), import meep as mp 맨 앞에
- resolution=10, 작은 시뮬레이션 (빠른 실행)
- 100줄 이내

출력 형식:
DEMO_CODE:
```python
코드
```
DEMO_DESCRIPTION:
(한국어 설명)"""

PROMPTS = {
    "Block": "Si 직사각형 도파관 Block을 포함한 SOI 단면을 정의하고, sim.plot2D()로 유전율 분포를 시각화하세요.",
    "Cylinder": "포토닉 결정의 Si 원통형 결함(Cylinder)을 포함한 2D 구조를 정의하고, 유전율 분포 imshow로 시각화하세요.",
    "PML": "PML 경계가 적용된 도파관에서 점 소스의 Ez 필드를 시뮬레이션하고, 필드 분포를 imshow로 시각화하세요. PML 영역이 필드를 흡수하는 것을 보여주세요.",
    "Medium": "Si(n=3.48)와 SiO2(n=1.44) Medium으로 구성된 SOI 도파관 단면을 정의하고, get_array(Dielectric)로 유전율 분포를 시각화하세요.",
    "mpi": "MPI 병렬 정보를 시각화: 직선 도파관 시뮬레이션 후 Ez 필드 분포와 함께 프로세스 정보를 텍스트로 표시하세요. am_master()로 rank-0만 출력.",
    "taper": "선형 테이퍼 도파관(0.4μm→2.0μm, 길이 5μm)을 Prism으로 정의하고 시뮬레이션 후 Ez 필드 분포와 투과율을 플롯하세요.",
    "eig_band": "EigenModeSource의 eig_band=1(TE0) vs eig_band=2(TE1) 모드 프로파일을 측정하고 subplot으로 비교 플롯하세요.",
    "eig_parity": "ODD_Z(TE 편광) vs EVEN_Z(TM 편광) EigenModeSource로 도파관을 여기하고, 각각의 Ez, Hz 필드 패턴을 subplot으로 비교 시각화하세요.",
    "LorentzianSusceptibility": "로렌츠 분산 매질의 투과율 스펙트럼을 시뮬레이션하고, 공진 주파수 근방에서 T vs frequency 그래프를 그리세요.",
    "OptimizationProblem": "mpa.OptimizationProblem을 사용해 간단한 최적화 문제(빔 스플리터 FOM)를 설정하고, 초기 구조의 유전율 분포와 FOM 값을 표시하세요. mpa = meep.adjoint",
}

sys.path.insert(0, str(Path(__file__).parent))
from run_concept_demos import preprocess_code

def generate(name, api_key):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"개념: {name}\n요구사항: {PROMPTS[name]}"}],
    )
    text = msg.content[0].text
    m = re.search(r'DEMO_CODE:\s*\n```python\n(.*?)```', text, re.DOTALL)
    if not m:
        m = re.search(r'```python\n(.*?)```', text, re.DOTALL)
    code = m.group(1).strip() if m else ""
    m2 = re.search(r'DEMO_DESCRIPTION:\s*\n(.*?)$', text, re.DOTALL)
    desc = m2.group(1).strip()[:500] if m2 else ""
    return code, desc

def run_docker(name, code):
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    processed = preprocess_code(code, name)
    # savefig 경로 강제 지정
    output_path = f"/tmp/concept_{safe}.png"

    tmp = Path(tempfile.gettempdir()) / f"_regen_{safe}.py"
    tmp.write_text(processed, encoding="utf-8")
    subprocess.run(["docker", "cp", str(tmp), f"meep-pilot-worker:/tmp/_regen_{safe}.py"], capture_output=True)
    result = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "python3", f"/tmp/_regen_{safe}.py"],
        capture_output=True, text=True, timeout=120
    )
    tmp.unlink(missing_ok=True)

    # 이미지 확인
    img_local = RESULTS_DIR / f"concept_{safe}.png"
    cp = subprocess.run(
        ["docker", "cp", f"meep-pilot-worker:{output_path}", str(img_local)],
        capture_output=True, timeout=10
    )
    img_ok = cp.returncode == 0 and img_local.exists() and img_local.stat().st_size > 3000
    return result, img_ok, img_local

def save_db(name, code, desc, img_ok):
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    img_url = f"/static/results/concept_{safe}.png" if img_ok else None
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    conn.execute(
        "UPDATE concepts SET demo_code=?, demo_description=?, result_images=?, updated_at=CURRENT_TIMESTAMP WHERE name=?",
        (code, desc, img_url, name)
    )
    conn.commit()
    conn.close()

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY 없음"); sys.exit(1)

    success = 0
    for name in WHITE_NAMES:
        print(f"\n🔄 {name}")
        for attempt in range(2):
            print(f"  {'1차' if attempt==0 else '2차 재시도'} 생성...")
            code, desc = generate(name, api_key)
            if not code or len(code) < 50:
                print(f"  ❌ 코드 생성 실패"); continue

            result, img_ok, img_path = run_docker(name, code)
            print(f"  exit={result.returncode}, img={'✅' if img_ok else '❌'} ({img_path.stat().st_size//1024 if img_path.exists() else 0}KB)")

            if img_ok:
                save_db(name, code, desc, True)
                print(f"  ✅ 완료!")
                success += 1
                break
            else:
                # 실패 원인 피드백
                err = (result.stderr or result.stdout)[-300:]
                if attempt == 0:
                    PROMPTS[name] += f"\n\n이전 실패 원인: {err[:200]}\n반드시 plt.figure() 후 데이터를 실제로 그린 뒤 savefig 호출하세요."
                else:
                    save_db(name, code, desc, False)
                    print(f"  ⚠️  2차도 실패, 코드만 저장")
            time.sleep(0.5)

    print(f"\n=== 완료: {success}/{len(WHITE_NAMES)} ===")
    # 최종 확인
    conn = sqlite3.connect(str(DB_PATH))
    n = conn.execute("SELECT COUNT(*) FROM concepts WHERE result_images IS NOT NULL AND result_images!=''").fetchone()[0]
    conn.close()
    print(f"이미지 있는 개념: {n}/56")

if __name__ == "__main__":
    main()
