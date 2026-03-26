# Verified Fix Pipeline Plan
## 목표: "시뮬레이터가 직접 실행하고 검증한 코드 수정 제안" 시스템

작성일: 2026-03-09

---

## 1. 현재 문제 (근본 원인)

### 증상
사용자가 `Simulation diverged at t=42.5` 에러를 입력했을 때:
- "build failure for pympb" 같은 **전혀 관계없는** GitHub discussion 반환
- `resolution=20`이 문제인데 "HDF5 파일 병렬 쓰기 성능" 얘기

### 근본 원인
```
현재 DB의 sim_errors 구성:
  github_issue:      242건 → discussion 제목/내용 (코드 수정 없음)
  github_structured: 151건 → LLM이 구조화한 요약 (검증 안 됨)
  error_injector:     50건 → Docker 실행 검증 O, 하지만 코드 수정 쌍 부족
  marl_auto:           3건 → MARL 자동 수정 (검증 O)
```

**핵심**: 실제로 MEEP을 돌려보고 고쳐서 저장된 것이 53건뿐.
나머지 393건은 텍스트 매칭용이지 실행 가능한 수정 제안이 아님.

---

## 2. 목표 상태

사용자가 입력:
```python
sim = mp.Simulation(resolution=20, ...)
sim.run(until=500)
# Error: Simulation diverged at t=42.5
```

시스템이 반환:
```
[MEEP 검증됨] Divergence: resolution 부족으로 인한 수치 발산

◈ 원인
  resolution=20이 해당 셀 크기(10x10)에 너무 낮습니다.
  Courant 조건: Δt = Δx/(c√2) → resolution=20은 dt=0.035
  발산 시간 t=42.5 ≈ 1200Δt 로 초기 발산 패턴

◉ 수정 코드
  # Before
  sim = mp.Simulation(..., resolution=20, ...)
  sim.run(until=500)

  # After  
  sim = mp.Simulation(..., resolution=40, ...)  # resolution 2배 이상
  sim.run(until_after_sources=mp.stop_when_fields_decayed(50, mp.Ez, pt, 1e-6))

✓ MEEP Docker 실행 검증: T=0.94, R=0.06 (정상)
```

---

## 3. 파이프라인 설계

### Phase 1: Error Pattern Matrix (즉시 구현 가능)

**아이디어**: 각 에러 타입별로 (원인 파라미터 → 증상 → 수정) 행렬 구성

```
에러 타입         | 파라미터 조건              | 수정
-----------------|---------------------------|---------------------------
Divergence/NaN   | resolution < 10           | resolution *= 2
Divergence/NaN   | PML < 0.5*wvl             | dpml = max(1.0, wvl)
Divergence/NaN   | dt 명시 + 큰 값           | dt 제거 (자동 계산)
T > 1.0          | eig_band=0                | eig_band=1
T > 1.0          | 노말라이제이션 누락         | norm_run 추가
MPI Abort        | np > cell_volume/res      | np 줄이기
AttributeError   | 구버전 API 사용            | 신 API로 교체
```

### Phase 2: Simulation-Verified Fix DB (핵심)

```
┌─────────────────────────────────────────────────────────────┐
│              Verified Fix Builder                            │
│                                                             │
│  1. Template Library                                        │
│     ├── 기본 waveguide (SOI 220nm)                          │
│     ├── ring resonator                                      │
│     ├── EigenMode source                                    │
│     ├── adjoint optimization                                │
│     └── MPB bandstructure                                   │
│                                                             │
│  2. Bug Injector (확장판)                                   │
│     ├── 현재: 8가지 버그 유형                                │
│     └── 목표: 30가지 버그 유형 (파라미터 값 범위 포함)       │
│                                                             │
│  3. Docker 실행 (meep-pilot-worker)                         │
│     ├── 버그 있는 코드 실행 → error traceback 캡처          │
│     ├── LLM 자동 수정 코드 생성                             │
│     └── 수정 코드 실행 → T/R 값 검증                        │
│                                                             │
│  4. 결과 저장 (sim_errors)                                  │
│     ├── original_code (버그 있는 코드)                      │
│     ├── fixed_code (수정 코드)                              │
│     ├── error_message (실제 traceback)                      │
│     ├── fix_description (한국어 설명 + 코드 diff)            │
│     ├── verification_result {T, R, exit_code}               │
│     └── fix_worked=1 (검증 통과)                            │
└─────────────────────────────────────────────────────────────┘
```

### Phase 3: 검색 정밀도 개선

**문제**: 지금 "Divergence" 태그만 보고 검색 → 관계없는 결과
**해결**: 에러 메시지 + 코드 파라미터 동시 매칭

```python
# 개선된 search_db 로직
def search_db_v2(error_info, code, error):
    # 1. 에러 메시지 핵심 토큰 추출
    #    "diverged at t=42.5" → token: "diverged", "NaN", "decay"
    
    # 2. 코드에서 파라미터 추출
    #    resolution=20 → low_resolution=True
    #    PML(1.0) → pml_ok=True
    
    # 3. verified fix DB에서 파라미터 조건 매칭
    #    WHERE error_type='Divergence' 
    #      AND fix_keywords LIKE '%resolution%'
    #      AND fix_worked=1
    
    # 4. fix_description에서 코드 diff 추출
    #    수정 코드를 직접 반환 (텍스트가 아닌 코드)
```

---

## 4. 구현 계획 (단계별)

### Step 1: Bug Catalog 확장 (1-2일)
현재 8가지 → 30가지로 확장

```python
# 추가할 버그 유형
NEW_BUGS = [
    # Divergence 계열
    {"name": "resolution_too_low_large_cell",  # 셀 크기에 비례
     "error_type": "Divergence",
     "find": r'resolution\s*=\s*(\d+)',
     "transform": lambda m: f"resolution={max(1, int(m.group(1))//4)}",
     "fix": "resolution을 셀 크기의 최소 10배로 설정"},
    
    {"name": "pml_too_thin_relative",  # 파장 대비 PML
     "error_type": "Divergence",
     "fix": "dpml = max(1.0, 0.5/fcen) — 최소 반파장 이상"},
    
    {"name": "courant_violation",  # dt 직접 지정
     "error_type": "Divergence",
     "fix": "dt 파라미터 제거 (MEEP 자동 계산이 항상 안전)"},
    
    # T > 1.0 계열
    {"name": "missing_normalization",
     "error_type": "Efficiency",
     "fix": "normalization run 추가 후 in_flux로 나누기"},
    
    {"name": "monitor_inside_source",
     "error_type": "Efficiency", 
     "fix": "flux monitor를 source 영역 바깥으로 이동"},
    
    # EigenMode 계열
    {"name": "wrong_eig_parity_3d",
     "error_type": "EigenMode",
     "fix": "3D에서는 eig_parity=mp.NO_PARITY 또는 mp.EVEN_Y"},
    
    {"name": "eig_center_outside_waveguide",
     "error_type": "EigenMode",
     "fix": "EigenModeSource center를 도파로 중심으로 맞추기"},
    
    # Adjoint 계열
    {"name": "missing_reset_meep",
     "error_type": "Adjoint",
     "fix": "반복 최적화 전 sim.reset_meep() 필수"},
    
    {"name": "design_region_mismatch",
     "error_type": "Adjoint",
     "fix": "MaterialGrid 크기 = Nx × Ny = resolution × 설계영역"},
    
    # MPI 계열
    {"name": "too_many_procs",
     "error_type": "MPIError",
     "fix": "mpirun -np는 최대 셀_볼륨/(최소청크크기) 이하로"},
]
```

### Step 2: Verified Fix Builder 스크립트 (tools/verified_fix_builder.py)

```python
"""
1. 패턴 + 버그 조합 (original buggy code)
2. Docker에서 실행 → error 캡처
3. LLM으로 fix code 생성
4. Docker에서 fix 실행 → T/R 검증
5. fix_worked=1이면 sim_errors 저장
"""

class VerifiedFixBuilder:
    def __init__(self, kb_url, docker_container):
        self.kb = kb_url
        self.docker = docker_container
    
    def build_one(self, buggy_code, bug_info):
        # Step 1: run buggy
        err_code, err_out = run_in_docker(buggy_code)
        if err_code == 0:
            return None  # 버그 효과 없음
        
        error_msg = parse_error(err_out)
        
        # Step 2: LLM fix
        fixed_code = llm_fix(buggy_code, error_msg, bug_info["fix_hint"])
        
        # Step 3: verify fix
        fix_code, fix_out = run_in_docker(fixed_code)
        if fix_code != 0:
            return None  # 수정도 실패
        
        # Step 4: parse T/R
        result = parse_numeric(fix_out)
        if not result.is_physical():
            return None  # T+R > 1.1 등
        
        # Step 5: save
        return {
            "original_code": buggy_code,
            "fixed_code": fixed_code,
            "error_message": error_msg,
            "fix_description": generate_korean_explanation(bug_info, result),
            "verification": {"T": result.T, "R": result.R, "exit": 0},
            "fix_worked": 1,
            "source": "verified_fix",
        }
```

### Step 3: 진단 응답 포맷 개선

현재 반환:
```json
{"solution": "It looks like it is getting confused between the real type..."}
```

목표 반환:
```json
{
  "fix_code_diff": "- resolution=20\n+ resolution=40",
  "fix_explanation": "resolution=20은 10x10 셀에서 발산 위험...",
  "verification": {"T": 0.94, "R": 0.06},
  "confidence": "MEEP 검증됨"
}
```

### Step 4: diagnose_engine.py 개선

```python
# verified_fix 소스 우선 반환
if row["source"] in ("verified_fix", "marl_auto", "error_injector"):
    score = 0.95  # 최상위 우선순위
    # fix_description에서 코드 diff 파싱해서 code 필드로
    code_block = extract_code_from_fix_desc(row["fix_description"])
else:
    score = 0.75  # github 텍스트는 낮은 점수 유지
```

---

## 5. 수집 목표

| 소스 | 현재 | 목표 | 방법 |
|------|------|------|------|
| verified_fix (신규) | 0 | 300 | VerifiedFixBuilder |
| error_injector | 50 | 200 | Bug Catalog 확장 |
| marl_auto | 3 | 50+ | MARL 배치 지속 |
| github_issue | 242 | 유지 | 키워드 보조용 |
| github_structured | 151 | 유지 | 보조용 |

**총 목표**: 검증된 코드 수정 쌍 **500건** (verified_fix+error_injector+marl_auto)

---

## 6. 구현 우선순위

```
즉시 (오늘):
  ① ErrorInjector 재실행 (DB sync 이슈 해결) → 200건 목표
  ② diagnose_engine: verified_fix/marl_auto/error_injector score=0.95 우선화
  ③ fix_description에서 코드 블록 추출 → code 필드로 분리

단기 (이번 주):
  ④ Bug Catalog 30가지로 확장
  ⑤ verified_fix_builder.py 구현 (LLM fix + Docker verify 자동화)
  ⑥ 한국어 fix_description 생성기 (파라미터 값 포함)

중기:
  ⑦ 코드 파라미터 추출기 (resolution, PML, sources 파싱)
  ⑧ 파라미터 조건 기반 검색 (resolution<20 AND cell_size>8 → Divergence)
  ⑨ 진단 응답에 코드 diff 표시 (Before/After)
```

---

## 7. 성공 기준

사용자가 `Simulation diverged, resolution=20` 입력 시:
- ✅ "resolution을 40 이상으로 올리세요" + 수정 코드 반환
- ✅ `fix_worked=1` MEEP 검증된 결과
- ✅ T=0.9x, R=0.0x 검증 값 표시
- ❌ GitHub discussion 텍스트 반환 안 함
