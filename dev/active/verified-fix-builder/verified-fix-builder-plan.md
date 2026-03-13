# Verified Fix Builder — Implementation Plan
Last Updated: 2026-03-09

## Executive Summary

meep-kb 진단 시스템이 현재 GitHub discussion 텍스트를 그대로 반환하는 문제를 해결한다.
시뮬레이터(MEEP)가 직접 실행 + 검증한 코드 수정 쌍을 자동으로 수집하는 파이프라인을 구축한다.

**목표**: "resolution을 20→40으로 올리세요 + 수정 코드" 같은 실행 가능한 진단 제안 제공

---

## 현재 상태 (Current State)

```
sim_errors DB (459건):
  github_issue:       242건  ← GitHub discussion 텍스트 (코드 수정 없음)
  github_structured:  151건  ← LLM 구조화 요약 (검증 안 됨)
  error_injector:      50건  ← Docker 실행 검증 O (but 코드 fix 쌍 미흡)
  marl_auto:            3건  ← MARL 자동 수정 (검증 O)
  err_file:            13건  ← 에러 파일 텍스트

검증된 코드 수정 쌍: 53건뿐 (10%)
```

**핵심 문제**:
1. 검색이 'Divergence' 태그만 보고 관계없는 내용 반환
2. fix_description에 Before/After 코드가 없음
3. verified 소스가 github 소스보다 낮은 점수로 묻힘

---

## 목표 상태 (Target State)

사용자 입력:
```
코드: sim = mp.Simulation(resolution=20, cell_size=mp.Vector3(10,10,0), ...)
에러: Simulation diverged at t=42.5
```

시스템 반환:
```
[MEEP 검증됨] Divergence: resolution 부족으로 인한 수치 발산

◈ 원인: resolution=20은 10×10 셀에서 Courant 조건 불안정

◉ 수정 코드:
  # Before
  sim = mp.Simulation(resolution=20, ...)
  # After
  sim = mp.Simulation(resolution=40, ...)   ← MEEP 검증: T=0.94, R=0.06 ✓
```

---

## 구현 단계

### Phase 1: Bug Catalog 확장 (8종 → 30종)
**파일**: `tools/error_injector.py` BUG_CATALOG 리스트 확장

추가할 버그 유형:
```python
# Divergence 계열 (추가)
- resolution_proportional   # 셀 크기 대비 resolution 낮음
- pml_too_thin_wvl          # 파장 대비 PML < 0.5λ
- courant_explicit_dt       # dt 직접 지정 (Courant 위반)
- until_too_short           # until이 너무 짧아 정상 수렴 전 종료
- no_symmetry_large_cell    # 대칭 없이 큰 셀 → 메모리/발산

# EigenMode 계열 (추가)
- eig_center_misaligned     # source center가 도파로 밖
- eig_parity_3d_wrong       # 3D에서 EVEN_Y+ODD_Z 아닌 값
- eig_kpoint_missing        # 주기 구조에서 k-point 미설정

# Adjoint 계열 (추가)
- missing_reset_meep        # 반복 루프에서 reset_meep() 누락
- design_variable_shape     # MaterialGrid 크기 ≠ x0 shape
- beta_too_high_initial     # binarization β 초기값 과도하게 높음
- missing_objective_weight  # objective function weight 누락

# Normalization 계열 (추가)
- missing_norm_run          # flux 절대값 사용 (normalization 없음)
- monitor_in_pml            # flux monitor가 PML 영역과 겹침
- monitor_inside_source     # refl monitor가 source 뒤에 없음

# MPI 계열 (추가)
- np_exceeds_chunks         # mpirun -np > 셀 청크 수
- mpi_unbalanced_adjoint    # adjoint forward/backward 청크 불일치
```

**완료 기준**: BUG_CATALOG에 30개 이상, 각 항목에 fix_code_template 포함

---

### Phase 2: verified_fix_builder.py 구현
**파일**: `tools/verified_fix_builder.py`

```
흐름:
  autosim 패턴 로드
    └→ BUG 주입 (buggy_code 생성)
         └→ Docker 실행 (meep-pilot-worker)
              └→ 에러 traceback 캡처
                   └→ LLM으로 fix_code 생성 (Claude API)
                        └→ Docker 실행 (fix_code)
                             └→ T/R 검증 (is_physical?)
                                  └→ fix_worked=1이면 sim_errors 저장
```

핵심 클래스:
```python
class VerifiedFixBuilder:
    def build_verified_pair(self, pattern_file, bug) -> Optional[FixPair]:
        """1 패턴 + 1 버그 → 검증된 수정 쌍 또는 None"""
        
    def run_batch(self, patterns, bugs, limit=None):
        """배치 실행: 모든 조합 시도"""
        
    def store_to_kb(self, pair: FixPair):
        """sim_errors + ChromaDB에 저장"""
```

핵심 데이터:
```python
@dataclass
class FixPair:
    original_code: str      # 버그 있는 코드
    fixed_code: str         # 검증된 수정 코드
    error_message: str      # 실제 traceback
    fix_description: str    # 한국어 설명 (Before/After 코드 포함)
    error_type: str
    root_cause: str
    verification: dict      # {T, R, exit_code, elapsed}
    fix_worked: int = 1
    source: str = "verified_fix"
```

한국어 설명 생성 형식:
```
{error_type} 에러: {root_cause}

원인: {detailed_cause}

수정 방법:
  # Before
  {buggy_snippet}
  # After  
  {fixed_snippet}

검증 결과: T={T:.3f}, R={R:.3f} (MEEP Docker 실행 확인)
```

**완료 기준**:
- `python tools/verified_fix_builder.py --dry-run --limit 5` 작동
- `python tools/verified_fix_builder.py --limit 50` 50건 이상 저장

---

### Phase 3: diagnose_engine.py score 개선
**파일**: `api/diagnose_engine.py`

```python
# score 우선순위 체계
SCORE_BY_SOURCE = {
    "verified_fix":     0.95,  # MEEP 실행 검증
    "marl_auto":        0.92,  # MARL 자동 수정
    "error_injector":   0.88,  # Docker 에러 확인
    "github_structured":0.72,  # LLM 구조화
    "github_issue":     0.65,  # 텍스트 참조
    "kb_fts":           0.65,  # FTS 텍스트
    "err_file":         0.60,  # 에러 파일
}
```

fix_description에서 코드 블록 추출:
```python
def extract_code_blocks(fix_desc: str) -> tuple[str, str]:
    """# Before / # After 블록 추출 → (before_code, after_code)"""
```

**완료 기준**: verified_fix 소스가 항상 상위 3건 안에 표시됨

---

### Phase 4: 검증 및 E2E 테스트
**파일**: `tools/_test_verified_fix.py`

테스트 케이스:
1. `resolution=20 + diverge` → verified_fix Divergence 카드 반환
2. `eig_band=0 + T>1` → verified_fix EigenMode 카드 반환
3. `reset_meep 없음 + adjoint error` → verified_fix Adjoint 카드 반환

**완료 기준**: 3개 테스트 모두 verified_fix 소스 결과 반환

---

## Risk Assessment

| 리스크 | 가능성 | 대응 |
|--------|--------|------|
| LLM fix 생성 실패 | 중간 | fix_worked=0으로 저장 후 스킵 |
| Docker 타임아웃 | 높음 | timeout=30s, 재시도 없음 |
| WAL lock 충돌 | 중간 | journal_mode=DELETE 강제 |
| 버그 주입 불가 | 높음 | regex 미매칭 시 스킵 |

---

## 수집 목표

| 소스 | 현재 | 목표 | 방법 |
|------|------|------|------|
| verified_fix | 0 | 200 | VerifiedFixBuilder |
| error_injector | 50 | 200 | Bug Catalog 확장 + 재실행 |
| marl_auto | 3 | 유지 | MARL 배치 지속 |
| **검증 합계** | **53** | **400+** | |

---

## 성공 기준

```
✅ verified_fix_builder.py 실행 → 1시간 내 100건 이상 저장
✅ 진단 테스트: "resolution=20 diverge" → verified_fix 카드 최상위 반환
✅ score 체계: verified_fix(0.95) > github_issue(0.65)
✅ fix_description: Before/After 코드 포함
✅ Docker 검증: T/R 값 표시
```
