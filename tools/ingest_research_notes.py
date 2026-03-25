"""
ingest_research_notes.py
memory/meep-errors.md에서 추출한 8개 패턴을 sim_errors_v2에 삽입.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"

# meep-errors.md에서 추출한 8개 패턴
KNOWN_ERRORS = [
    {
        "error_class": "PhysicsError",
        "error_type": "EigenMode_eig_band_zero",
        "error_message": "eig_band=0 설정으로 에너지 비보존 (Efficiency > 100%)",
        "symptom": "Efficiency > 100%, 에너지 비보존, T+R != 1",
        "physics_cause": (
            "MEEP mode 번호는 1-indexed. eig_band=0은 정의되지 않은 모드. "
            "EigenmodeSource(..., eig_band=0)은 TE0 모드가 아니라 undefined band를 참조함."
        ),
        "code_cause": "EigenmodeSource(eig_band=0) — 0이 아니라 1부터 시작",
        "trigger_code": "EigenmodeSource(..., eig_band=0)",
        "fix_type": "code_only",
        "fix_description": "eig_band=0 → eig_band=1 (TE0), eig_band=2 (TE1)",
        "original_code": "EigenmodeSource(..., eig_band=0)",
        "fixed_code": "EigenmodeSource(..., eig_band=1)  # TE0 = band 1",
        "fix_worked": 1,
        "source": "research_notes",
    },
    {
        "error_class": "PhysicsError",
        "error_type": "EigenMode_eig_parity_wrong",
        "error_message": "eig_parity=mp.EVEN_Y 설정으로 TM 모드 여기 (에너지 비보존)",
        "symptom": "Efficiency > 100%, 잘못된 모드 여기, T+R 불일치",
        "physics_cause": (
            "eig_parity=mp.EVEN_Y는 TM 모드를 선택함. TE 모드(SOI)의 경우 "
            "2D: eig_parity=mp.ODD_Z + mp.EVEN_Y, 3D: eig_parity=mp.ODD_Z 사용 필요."
        ),
        "code_cause": "eig_parity=mp.EVEN_Y → TM 모드가 됨",
        "trigger_code": "EigenmodeSource(eig_parity=mp.EVEN_Y)",
        "fix_type": "code_only",
        "fix_description": "TE mode: 2D → eig_parity=mp.ODD_Z+mp.EVEN_Y, 3D → eig_parity=mp.ODD_Z",
        "original_code": "EigenmodeSource(eig_parity=mp.EVEN_Y)",
        "fixed_code": "EigenmodeSource(eig_parity=mp.ODD_Z + mp.EVEN_Y)  # TE mode (2D)\n# or: EigenmodeSource(eig_parity=mp.ODD_Z)  # TE mode (3D SOI)",
        "fix_worked": 1,
        "source": "research_notes",
    },
    {
        "error_class": "GeometryError",
        "error_type": "Substrate_PML_reflection",
        "error_message": "SiO2 기판이 PML 전에 끝나 반사 발생",
        "symptom": "반사가 심함, R이 비정상적으로 높음, T+R > 1 or T 낮음",
        "physics_cause": (
            "SiO2 substrate가 simulation cell 경계(PML 시작 전)에서 끊기면 "
            "PML-substrate 경계에서 반사 발생. substrate는 PML 내부까지 연장되어야 함."
        ),
        "code_cause": "mp.Block(size=mp.Vector3(cell_x - 2*dpml, ...)) — PML 제외한 크기",
        "trigger_code": "mp.Block(size=mp.Vector3(cell_x - 2*dpml, substrate_thickness, mp.inf))",
        "fix_type": "code_only",
        "fix_description": "substrate Block의 x 크기를 mp.inf 또는 cell_x 전체로 확장",
        "original_code": "mp.Block(size=mp.Vector3(cell_x - 2*dpml, substrate_thickness, mp.inf), ...)",
        "fixed_code": "mp.Block(size=mp.Vector3(mp.inf, substrate_thickness, mp.inf), ...)  # PML 포함 전체",
        "fix_worked": 1,
        "source": "research_notes",
    },
    {
        "error_class": "NumericalError",
        "error_type": "FOM_NaN_gradient_divergence",
        "error_message": "FOM = NaN: Gradient 발산 또는 MaterialGrid numerical instability",
        "symptom": "FOM이 NaN, gradient 계산 실패, adjoint 최적화 중단",
        "physics_cause": (
            "β (projection sharpness)가 너무 급격히 증가하면 gradient가 발산. "
            "MaterialGrid의 numerical instability 또는 "
            "Source 위치가 design region과 너무 가까워 near-field 영향."
        ),
        "code_cause": (
            "beta_schedule 급격 증가 [0, 100, 1000], "
            "또는 source center가 design region과 < 0.5μm 이격"
        ),
        "trigger_code": "beta_schedule=[0, 100, 1000]  # 급격한 beta 증가",
        "fix_type": "code_only",
        "fix_description": "β를 2부터 시작 점진 증가, learning rate 낮추기, source를 design region에서 1μm 이상 이격",
        "original_code": "# beta schedule: [0, 100, 1000]\n# source too close to design region",
        "fixed_code": "# beta schedule: [2, 4, 8, 16, 32] (점진적)\n# source center: design_region_start - 1.0 (1μm 이격)",
        "fix_worked": 1,
        "source": "research_notes",
    },
    {
        "error_class": "RuntimeError",
        "error_type": "MPI_not_enough_slots",
        "error_message": "mpirun: not enough slots / Address already in use",
        "symptom": "MPI 실행 실패, 이전 프로세스가 포트/슬롯 점유",
        "physics_cause": (
            "이전 mpirun/python 프로세스가 종료되지 않고 남아있어 새 MPI 실행 차단. "
            "좀비 프로세스 또는 포트 충돌."
        ),
        "code_cause": "이전 MPI 프로세스 미종료",
        "trigger_code": "mpirun -np 10 python script.py  # 이전 실행 잔류 시",
        "fix_type": "environment",
        "fix_description": "pkill -9 mpirun && pkill -9 python meep → sleep 2 → 재실행",
        "original_code": "mpirun -np 10 python script.py",
        "fixed_code": "pkill -9 -f 'mpirun'\npkill -9 -f 'python.*meep'\nimport time; time.sleep(2)\n# then: mpirun -np 10 python script.py",
        "fix_worked": 1,
        "source": "research_notes",
    },
    {
        "error_class": "GeometryError",
        "error_type": "3D_substrate_z_offset_wrong",
        "error_message": "3D에서 substrate geometry의 z 좌표계 미반영으로 Mode Profile 오류",
        "symptom": "3D 시뮬레이션에서 모드 프로파일 오류, 예상치 못한 투과율",
        "physics_cause": (
            "3D MEEP cell의 z range는 [-sz/2, +sz/2]. "
            "substrate center_z는 -sz/2 + dpml + substrate_thickness/2로 명시 계산 필요. "
            "Source/Monitor center도 z=0이 아니라 slab center에 위치해야 함."
        ),
        "code_cause": "mp.Block(center=mp.Vector3(0,0,0)) — z=0이 substrate center가 아님",
        "trigger_code": "mp.Block(center=mp.Vector3(0, 0, 0), size=mp.Vector3(mp.inf, mp.inf, substrate_thickness))",
        "fix_type": "code_only",
        "fix_description": "substrate_center_z = -sz/2 + dpml + substrate_thickness/2 으로 명시 계산",
        "original_code": "mp.Block(center=mp.Vector3(0, 0, 0), size=mp.Vector3(mp.inf, mp.inf, substrate_thickness))",
        "fixed_code": (
            "sz = 2*dpml + substrate_thickness + slab_thickness + clad_thickness\n"
            "substrate_center_z = -sz/2 + dpml + substrate_thickness/2\n"
            "mp.Block(center=mp.Vector3(0, 0, substrate_center_z), "
            "size=mp.Vector3(mp.inf, mp.inf, substrate_thickness + dpml))"
        ),
        "fix_worked": 1,
        "source": "research_notes",
    },
    {
        "error_class": "PerformanceError",
        "error_type": "Simulation_decay_too_strict",
        "error_message": "stop_when_fields_decayed 임계값이 너무 낮아 시뮬레이션이 수 시간 실행",
        "symptom": "시뮬레이션이 끝나지 않음, 실행 시간 비정상적으로 길어짐",
        "physics_cause": (
            "decay 임계값 1e-9는 너무 엄격. 일반적인 광학 시뮬레이션에서 "
            "field가 1e-9 수준까지 감쇠하려면 매우 오랜 시간 필요. "
            "1e-3 수준으로도 충분히 정확한 결과 보장."
        ),
        "code_cause": "mp.stop_when_fields_decayed(50, mp.Ez, pt, 1e-9) — decay 임계값 너무 낮음",
        "trigger_code": "until_after_sources=mp.stop_when_fields_decayed(50, mp.Ez, pt, 1e-9)",
        "fix_type": "code_only",
        "fix_description": "decay 임계값 1e-9 → 1e-3 (권장값)",
        "original_code": "until_after_sources=mp.stop_when_fields_decayed(50, mp.Ez, pt, 1e-9)",
        "fixed_code": "until_after_sources=mp.stop_when_fields_decayed(50, mp.Ez, pt, 1e-3)  # 권장값",
        "fix_worked": 1,
        "source": "research_notes",
    },
    {
        "error_class": "PhysicsError",
        "error_type": "3D_efficiency_drop_neff_mismatch",
        "error_message": "3D 검증 시 효율 급락: 2D 최적화의 neff가 substrate 미포함",
        "symptom": "2D에서 높은 효율, 3D로 전환 시 효율 급락 (예: 95% → 40%)",
        "physics_cause": (
            "2D inverse design 최적화 시 neff를 substrate 없이 계산하면 "
            "3D 실제 구조와 effective index 불일치 발생. "
            "Air cladding 구조는 특히 이 문제에 민감."
        ),
        "code_cause": "MPB neff 계산 시 substrate 레이어 미포함",
        "trigger_code": "# MPB neff without substrate layer",
        "fix_type": "code_only",
        "fix_description": "3D 검증 전 MPB로 substrate 포함한 실제 neff 재계산, EigenmodeSource center_freq 조정",
        "original_code": "# 2D: neff calculated without substrate\nEigenmodeSource(center_frequency=1/wavelength)",
        "fixed_code": (
            "# 3D: neff recalculated with substrate via MPB\n"
            "# neff = mpb.ModeSolver(geometry=[substrate+slab]).run_te()[0].freq\n"
            "EigenmodeSource(center_frequency=neff/wavelength)"
        ),
        "fix_worked": 1,
        "source": "research_notes",
    },
]


def ingest(conn: sqlite3.Connection) -> int:
    """KNOWN_ERRORS를 sim_errors_v2에 삽입. 중복 방지 포함. 삽입된 수 반환."""
    cur = conn.cursor()

    # 기존 research_notes 데이터 삭제 (재실행 시 중복 방지)
    cur.execute("DELETE FROM sim_errors_v2 WHERE source = 'research_notes'")
    deleted = cur.rowcount
    if deleted:
        print(f"  기존 research_notes {deleted}건 삭제 (재삽입)")

    inserted = 0
    now = datetime.now().isoformat()

    for err in KNOWN_ERRORS:
        cur.execute("""
            INSERT INTO sim_errors_v2 (
                error_class, error_type, error_message,
                symptom, trigger_code,
                physics_cause, code_cause,
                fix_type, fix_description,
                original_code, fixed_code,
                fix_worked, source,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            err.get("error_class"),
            err["error_type"],
            err["error_message"],
            err.get("symptom"),
            err.get("trigger_code"),
            err["physics_cause"],
            err.get("code_cause"),
            err["fix_type"],
            err["fix_description"],
            err.get("original_code"),
            err.get("fixed_code"),
            err["fix_worked"],
            err["source"],
            now,
        ))
        inserted += 1

    conn.commit()
    return inserted


def main():
    print(f"DB: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))

    print(f"KNOWN_ERRORS: {len(KNOWN_ERRORS)}개 패턴 삽입 시작")
    inserted = ingest(conn)
    conn.close()

    print(f"\n=== 결과 ===")
    print(f"삽입된 research_notes 패턴: {inserted}건")

    # 검증
    conn2 = sqlite3.connect(str(DB_PATH))
    cur = conn2.cursor()
    cur.execute("""
        SELECT COUNT(*), SUM(fix_worked), COUNT(physics_cause)
        FROM sim_errors_v2 WHERE source='research_notes'
    """)
    count, fix_worked_sum, physics_count = cur.fetchone()
    conn2.close()

    print(f"DB 확인: {count}건, fix_worked=1 합계: {fix_worked_sum}, physics_cause 있음: {physics_count}")

    if count == 8 and fix_worked_sum == 8 and physics_count == 8:
        print("[OK] All verifications passed!")
    else:
        print("[FAIL] Verification failed!")
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
