"""
/api/ingest/sim_error 엔드포인트 테스트
MARL auto-save 파이프라인 검증
"""
import urllib.request, json

KB_URL = "http://localhost:8765"

# 테스트 데이터: 실제 MARL이 저장해야 할 형태
test_cases = [
    {
        "error_type": "Adjoint",
        "error_message": "RuntimeError: changed_materials: cannot add new materials to a simulation after it has been run",
        "original_code": "opt = mpa.OptimizationProblem(...)\nopt.update_design([x0])\nf, dJ = opt(x0, need_gradient=True)",
        "fixed_code": "# reset_meep() 필요\nsim.reset_meep()\nopt = mpa.OptimizationProblem(...)\nopt.update_design([x0])\nf, dJ = opt(x0, need_gradient=True)",
        "fix_description": "adjoint 최적화 반복 시 sim.reset_meep() 호출 필요. OptimizationProblem은 매 iteration마다 시뮬레이션을 재실행하는데, reset 없이 재실행하면 이 에러 발생.",
        "root_cause": "reset_meep() 누락: adjoint loop에서 매 iteration마다 시뮬레이션 상태 초기화 필요",
        "pattern_name": "MARL-TEST-adjoint-reset",
        "source": "marl_auto",
        "fix_worked": 1,
        "project_id": "TEST-ERR-002",
    },
    {
        "error_type": "Divergence",
        "error_message": "meep: Simulation diverged at t=42.5. NaN detected in field components.",
        "original_code": "sim = mp.Simulation(resolution=5, ...)\nsim.run(until=500)",
        "fixed_code": "sim = mp.Simulation(resolution=20, ...)\nsim.run(until=200)",
        "fix_description": "resolution=5는 너무 낮아 수치 발산 발생. MEEP에서 안정적인 시뮬레이션을 위해 Courant 조건 필요: Δt ≤ Δx/(c√D). resolution을 20 이상으로 높이거나 시뮬레이션 시간을 줄이세요.",
        "root_cause": "Courant stability 위반: resolution 너무 낮음 (5 < 10 최소 권장)",
        "pattern_name": "MARL-TEST-diverge",
        "source": "marl_auto",
        "fix_worked": 1,
        "project_id": "TEST-ERR-003",
    },
    {
        "error_type": "MPIError",
        "error_message": "MPI_Abort was invoked on rank 0 with errorcode 1. The number of adjoint chunks (3) is not equal to the number of forward chunks (0).",
        "original_code": "mpirun -np 10 python adjoint_sim.py",
        "fixed_code": "# split_chunks_evenly=False 또는 -np 수 조정\nsim = mp.Simulation(..., split_chunks_evenly=True)\nmpirun -np 8 python adjoint_sim.py",
        "fix_description": "adjoint 시뮬레이션에서 MPI 프로세스 수가 청크 분할과 맞지 않음. split_chunks_evenly=True 설정 또는 -np를 시뮬레이션 셀 크기에 맞게 조정하세요.",
        "root_cause": "MPI 청크 불균형: adjoint forward/backward 청크 수 불일치",
        "pattern_name": "MARL-TEST-mpi-chunks",
        "source": "marl_auto",
        "fix_worked": 1,
        "project_id": "TEST-ERR-004",
    },
]

for i, tc in enumerate(test_cases):
    data = json.dumps(tc).encode('utf-8')
    req = urllib.request.Request(
        f"{KB_URL}/api/ingest/sim_error",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read())
        print(f"[{i+1}] {tc['error_type']}: {result.get('message','')}")
    except Exception as e:
        print(f"[{i+1}] 오류: {e}")

# 저장 확인
print("\n저장 확인:")
req2 = urllib.request.Request(f"{KB_URL}/api/stats/errors")
with urllib.request.urlopen(req2, timeout=10) as r:
    stats = json.loads(r.read())
print(f"총 {stats['total']}개 (verified: {stats['verified']}개)")
for b in stats.get('by_source', [])[:6]:
    print(f"  {b['source']}: {b['count']}개")
