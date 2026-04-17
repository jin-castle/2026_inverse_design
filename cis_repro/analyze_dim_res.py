"""
CIS vs 2D 시뮬레이션 분석
- 8개 논문의 dimensionality, resolution, 실행 시간 분석
- resolution별 복셀 수 + 예상 시간 비교
- 2D 근사 가능성 검토
"""
import json, re
from pathlib import Path

NB_DIR = Path('C:/Users/user/.openclaw/workspace/dev/cis_reproduce')

# ── 8개 논문 분석 ──────────────────────────────────────────────────
rows = []
for nb_file in sorted(NB_DIR.rglob('*.ipynb')):
    try:
        data = json.loads(nb_file.read_text(encoding='utf-8', errors='replace'))
        code = '\n'.join(''.join(c['source']) for c in data['cells'] if c['cell_type']=='code')

        m_res = re.search(r'resolution\s*=\s*(\d+)', code)
        res   = int(m_res.group(1)) if m_res else None

        has_3d = 'mp.Vector3(Sx, Sy, Sz)' in code
        m_sp   = re.search(r'SP_size\s*=\s*([\d.]+)', code)
        m_fl   = re.search(r'FL_thickness\s*=\s*([\d.]+)', code)
        m_lt   = re.search(r'Layer_thickness\s*=\s*([\d.]+)', code)
        m_w    = re.search(r'\bw\s*=\s*(0\.\d+)', code)
        m_d    = re.search(r'D_[RGB]\s*=\s*([\d.]+)', code)

        sp = float(m_sp.group(1)) if m_sp else None
        fl = float(m_fl.group(1)) if m_fl else None
        lt = float(m_lt.group(1)) if m_lt else None
        min_feat = float(m_w.group(1)) if m_w else (float(m_d.group(1)) if m_d else None)

        # 셀 크기 추정
        if sp and fl and lt and res:
            Sx = sp * 2
            Sz_approx = 0.4 + 0.2 + 0.2 + lt + fl + 0.4 + 0.4
            Nvox_3d = int(Sx*res) * int(Sx*res) * int(Sz_approx*res)
            Nvox_2d = int(Sx*res) * int(Sz_approx*res)
            grids = round(min_feat * res, 1) if min_feat else None
        else:
            Nvox_3d = Nvox_2d = grids = None

        rows.append({
            'name': nb_file.name.replace('_Re.ipynb',''),
            'res': res, 'has_3d': has_3d,
            'sp': sp, 'fl': fl, 'lt': lt,
            'min_feat': min_feat,
            'grids': grids,
            'Nvox_3d': Nvox_3d,
            'Nvox_2d': Nvox_2d,
        })
    except Exception:
        pass

# ── 출력 ────────────────────────────────────────────────────────────
print("=" * 80)
print("CIS Color Router 논문 — 시뮬레이션 파라미터 분석")
print("=" * 80)

print(f"\n{'논문':<25} {'res':>4} {'3D':>3} {'SP':>5} {'FL':>5} {'LT':>5} {'min':>6} {'격자':>5} {'복셀_3D':>11} {'복셀_2D':>9}")
print("─" * 80)
for r in rows:
    feat_str = f"{r['min_feat']*1000:.0f}nm" if r['min_feat'] else "—"
    vox3 = f"{r['Nvox_3d']//1000:,}K"  if r['Nvox_3d'] else "—"
    vox2 = f"{r['Nvox_2d']//1000:,}K"  if r['Nvox_2d'] else "—"
    print(f"{r['name'][:24]:<25} {str(r['res'] or '—'):>4} "
          f"{'Y' if r['has_3d'] else 'N':>3} "
          f"{str(r['sp']) if r['sp'] else '—':>5} "
          f"{str(r['fl']) if r['fl'] else '—':>5} "
          f"{str(r['lt']) if r['lt'] else '—':>5} "
          f"{feat_str:>6} "
          f"{str(r['grids']) if r['grids'] else '—':>5} "
          f"{vox3:>11} {vox2:>9}")

# ── resolution별 실행 시간 비교 ──────────────────────────────────────
print("\n" + "=" * 80)
print("Resolution별 복셀 수 + 예상 실행 시간 (Single2022 기준: Sx=1.6, Sz=3.9)")
print("실제 측정: res=50, mpirun -np 4 → 508초")
print("=" * 80)

Sx = Sy = 1.6
Sz = 3.9
T_measured_sec = 508.5  # res=50, np=4 실제 측정값
Nvox_50 = int(Sx*50)**2 * int(Sz*50)

print(f"\n{'res':>6} {'복셀':>12} {'배율':>7} {'예상(np=4)':>12} {'예상(np=10)':>13} {'예상(np=128)':>14}")
print("─" * 70)
for res in [10, 20, 30, 40, 50, 60, 80, 100]:
    Nvox = int(Sx*res)**2 * int(Sz*res)
    scale = Nvox / Nvox_50
    t_np4   = T_measured_sec * scale
    t_np10  = T_measured_sec * scale * (4/10)
    t_np128 = T_measured_sec * scale * (4/128)

    def fmt_t(sec):
        if sec < 60: return f"{sec:.0f}s"
        if sec < 3600: return f"{sec/60:.1f}min"
        return f"{sec/3600:.1f}h"

    mark = " ← 측정값" if res == 50 else ""
    mark2 = " **" if t_np10 > 7200 else ""
    print(f"{res:>6} {Nvox:>12,} {scale:>7.1f}x {fmt_t(t_np4):>12} {fmt_t(t_np10):>13}{mark2} {fmt_t(t_np128):>14}{mark}")

# ── 2D vs 3D 필요성 분석 ────────────────────────────────────────────
print("\n" + "=" * 80)
print("3D 시뮬레이션이 왜 필요한가 — CIS color router vs 메타렌즈")
print("=" * 80)

analysis = """
[CIS Color Router가 3D 필수인 이유]

1. 색 분리 메커니즘이 Z축 의존적
   - 빛이 메타서피스(Z축 위)에서 산란/회절 후 Z축 아래 검출기에 집속
   - 2D (XZ 단면)는 Bayer 4분면(X,Y 모두)을 표현 불가
   - X방향 G, Y방향 R/B 같은 비대칭 집속은 XY 모두 필요

2. Bayer 사분면 = 2D 공간에서의 색 분리
   - R(-x,-y), Gr(-x,+y), B(+x,+y), Gb(+x,-y) ← X,Y 동시 필요
   - 2D (XZ)면 X방향만 → R vs B 구분은 되지만 G(+y) vs R(-y) 구분 불가

3. pillar_mask가 2D (NxN)
   - 20×20 이진 배열 구조 자체가 X,Y 모두 설계됨
   - XZ 단면만 보면 1D 배열처럼 보여서 실제 설계와 다름

[그래서 resolution을 낮춰도 되는가?]

   YES — 단, 최소 격자 조건 충족 시
   - 최소 feature(pillar) × resolution >= 8격자 이상
   - Single2022: w=80nm, res=50 → 4격자 (논문 본인도 타협점)
   - res=30: 80nm × 30 = 2.4격자 → 너무 적음
   - res=40: 80nm × 40 = 3.2격자 → 겨우 최소
   - 실용적 타협: res=20으로 빠른 검증 → res=50으로 정밀 실행

[2D로 충분한 케이스 (메타렌즈 등)]

   - 1D 배열 구조 (grating, 회절격자)
   - 단일 방향 포커싱 (cylindrical lens)
   - 편광 분리 (X 또는 Y 방향만)
   - 파장 필터링 (Z방향만)
   
   → CIS color router는 2D 사분면이 핵심이라 3D 불가피

[현실적 전략]

   단계 1: res=10~20으로 2~3분 fast-check (구조 확인)
   단계 2: res=30~40으로 15~30분 검증 실행 (정성적 결과 확인)
   단계 3: res=50으로 SimServer 풀런 (논문 비교용 정량 결과)
"""
print(analysis)

# ── 실제 측정값 기반 권장사항 ───────────────────────────────────────
print("=" * 80)
print("권장 실행 전략 (Single2022 실제 측정 기반)")
print("=" * 80)
print(f"""
  측정: res=50, mpirun -np 4 → {T_measured_sec:.0f}s ({T_measured_sec/60:.1f}분)
  
  빠른 검증 (res=20, np=4):
    복셀 = {int(Sx*20)**2 * int(Sz*20):,}개
    예상 시간 = {T_measured_sec * (int(Sx*20)**2 * int(Sz*20)) / Nvox_50:.0f}s ({T_measured_sec * (int(Sx*20)**2 * int(Sz*20)) / Nvox_50/60:.1f}분)
    격자 수 (w=80nm): {0.08*20:.1f}격자 → 주의 필요

  중간 실행 (res=40, np=10):
    복셀 = {int(Sx*40)**2 * int(Sz*40):,}개
    예상 시간 = {T_measured_sec * (int(Sx*40)**2 * int(Sz*40)) / Nvox_50 * (4/10):.0f}s ({T_measured_sec * (int(Sx*40)**2 * int(Sz*40)) / Nvox_50 * (4/10) /60:.1f}분)
    격자 수 (w=80nm): {0.08*40:.1f}격자

  풀런 (res=50, np=128 SimServer):
    예상 시간 = {T_measured_sec * (4/128):.0f}s ({T_measured_sec * (4/128)/60:.1f}분) ← 빠름!
""")
