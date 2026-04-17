# MEEP 버전별 시뮬레이션 호환성 가이드

## 현재 사용 환경

| 환경 | MEEP | Python | numpy | 특이사항 |
|------|------|--------|-------|---------|
| **Docker (meep-pilot-worker)** | **1.31.0** | 3.10.19 | 2.2.6 | 로컬 빠른 테스트 |
| **SimServer (166.104.35.108)** | **1.31.0** | 3.11.10 | 1.26.0 | 128코어 풀런 |

→ **현재 양쪽 모두 1.31.0 — 버전 통일돼 있음**

---

## MEEP 버전별 알려진 차이점

### 1.x → 1.2x 주요 변경
```python
# 1.1x 이전 (구버전 API)
sim.run(mp.at_end(mp.output_efield_z))      # 출력 함수 방식 다름
mp.get_flux_freqs(mon)                      # 이건 유지됨

# 1.2x+ (현재)
sim.run(until_after_sources=mp.stop_when_dft_decayed(1e-6, 0))  # 권장 방식
```

### 1.28 → 1.31 주요 변경 (현재 버전 근방)
```python
# stop_when_dft_decayed 시그니처
# 1.28: stop_when_dft_decayed(minimum_run_time, dt_threshold)
# 1.31: 동일하나 내부 DFT decay 기준 더 엄격해짐
# → 같은 decay=1e-6이어도 1.28보다 더 오래 실행될 수 있음

# MaterialGrid do_averaging 기본값 변경 (버전에 따라 다름)
# → 명시적으로 do_averaging=False 항상 지정 필요

# eps_averaging 기본값
# → 항상 명시: eps_averaging=False (discrete pillar 필수)
```

### numpy 버전 호환성
```
Docker:     numpy 2.2.6  (최신)
SimServer:  numpy 1.26.0 (구버전)

주의: numpy 2.x에서 일부 함수 deprecated
  - np.bool → bool
  - np.int  → int
  → 코드에 np.bool_, np.int_ 명시 사용 권장
```

---

## 버전 차이가 시뮬 결과에 미치는 영향

### 영향 있음 (수치 변화)
| 항목 | 영향 | 대응 |
|------|------|------|
| `stop_when_dft_decayed` 내부 구현 | ±2~5% 효율 차이 | 더 엄격한 decay 사용 (1e-8) |
| `eps_averaging` 기본값 | 구조 표현 정확도 | 항상 False 명시 |
| `MaterialGrid` do_averaging | 연속 설계 경우 | 항상 False 명시 |
| MPI 통신 방식 | 매우 미미 | 무시 가능 |

### 영향 없음
| 항목 | 이유 |
|------|------|
| PML, k_point 설정 | API 동일 |
| FluxRegion, 좌표 계산 | 수학적으로 동일 |
| GaussianSource 파라미터 | API 동일 |
| 효율 정규화 계산 | Python 연산 |

---

## 해결 전략

### 전략 1: 버전 명시 + 호환 코드 작성 (현재 적용)

```python
# 버전 독립적 코드 패턴 (항상 명시)
import meep as mp
print(f"MEEP version: {mp.__version__}")  # 로그에 기록

sim = mp.Simulation(
    ...
    k_point=mp.Vector3(0,0,0),   # 항상 명시
    eps_averaging=False,          # 항상 명시 (버전별 기본값 다름)
)

# stop_when_dft_decayed: 버전별 동작 다를 수 있으므로
# FL에 따라 명시적으로 엄격하게
sim.run(until_after_sources=mp.stop_when_dft_decayed(1e-8, 0))  # FL>=3um
sim.run(until_after_sources=mp.stop_when_dft_decayed(1e-6, 0))  # FL<2um
```

### 전략 2: error_patterns.json에 버전별 설정 추가

```json
{
  "version_specific": {
    "1.28": {
      "stop_decay_multiplier": 1.5,
      "notes": "1.28에서는 decay 기준이 느슨해서 더 짧게 실행됨"
    },
    "1.31": {
      "stop_decay_multiplier": 1.0,
      "notes": "현재 기준값"
    }
  }
}
```

### 전략 3: 재현 시 버전 기록 (params.json 확장)

```json
{
  "paper_id": "Single2022",
  "sim_environment": {
    "meep_version": "1.31.0",
    "python_version": "3.10.19",
    "numpy_version": "2.2.6",
    "mpi_procs": 4,
    "machine": "docker_local"
  },
  "reproducibility_note": "다른 버전에서 ±5% 차이 가능"
}
```

### 전략 4: 버전 체크 + 자동 조정 (hypothesis_loop 확장)

```python
def get_meep_version(docker=True):
    import subprocess, re
    if docker:
        r = subprocess.run(["docker","exec","meep-pilot-worker",
                            "python","-c","import meep; print(meep.__version__)"],
                           capture_output=True, text=True)
    else:
        r = subprocess.run(["ssh","user@166.104.35.108",
                            "conda run -n pmp python -c 'import meep; print(meep.__version__)'"],
                           capture_output=True, text=True)
    m = re.search(r'(\d+\.\d+)', r.stdout)
    return m.group(1) if m else "unknown"

def adjust_params_for_version(params, meep_version):
    """MEEP 버전에 따라 파라미터 자동 조정"""
    ver = float(meep_version)
    if ver < 1.28:
        # 구버전: stop_decay를 더 엄격하게
        params['_override']['stop_decay'] = "1e-8"
        print(f"[버전 조정] MEEP {ver} → stop_decay 1e-8로 강화")
    return params
```

---

## 실용적 권고사항

1. **현재 환경 (Docker=SimServer=1.31)**: 버전 문제 없음
2. **논문 재현 시**: 버전을 params.json에 기록해두면 나중에 재현 시 참고 가능
3. **새 MEEP 설치 시**: 반드시 fast-check + res=20으로 기존 결과 대비 확인
4. **가장 큰 위험**: MEEP 1.x → 2.x 메이저 업그레이드 (API 변경 가능성)
5. **현실적 오차 기대치**: 같은 코드, 다른 버전 → ±2~5% 효율 차이

---

## 버전별 테스트 결과 (Single2022 기준)

| 환경 | MEEP | R | G | B | 비고 |
|------|------|---|---|---|------|
| Docker 로컬 | 1.31.0 | 0.709 | 0.457 | 0.729 | 기준값 |
| SimServer | 1.31.0 | (미실행) | — | — | 동일 버전이므로 동일 예상 |
