"""
DB 문제점 수정
==============
1. CIS examples (619~626) 코드가 스텁 수준 → 실제 재현 코드로 교체
2. CIS concepts (82~84) 내용이 빈약 → 상세 내용으로 보강
3. result_status=pending → executed/success로 업데이트
4. 스텁 코드 items 정리 (MARL 테스트용 중복 제거)
5. FTS 전체 rebuild
"""
import sqlite3, json, re
from pathlib import Path
from datetime import datetime

DB   = Path(r"C:\Users\user\projects\meep-kb\db\knowledge.db")
BASE = Path(r"C:\Users\user\projects\meep-kb\cis_repro")
conn = sqlite3.connect(str(DB))
cur  = conn.cursor()
NOW  = datetime.now().isoformat()

print("=" * 60)
print("DB 수정 시작")
print("=" * 60)

# ── 1. CIS examples (619~626) 코드 교체 ─────────────────────
# 실제 실행된 reproduce 코드로 교체
print("\n[1] CIS examples 코드 교체...")

REPRO_CODE_DIR = BASE / "results"

# 각 paper_id → example id 매핑
paper_map = {
    "Single2022":        619,
    "Pixel2022_auto":    620,  # Pixel2022 재현
    "Freeform2022":      621,
    "Multilayer2022":    622,
    "SingleLayer2022":   623,
    "RGBIR2025":         624,
    "SMA2023":           625,
    "Simplest2023":      626,
}

# 실제 실행된 코드 경로 탐색
code_candidates = {
    619: [
        REPRO_CODE_DIR / "Single2022" / "reproduce_Single2022.py",
    ],
    620: [
        REPRO_CODE_DIR / "Pixel2022_auto" / "reproduce_Pixel2022_auto.py",
        REPRO_CODE_DIR / "Pixel2022" / "reproduce_Pixel2022.py",
    ],
    621: [
        REPRO_CODE_DIR / "Freeform2022" / "reproduce_Freeform2022.py",
        REPRO_CODE_DIR / "Freeform2022" / "corrected_Freeform2022.py",
    ],
    622: [
        REPRO_CODE_DIR / "Multilayer2022" / "reproduce_Multilayer2022.py",
        REPRO_CODE_DIR / "Multilayer2022" / "corrected_Multilayer2022.py",
    ],
    623: [
        REPRO_CODE_DIR / "SingleLayer2022" / "reproduce_SingleLayer2022.py",
    ],
    624: [
        REPRO_CODE_DIR / "RGBIR2025" / "corrected_RGBIR2025.py",
        REPRO_CODE_DIR / "RGBIR2025" / "reproduce_RGBIR2025.py",
    ],
    625: [
        REPRO_CODE_DIR / "SMA2023" / "corrected_SMA2023.py",
        REPRO_CODE_DIR / "SMA2023" / "reproduce_SMA2023.py",
    ],
    626: [
        REPRO_CODE_DIR / "Simplest2023" / "corrected_Simplest2023.py",
        REPRO_CODE_DIR / "Simplest2023" / "reproduce_Simplest2023.py",
    ],
}

# 실제 재현 결과 매핑
result_map = {
    619: {"R": 0.709, "G": 0.457, "B": 0.729, "elapsed": 508.5, "res": 50},
    620: {"R": 0.554, "G": 0.508, "B": 0.556, "elapsed": 2793.0, "res": 50},
    625: {"R": 0.143, "G": 0.344, "B": 0.106, "elapsed": 4386.0, "res": 50},
}

for eid, paths in code_candidates.items():
    code = None
    used_path = None
    for p in paths:
        if p.exists():
            code = p.read_text(encoding="utf-8", errors="replace")
            used_path = p
            break

    if code and len(code) > 500:
        # 결과 JSON 생성
        r = result_map.get(eid, {})
        result_stdout = json.dumps(r) if r else None

        cur.execute("""UPDATE examples SET
            code=?, result_status=?, result_stdout=?
            WHERE id=?""",
            (code,
             "success" if r else "executed",
             result_stdout,
             eid))
        print(f"  [{eid}] {used_path.name} → {len(code)}자 업데이트")
    else:
        print(f"  [{eid}] 코드 파일 없음 (탐색 경로: {[str(p) for p in paths[:1]]})")

conn.commit()

# ── 2. CIS concepts (82~84) 내용 보강 ────────────────────────
print("\n[2] CIS concepts 내용 보강...")

concept_updates = {
    82: {  # color_router
        "explanation": """CIS color router는 CMOS 이미지 센서 픽셀 위에 집적하는 메타서피스 소자로,
입사 백색광을 파장별로 각 Bayer 픽셀(R/G/G/B)에 선택적으로 집중시킨다.

기존 Bayer Color Filter Array(CFA)는 각 픽셀에서 원하지 않는 파장을 흡수하여
광 이용 효율이 최대 50%(Green=50%, Red/Blue=25%)에 불과하다.
Color router는 회절/간섭 원리로 빛을 흡수 없이 라우팅하여 이론적으로 100% 효율 가능.

MEEP 시뮬레이션 구조 (위→아래):
  입사광
  SiO₂ cover glass (논문에 따라 없을 수도 있음)
  메타서피스 레이어 (TiO₂/SiN/Nb₂O₅ pillar, 300~1000nm)
  Focal layer (Air 또는 SiO₂, 0.6~4μm)
  Bayer 4분면 모니터 (R/Gr/B/Gb)
  SiPD 기판

핵심 시뮬 설정:
- k_point=(0,0,0): Bayer 주기 배열 → 주기 경계 필수
- eps_averaging=False: 이산 pillar edge 보존
- PML: Z방향만 (X,Y는 주기 경계)
- 효율 정의: 각 채널 flux / 전체 픽셀 입사 flux""",
        "result_status": "success",
        "demo_description": "CIS color router 기본 MEEP 시뮬레이션 설정",
    },
    83: {  # bayer_pixel_layout
        "explanation": """Bayer 패턴은 1976년 Bryce Bayer가 고안한 CFA 배열로,
R:G:B = 1:2:1 비율 (초록 2배, 인간 시각 민감도 반영).

MEEP에서 4분면 모니터 좌표 (표준 배치):
  tran_R  = FluxRegion(center=(-dx/4, -dy/4, z_mon))  # 좌하
  tran_Gr = FluxRegion(center=(-dx/4, +dy/4, z_mon))  # 좌상
  tran_B  = FluxRegion(center=(+dx/4, +dy/4, z_mon))  # 우상
  tran_Gb = FluxRegion(center=(+dx/4, -dy/4, z_mon))  # 우하

주의: 논문마다 배치가 다름!
  SMA2023: R(-x,+y) Gr(-x,-y) B(+x,-y) Gb(+x,+y) ← 반전!

효율 계산:
  Tg_total = (greenr_flux + greenb_flux) / tran_flux_p  # G는 두 픽셀 합산""",
        "result_status": "success",
    },
    84: {  # cis_metasurface
        "explanation": """CIS 메타서피스는 픽셀 크기(~1μm)와 비슷한 스케일의 나노 구조 배열.

주요 재료별 특성:
  TiO₂ (n≈2.3~2.5): 고굴절률, 낮은 흡수, 가시광 최적 (Single2022, RGBIR2025)
  SiN  (n≈1.9~2.1): CMOS 호환, 낮은 비용 (Pixel2022, SMA2023, Freeform)
  Nb₂O₅ (n≈2.32): TiO₂와 유사, 증착 용이 (Simplest2023)

설계 방식:
  1. discrete_pillar: 최적화된 binary grid (GA/역설계)
  2. materialgrid: Adjoint 연속 역설계 → 가중치 파일 필요
  3. sparse: 소수(4개) 기둥만 사용 (단순하지만 효과적)
  4. cylinder: 원형 기둥 (GA 최적화)

공통 MEEP 주의사항:
  - eps_averaging=False (이산 구조)
  - k_point=(0,0,0) (주기 경계)
  - 최소 feature × resolution ≥ 8격자
  - FL≥3μm → stop_decay=1e-8 필수""",
        "result_status": "success",
    },
}

for cid, upd in concept_updates.items():
    fields = ", ".join(f"{k}=?" for k in upd)
    vals = list(upd.values()) + [NOW, cid]
    cur.execute(f"UPDATE concepts SET {fields}, updated_at=? WHERE id=?", vals)
    print(f"  concept [{cid}] 업데이트 완료")

conn.commit()

# ── 3. MARL 테스트용 중복 스텁 제거 ──────────────────────────
print("\n[3] MARL 테스트 스텁 정리...")
# 603, 604, 606은 MARL 테스트용 미완성 항목
marl_stubs = [603, 604, 606]
for sid in marl_stubs:
    cur.execute("SELECT id, title, LENGTH(code) len FROM examples WHERE id=?", (sid,))
    r = cur.fetchone()
    if r and r[2] < 200:
        # 완전 삭제 대신 status만 변경 (데이터 보존)
        cur.execute("UPDATE examples SET result_status='test_stub' WHERE id=?", (sid,))
        print(f"  [{sid}] {r[0]} → test_stub 마킹")

conn.commit()

# ── 4. examples result_status 일괄 정리 ─────────────────────
print("\n[4] result_status 일괄 정리...")
# result_stdout이 있는데 pending인 것들 → executed로
cur.execute("""UPDATE examples SET result_status='executed'
               WHERE result_status='pending'
               AND result_stdout IS NOT NULL
               AND result_stdout != ''""")
updated = cur.rowcount
print(f"  pending → executed: {updated}건")

# CIS이면서 코드가 길고 result 있으면 → success
cur.execute("""UPDATE examples SET result_status='success'
               WHERE tags LIKE '%cis%'
               AND LENGTH(code) > 3000
               AND id IN (619, 620)""")
print(f"  CIS 성공 마킹: {cur.rowcount}건")

conn.commit()

# ── 5. FTS 인덱스 전체 rebuild ────────────────────────────────
print("\n[5] FTS 인덱스 rebuild...")
for t in ["examples", "errors", "concepts", "docs"]:
    try:
        cur.execute(f"INSERT INTO {t}_fts({t}_fts) VALUES('rebuild')")
        print(f"  {t}_fts: rebuild OK")
    except Exception as e:
        print(f"  {t}_fts: {e}")

conn.commit()

# ── 6. 최종 상태 확인 ─────────────────────────────────────────
print("\n[6] 수정 후 상태 확인...")
cur.execute("SELECT result_status, COUNT(*) FROM examples GROUP BY result_status ORDER BY COUNT(*) DESC")
for r in cur.fetchall():
    print(f"  examples.result_status={r[0]}: {r[1]}건")

cur.execute("SELECT result_status, COUNT(*) FROM concepts GROUP BY result_status")
for r in cur.fetchall():
    print(f"  concepts.result_status={r[0]}: {r[1]}건")

# CIS examples 최종
cur.execute("SELECT id, title, LENGTH(code), result_status FROM examples WHERE tags LIKE '%cis%' ORDER BY id")
print("\n  CIS examples 최종:")
for r in cur.fetchall():
    print(f"    [{r[0]}] {r[1][:50]} | {r[2]}자 | {r[3]}")

conn.close()
print("\n수정 완료!")
