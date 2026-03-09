"""
diagnose_engine 로컬 테스트 (Docker 없이)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.diagnose_engine import parse_error, search_db, extract_physics_context

# 테스트 케이스 1: MPI 오류
test_code = """
import meep as mp
import numpy as np

sim = mp.Simulation(
    cell_size=mp.Vector3(10, 10, 0),
    resolution=20,
    sources=[mp.EigenModeSource(
        mp.ContinuousSource(frequency=1/1.55),
        center=mp.Vector3(-4, 0, 0),
        size=mp.Vector3(0, 2, 0),
        eig_band=0,  # 버그: 1부터 시작해야 함
    )],
)
sim.run(until=100)
"""

test_error1 = """
Traceback (most recent call last):
  File "test.py", line 15, in <module>
    sim.run(until=100)
MPIError: The number of adjoint chunks (3) is not equal to the number of forward chunks (0)
"""

test_error2 = """
Traceback (most recent call last):
  File "test.py", line 10, in <module>
    src = mp.EigenModeSource(...)
AttributeError: module 'meep' has no attribute 'FreqRange'
"""

test_error3 = """
meep: Simulation diverged at t=45.2
NaN detected in field components
"""

for i, (code, err) in enumerate([(test_code, test_error1), (test_code, test_error2), (test_code, test_error3)]):
    print(f"\n{'='*60}")
    print(f"테스트 {i+1}: {err.strip()[:60]}")
    error_info = parse_error(code, err)
    print(f"감지 타입: {error_info['primary_type']}")
    print(f"MEEP 키워드: {error_info['meep_keywords'][:5]}")

    results = search_db(error_info, code, err, n=5)
    print(f"DB 검색 결과: {len(results)}개")
    for r in results[:3]:
        print(f"  [{r['source']}] {r['type']}: {r['title'][:60]} (score={r['score']})")
        if r.get('solution'):
            print(f"    해결: {r['solution'][:80]}")
