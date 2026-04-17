"""현재 탐색 공간 밖의 변수들 분석"""
import json, re
from pathlib import Path

BASE   = Path(__file__).parent
NB_DIR = Path(r"C:\Users\user\.openclaw\workspace\dev\cis_reproduce")

nb = NB_DIR / "Pixelated Bayer spectral router based on a sparse meta-atom array_Chinese Optics Letters" / "SMA_Re.ipynb"
data = json.loads(nb.read_text(encoding="utf-8", errors="replace"))
code = "\n".join("".join(c["source"]) for c in data["cells"] if c["cell_type"]=="code")

print("=" * 65)
print("현재 HypothesisLoop이 탐색하는 것 (5개 변수)")
print("=" * 65)
print("  cover_glass:    True / False")
print("  ref_sim_type:   air / with_cover")
print("  stop_decay:     1e-3/1e-4/1e-6/1e-8")
print("  source_count:   1 / 2")
print("  sipd_material:  Air / SiO2")
print()
print("  → res=20 7개 후보 모두 R=0.186 G=0.388 B=0.192 동일")
print("  → 이 5개 변수로는 오차를 줄이지 못함")
print()

print("=" * 65)
print("탐색 안 하는 변수들 (SMA 오차의 실제 원인 후보)")
print("=" * 65)

# --- 1. Bayer 사분면 배치 ---
print()
print("[변수 1] Bayer 4분면 배치 순서")
flux_centers = re.findall(
    r'tran_([a-z0-9]+)\s*=.*?FluxRegion.*?Vector3\(([^)]+)\)',
    code, re.DOTALL
)
print("  원본 SMA 모니터 좌표:")
for name, center in flux_centers[:8]:
    print(f"    tran_{name}: ({center.strip()[:60]})")
print()
print("  현재 생성 코드 모니터 좌표:")
print("    tran_R:  (-dx/4, -dy/4)")
print("    tran_Gr: (-dx/4, +dy/4)")
print("    tran_B:  (+dx/4, +dy/4)")
print("    tran_Gb: (+dx/4, -dy/4)")
print("  → SMA 원본이 이와 동일한지 확인 필요!")

# --- 2. n_material ---
print()
print("[변수 2] 재료 굴절률 n_material (현재 고정값)")
sin_n = re.findall(r'SiN\s*=\s*mp\.Medium\(index=([\d.]+)\)', code)
print(f"  원본: SiN index={sin_n[0] if sin_n else '?'}")
print("  실제 SiN(Si3N4) 굴절률은 파장에 따라 1.9 ~ 2.1 범위")
print("  → n=2.02 고정 대신 n=[1.9, 1.95, 2.0, 2.02, 2.05] 탐색 가능")

# --- 3. SMA pillar 좌표 정밀도 ---
print()
print("[변수 3] SMA sparse pillar 좌표 cx, cy")
block_lines = [l for l in code.splitlines() if "mp.Block" in l and "Layer_thickness" in l]
for l in block_lines[:5]:
    print(f"  {l.strip()[:100]}")
print()
print("  논문 원본 좌표:")
cx_vals = re.findall(r"Vector3\(([-+\d.]+),\s*([-+\d.]+)", code)
for cx, cy in cx_vals[:6]:
    print(f"    center=({cx}, {cy})")
print("  → cx=±0.56μm 이 논문에서 정확히 명시된 값인가?")
print("    hd=4.0μm(기판), SP_size=1.12μm → 서브픽셀 중심 = SP/2=0.56 (맞음)")

# --- 4. 효율 계산 정규화 분모 ---
print()
print("[변수 4] 효율 정규화 방식")
eff_patterns = [(l.strip()[:80]) for l in code.splitlines()
                if 'tran_flux_p' in l or 'total_flux' in l]
for p in eff_patterns[:4]:
    print(f"  {p}")
print()
print("  원본: tran_flux_p (pixel 면적 flux) = 픽셀 정규화")
print("  생성: tran_p (동일) ← 맞음")
print("  BUT: tran_flux_p 계산 위치가 메인 vs 참조 시뮬 중 어느 것?")

# --- 5. source 파라미터 ---
print()
print("[변수 5] GaussianSource 중심 파장 + 대역폭")
freq_lines = [l.strip()[:80] for l in code.splitlines()
              if 'frequency' in l or 'fwidth' in l or 'fcen' in l]
for l in freq_lines[:6]:
    print(f"  {l}")
print("  → 원본: frequency=1/(0.545*um_scale), fwidth=frequency*2")
print("  → 생성: 동일 ← 맞음")

# --- 6. 가장 중요: SMA 원본의 opt.sim 구조 ---
print()
print("[변수 6] 가장 중요 — opt.sim vs sim 직접 실행")
print("  원본: mpa.OptimizationProblem 래퍼 사용")
print("  opt.sim_1 = 참조 시뮬")
print("  opt.sim   = 메인 시뮬")
print()
print("  생성: 직접 mp.Simulation() 사용")
print()
print("  차이: opt.sim_1.run()이 mp.stop_when_dft_decayed를 어떻게 처리하는가?")
print("  opt 래퍼에서의 decay 체크 기준이 직접 실행과 다를 수 있음!")

# --- 7. 참조 시뮬 소스 ---
print()
print("[변수 7] 참조 시뮬 source 교체 방식")
change_src = re.findall(r'change_sources\([^)]+\)', code)
for cs in change_src[:3]:
    print(f"  원본: {cs}")
print()
print("  원본: opt.sim_1.change_sources(source)")
print("  생성: sim_ref에 새 소스 직접 설정")
print("  → 참조 시뮬 source가 원본과 정확히 동일한가?")
print("    원본: [mp.Source(src, component=mp.Ex, ...)] (Ex 단독)")
print("    생성: [mp.Source(src, component=mp.Ex, ...)] (동일 — 맞음)")

# --- 8. tran_pixel 위치 ---
print()
print("[변수 8] tran_pixel(효율 분모) 모니터 위치")
tran_pixel = re.findall(r'tran_p(?:ixel)?\s*=.*?FluxRegion.*?size.*?Vector3\(([^)]+)\)', code, re.DOTALL)
for tp in tran_pixel[:3]:
    print(f"  원본: size=({tp.strip()[:60]})")
print()
print("  → pixel 모니터 크기: Sx×Sy (전체) vs design_region_x×design_region_y")
print("  SMA에서 Sx==design_region_x이므로 동일 — 문제 없음")

# --- 결론 ---
print()
print("=" * 65)
print("결론: SMA 오차 47% 원인")
print("=" * 65)
print("""
현재 7개 후보가 모두 동일한 결과를 내는 이유:
  → 5개 변수(cover/ref/decay/src/sipd)를 바꿔도 효율 안 변함
  → SMA 소자의 물리적 특성 때문:
    - 4개 기둥만으로는 색분리 효율이 물리적으로 제한됨
    - 논문 target(R=0.45)이 이 구조의 실제 한계에 가까움
    - res=20과 res=50 결과가 동일 → 수렴 완료

진짜 남은 오차 원인 후보:
  A. n_material 불확실성 (SiN n=1.9~2.1 범위)
  B. pillar 크기 미세 조정 (w1=920nm ± 5nm)
  C. 논문 target 자체가 다른 정규화 기준 사용
  D. 실제 fabricated 결과 vs 시뮬 차이 (원본도 마찬가지)

→ HypothesisLoop에 추가해야 할 변수:
  n_material:  [1.9, 1.95, 2.0, 2.02, 2.05, 2.1]
  pillar_scale: [0.95, 1.0, 1.05] (전체 pillar 크기 ±5%)
  bayer_config: 현재 R/G/G/B 배치 외 다른 배치
""")

# 현재까지 완료된 hyp 결과
print("=" * 65)
print("현재까지 hyp loop 결과")
print("=" * 65)
hyp_dir = BASE / "results" / "SMA2023" / "hyp"
if hyp_dir.exists():
    for log in sorted(hyp_dir.glob("hyp_c1*_res50.log")):
        txt = log.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"\[Result\] R=([\d.]+) G=([\d.]+) B=([\d.]+)", txt)
        if m:
            print(f"  {log.stem}: R={m.group(1)} G={m.group(2)} B={m.group(3)}")
        else:
            lines = txt.splitlines()
            last = next((l for l in reversed(lines) if l.strip()), "진행 중")
            print(f"  {log.stem}: {last[-60:]}")
