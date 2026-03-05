"""
Pattern DB description/use_case 일괄 업그레이드 스크립트
- 영어 중심으로 재작성 (임베딩 품질 향상)
- 다양한 쿼리 표현 포함 (검색 recall 향상)
"""
import sqlite3

DB_PATH = '/app/db/knowledge.db'

# ── 업그레이드할 패턴 목록 ─────────────────────────────────────────────────
# 형식: (pattern_name, new_description, new_use_case)
UPGRADES = [
    (
        "dft_fields_extraction",
        "Extract DFT (Discrete Fourier Transform) field arrays from MEEP simulation. "
        "Register a DFT monitor with sim.add_dft_fields() before running, then retrieve "
        "complex field arrays (Ez, Hx, Ey, etc.) per frequency using sim.get_dft_array(). "
        "Supports 2D/3D, single or multi-frequency. Essential for field visualization, "
        "mode overlap calculation, and adjoint optimization monitoring. "
        "DFT field 추출: add_dft_fields로 모니터 등록 후 get_dft_array로 복소 필드 배열 획득.",
        "DFT field plot, DFT field extraction, get_dft_array usage, add_dft_fields, "
        "forward field visualization, adjoint field check, Ez Hx Ey field extraction, "
        "field array after simulation, frequency domain field, DFT 필드 추출, 필드 시각화, "
        "시뮬레이션 결과 확인, field propagation plot, imshow field"
    ),
    (
        "dft_field_monitor_3d",
        "Set up and extract DFT field monitor in 3D MEEP simulation for SOI slab waveguide. "
        "Records Ey field at a fixed YZ cross-section plane (x=const) to capture TE mode profile. "
        "Uses add_dft_fields with nfreq=1 at center frequency. Critical for verifying mode "
        "excitation quality and computing TE0/TE1 overlap integrals in 3D inverse design. "
        "3D DFT 필드 모니터: YZ 평면에서 Ey 필드 추출, SOI slab TE 모드 프로파일 확인.",
        "3D DFT field monitor, YZ plane field extraction, TE mode profile 3D, "
        "add_dft_fields 3D, Ey field slab waveguide, DFT monitor setup 3D simulation, "
        "mode profile extraction 3D, SOI waveguide field, 3D 필드 모니터, slab mode profile"
    ),
    (
        "plot_dft_mode_profiles",
        "Visualize DFT mode profiles from 3D simulation: (left) 2D |Ey|² heatmap on YZ plane, "
        "(right) 1D cross-section profile overlaid with theoretical TE0/TE1 reference. "
        "Annotates overlap integral values on the plot. Used to verify input (TE0 overlap>0.95) "
        "and output (TE1 overlap>0.9) mode quality in mode converter design. "
        "DFT 모드 프로파일 시각화: heatmap + 이론값 overlay + overlap 수치 표시.",
        "DFT mode profile plot, plot_dft_mode, TE0 TE1 overlap visualization, "
        "mode quality verification, Ey profile heatmap, overlap integral plot, "
        "mode converter output verification, 3D field profile, DFT 모드 프로파일, 모드 시각화"
    ),
    (
        "adjoint_solver_basics",
        "MEEP adjoint solver fundamentals: set up OptimizationProblem, define FOM using "
        "EigenmodeCoefficient, run forward + adjoint passes, retrieve gradient dJ/dp. "
        "Covers design variable setup with MaterialGrid, filter+projection pipeline, "
        "and gradient-based optimization loop with nlopt or custom optimizer. "
        "meep.adjoint 기본: OptimizationProblem 설정, EigenmodeCoefficient FOM, gradient 자동 계산.",
        "adjoint solver basics, meep adjoint tutorial, OptimizationProblem setup, "
        "EigenmodeCoefficient FOM, adjoint gradient calculation, MaterialGrid design variable, "
        "adjoint optimization loop, gradient-based photonic design, inverse design MEEP, "
        "adjoint 기본, 역설계 기초, gradient 계산, adjoint 시작하기"
    ),
    (
        "adjoint_optimization_problem",
        "Complete structure of meep.adjoint.OptimizationProblem: forward simulation pass, "
        "adjoint simulation pass, objective function evaluation, gradient computation dJ/dp. "
        "Shows __call__ method, get_objective_and_gradient(), design variable update workflow. "
        "Handles multiple frequencies, multiple objective functions, and design region mapping. "
        "OptimizationProblem 전체 구조: forward+adjoint pass, 설계변수 업데이트 루프.",
        "OptimizationProblem MEEP, adjoint forward pass, adjoint backward pass, "
        "get_objective_and_gradient, adjoint design variable update, multiple frequency adjoint, "
        "adjoint optimization complete example, mpa.OptimizationProblem, "
        "OptimizationProblem 사용법, adjoint 최적화 루프, 설계변수 업데이트"
    ),
    (
        "adjoint_objective_functions",
        "Define objective functions (FOM) for MEEP adjoint optimization. "
        "EigenmodeCoefficient: maximize |α|² for target mode at output port. "
        "FluxObjective: maximize power through a flux region. "
        "Multi-objective: weighted sum of transmission + reflection suppression. "
        "Shows correct eig_band indexing (1-based), eig_parity for TE/TM mode selection. "
        "FOM 정의: EigenmodeCoefficient |α|², FluxObjective, 다중 목적함수 조합.",
        "adjoint objective function, FOM definition MEEP, EigenmodeCoefficient usage, "
        "FluxObjective adjoint, eig_band indexing, eig_parity TE TM mode, "
        "transmission maximization adjoint, multi-objective adjoint FOM, "
        "FOM 정의, 목적함수, EigenmodeCoefficient 사용법, eig_band 오류"
    ),
    (
        "adjoint_waveguide_bend_optimization",
        "Complete adjoint topology optimization example for 90-degree waveguide bend. "
        "Full pipeline: geometry setup, source/monitor definition, OptimizationProblem, "
        "conic filter + tanh projection, BFGS optimization loop with callback, "
        "convergence plot, final structure visualization. Uses SOI 220nm platform. "
        "도파로 굽힘 adjoint 최적화 완전 예제: 필터+projection+최적화 루프 전체.",
        "adjoint waveguide bend optimization, complete adjoint example, BFGS adjoint, "
        "topology optimization waveguide, conic filter tanh projection adjoint, "
        "adjoint full pipeline, waveguide bend inverse design, SOI adjoint optimization, "
        "adjoint 예제, 도파로 최적화 예제, 완전한 adjoint 코드, topology 최적화"
    ),
    (
        "adjoint_mode_converter_opt",
        "Complete adjoint optimization for TE0-to-TE1 mode converter. "
        "Design region between tapered waveguides, EigenmodeCoefficient TE1 at output, "
        "conic filter for minimum feature size, beta-schedule for binarization, "
        "MPI-parallel execution, checkpoint save/resume. Jin's MCTP project pattern. "
        "모드 변환기 adjoint 최적화: TE0→TE1, conic filter, beta schedule, MPI 병렬.",
        "mode converter adjoint optimization, TE0 to TE1 mode conversion, "
        "mode converter inverse design, EigenmodeCoefficient TE1, conic filter mode converter, "
        "beta schedule binarization, mode converter MEEP, MCTP optimization, "
        "모드 변환기 최적화, TE0 TE1 변환, 모드 컨버터 adjoint"
    ),
    (
        "eigenmode_source_kpoints",
        "Correctly set up EigenModeSource with eig_kpoint for propagation direction control. "
        "eig_kpoint specifies the k-vector direction for eigenmode solver — critical for "
        "selecting forward-propagating vs backward modes. eig_band is 1-indexed (not 0). "
        "eig_parity: mp.ODD_Z for TE, mp.EVEN_Z for TM in 2D; mp.NO_PARITY for 3D. "
        "Common bugs: eig_band=0 (wrong), wrong eig_kpoint direction, missing eig_parity. "
        "EigenModeSource k-point 설정: 전파 방향, eig_band 1부터, eig_parity TE/TM 선택.",
        "EigenModeSource eig_kpoint, eigenmode source direction, eig_band indexing, "
        "eig_parity TE TM, EigenModeSource forward propagating, eigenmode source 3D, "
        "eig_band=0 error, eigenmode source wrong mode, TE mode source MEEP, "
        "EigenModeSource 설정, eig_kpoint 방향, eig_band 오류, TE 모드 소스"
    ),
    (
        "pml_boundary_conditions",
        "Set up PML (Perfectly Matched Layer) absorbing boundary conditions in MEEP. "
        "PML thickness: minimum lambda/2 (typically 1.0 μm for 1550nm). "
        "Critical: background material (SiO2) must extend to mp.inf, NOT just to cell boundary, "
        "otherwise reflections occur at PML interface. For waveguide simulations: "
        "PML only on x-boundaries (not y) to allow guided mode propagation. "
        "PML 설정: 최소 두께, SiO2 mp.inf 연장 필수, 방향별 PML, 반사 방지.",
        "PML boundary conditions MEEP, PML setup, PML thickness, absorbing boundary, "
        "SiO2 background PML, mp.inf material extension, waveguide PML x-direction, "
        "PML reflection artifact, boundary condition MEEP, "
        "PML 설정, 경계 조건, PML 두께, SiO2 배경 mp.inf, PML 반사 오류"
    ),
    (
        "mpi_parallel_simulation",
        "Run MEEP simulation with MPI parallelization. Command: mpirun -np N python script.py. "
        "Use mp.am_master() guard for file I/O and print statements to avoid duplicate output. "
        "Before new run: kill existing MPI processes (pkill -f mpirun). "
        "Checkpoint pattern: save npz every K iterations, resume with --resume flag. "
        "MPI slot error fix: --oversubscribe flag or reduce -np count. "
        "MPI 병렬 실행: am_master() 가드, 프로세스 정리, 체크포인트 저장/재개.",
        "MPI parallel MEEP, mpirun MEEP, am_master MPI guard, MPI duplicate output fix, "
        "MPI slot error oversubscribe, checkpoint save resume MPI, parallel simulation MEEP, "
        "mpirun -np 10, kill MPI processes, "
        "MPI 병렬, mpirun 오류, am_master, MPI 슬롯 오류, 체크포인트"
    ),
    (
        "plot_convergence_4panel",
        "4-panel convergence monitoring plot for adjoint optimization. "
        "Panel 1: FOM vs iteration. Panel 2: binarization metric vs iteration. "
        "Panel 3: beta schedule. Panel 4: gradient norm. "
        "Saves to convergence.png. Useful for diagnosing optimization stagnation, "
        "FOM collapse after beta increase, and gradient vanishing. "
        "adjoint 수렴 모니터링 4패널: FOM, binarization, beta, gradient norm.",
        "convergence plot adjoint, optimization convergence monitoring, FOM vs iteration plot, "
        "binarization convergence, beta schedule plot, adjoint optimization progress, "
        "convergence.png adjoint, gradient norm plot, "
        "수렴 플롯, FOM 수렴, 최적화 진행 시각화, binarization 모니터링"
    ),
    (
        "apply_conic_filter",
        "Apply conic (cone-shaped) spatial filter to design variables for minimum feature size (MFS) control. "
        "filter_radius = MFS / (2 * dx) in pixel units. Prevents features smaller than MFS. "
        "From meep.adjoint: mpa.conic_filter(x, radius, Lx, Ly, resolution). "
        "Must apply BEFORE tanh projection in the filter pipeline: x -> conic -> tanh -> design. "
        "conic filter MFS 제어: filter_radius = MFS/(2*dx), projection 전에 적용 필수.",
        "conic filter MEEP adjoint, minimum feature size filter, mpa.conic_filter, "
        "spatial filter design variables, filter radius MFS, fabrication constraint filter, "
        "conic filter before projection, filter pipeline adjoint, "
        "conic filter 사용법, MFS 제약, 최소 피처 크기, 공간 필터"
    ),
    (
        "apply_tanh_projection",
        "Apply tanh projection to binarize grayscale design variables toward 0/1 (Si/SiO2). "
        "Formula: (tanh(beta*eta) + tanh(beta*(x-eta))) / (tanh(beta*eta) + tanh(beta*(1-eta))). "
        "beta controls sharpness: start low (beta=1-4), increase gradually (beta schedule). "
        "eta=0.5 for symmetric threshold. Higher beta → sharper binary but risk of FOM collapse. "
        "tanh projection 이진화: beta 점진적 증가, eta=0.5, FOM 붕괴 주의.",
        "tanh projection MEEP adjoint, binarization projection, beta binarization, "
        "grayscale to binary design, mpa.tanh_projection, beta schedule projection, "
        "FOM collapse after beta increase, binarization adjoint optimization, "
        "tanh projection 사용법, 이진화, beta 증가 FOM 붕괴"
    ),
    (
        "stop_when_fields_decayed",
        "Automatically terminate MEEP simulation when fields have sufficiently decayed. "
        "mp.stop_when_fields_decayed(dt, c, pt, decay_by): stops when field component c "
        "at point pt has decayed by factor decay_by over interval dt. "
        "Alternative: mp.stop_when_dft_decayed() for frequency-domain convergence. "
        "Prevents over-running and under-running simulations. Typical: decay_by=1e-3 to 1e-6. "
        "시뮬레이션 자동 종료: 필드 감쇠 기준, dt/decay_by 설정, DFT 수렴 종료.",
        "stop_when_fields_decayed MEEP, simulation termination condition, "
        "automatic stop MEEP, mp.stop_when_dft_decayed, field decay stopping criterion, "
        "until_after_sources MEEP, simulation run until convergence, "
        "시뮬레이션 종료 조건, 자동 종료, 필드 감쇠"
    ),
]

def update_patterns():
    conn = sqlite3.connect(DB_PATH)
    updated = 0
    for pattern_name, new_desc, new_use_case in UPGRADES:
        result = conn.execute(
            "UPDATE patterns SET description=?, use_case=? WHERE pattern_name=?",
            (new_desc, new_use_case, pattern_name)
        )
        if result.rowcount > 0:
            print(f"[OK] {pattern_name}")
            updated += 1
        else:
            print(f"[NOT FOUND] {pattern_name}")
    conn.commit()
    conn.close()
    print(f"\nUpdated: {updated}/{len(UPGRADES)}")

if __name__ == "__main__":
    update_patterns()
