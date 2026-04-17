# CIS 논문 자동 재현 시스템 아키텍처
> 목표: 새 논문 → 오차 ≤5% 완전 자동화

---

## 핵심 통찰

```
오차 원인의 80% = 5개 이산 변수의 잘못된 조합

  A. cover_glass:    True / False          (2가지)
  B. ref_sim_type:   'air' / 'with_cover'  (2가지)
  C. stop_decay:     1e-3/1e-4/1e-6/1e-8  (4가지)
  D. source_count:   1 / 2                (2가지)
  E. sipd_material:  'Air' / 'SiO2'       (2가지)

전체 조합: 2×2×4×2×2 = 64가지
res=20으로 빠른 테스트: 각 2-10분
→ 색분리 방향으로 필터링 → 10개 이하로 축소
→ res=50 최종: 1-3개 후보
```

---

## 3단계 자동화 아키텍처

```
[Stage 1] 파라미터 추출
    PDF → param_extractor (LLM + 규칙)
    → 5개 이산 변수 초기 추정 (메타데이터 기반)

[Stage 2] 가설 생성 + 빠른 검증 (Hypothesis Loop)
    초기 후보 64개 → 메타데이터 필터 → 10-20개
    → res=20 병렬 실행
    → 색분리 방향 체크 → 3-5개 생존
    → 오차 계산 → 최적 후보 선택

[Stage 3] 최종 실행 + 학습
    best candidate → res=50 실행
    오차 ≤5%: 완료 → DB 저장
    오차 >5%: 추가 탐색 or 수동 개입 요청
    모든 결과 → error_patterns.json 업데이트
```

---

## 메타데이터 기반 초기 필터링 규칙

```python
# FL 길이에 따른 stop_decay 추정
FL_TO_DECAY = {
    "FL < 1.5": ["1e-3", "1e-4"],       # 짧은 초점
    "1.5 ≤ FL < 3.0": ["1e-6", "1e-4"], # 중간
    "FL ≥ 3.0": ["1e-8", "1e-6"],       # 긴 초점 (필수 1e-8)
}

# 설계 타입에 따른 cover_glass 추정
DESIGN_TO_COVER = {
    "discrete_pillar":  [True, True],   # 대부분 있음
    "materialgrid":     [True, True],
    "sparse":           [False, True],  # SMA는 없음 (논문마다 다름)
    "cylinder":         [True, False],
}

# ref_sim_type 추정 (cover_glass 있으면 with_cover 시도)
def estimate_ref_sim(cover_glass):
    return ["with_cover", "air"] if cover_glass else ["air"]
```

---

## Hypothesis Loop 구현 계획

```python
class HypothesisLoop:
    def __init__(self, params, target_err=5.0):
        self.params     = params
        self.target_err = target_err
        self.history    = []  # 시도 결과 저장
    
    def generate_candidates(self):
        """메타데이터 기반 후보 조합 생성"""
        FL = self.params['FL_thickness']
        dt = self.params['design_type']
        
        # FL 길이로 stop_decay 후보 결정
        if FL >= 3.0:
            decays = ["1e-8", "1e-6"]
        elif FL >= 1.5:
            decays = ["1e-6", "1e-4"]
        else:
            decays = ["1e-3", "1e-6"]
        
        # 설계 타입으로 cover_glass 후보 결정
        covers = [True, False] if dt == "sparse" else [True]
        
        candidates = []
        for decay in decays:
            for cover in covers:
                for ref in (["with_cover", "air"] if cover else ["air"]):
                    for src_cnt in [2]:  # 항상 2 (Ex+Ey)
                        for sipd in (["SiO2"] if dt == "sparse" else ["Air"]):
                            candidates.append({
                                "stop_decay":    decay,
                                "cover_glass":   cover,
                                "ref_sim_type":  ref,
                                "source_count":  src_cnt,
                                "sipd_material": sipd,
                            })
        return candidates
    
    def quick_validate(self, candidate):
        """res=20으로 색분리 방향만 확인 (2-5분)"""
        eff = run_simulation(res=20, **candidate)
        
        # 색분리 방향 체크
        ok_R = eff['R'] > 0.15   # R이 최소 15% 이상
        ok_B = eff['B'] > 0.15   # B가 최소 15% 이상
        ok_G = eff['G'] > 0.10
        direction_ok = ok_R and ok_B and ok_G
        
        return {
            "candidate": candidate,
            "eff_20": eff,
            "direction_ok": direction_ok,
            "score": eff['R'] + eff['G'] + eff['B'],  # 합산 효율
        }
    
    def run(self):
        candidates = self.generate_candidates()
        print(f"[HypLoop] {len(candidates)}개 후보 생성")
        
        # Step 1: res=20 빠른 검증
        results = [self.quick_validate(c) for c in candidates]
        survivors = [r for r in results if r['direction_ok']]
        
        if not survivors:
            # 방향이 맞는 게 없음 → 전체 재시도 또는 수동 개입
            return self.escalate()
        
        # Step 2: 상위 3개만 res=50 실행
        survivors.sort(key=lambda x: -x['score'])
        top3 = survivors[:3]
        
        best = None
        for r in top3:
            eff50 = run_simulation(res=50, **r['candidate'])
            err = calc_error(eff50, self.params['target_efficiency'])
            if err <= self.target_err:
                best = (r['candidate'], eff50, err)
                break
        
        # Step 3: 결과 → DB 업데이트
        if best:
            update_error_patterns(self.params['paper_id'], best[0])
        
        return best
```

---

## 학습 루프 (error_patterns 자동 업데이트)

```python
def update_error_patterns(paper_id, winning_config):
    """성공한 설정을 DB에 저장 → 다음 논문에 활용"""
    ep = load_error_patterns()
    
    ep["paper_specific"][paper_id] = {
        "confirmed_errors": [],  # 자동 발견된 버그들
        "overrides": winning_config,
        "auto_discovered": True,
        "discovery_date": datetime.now().isoformat(),
    }
    
    # meep-kb DB에도 저장
    save_to_meep_kb(paper_id, winning_config)
    
    # 유사 논문 패턴 업데이트
    # (FL > 3μm → stop_decay=1e-8 규칙 강화)
    update_global_rules(paper_id, winning_config)
```

---

## 전체 파이프라인 (새 논문 투입 시)

```
새 논문 (PDF/텍스트)
    │
    ▼ param_extractor.py (LLM + 규칙)
    │  → 치수: SP, Layer, FL, tile_w, n_material
    │  → 5개 이산변수: 초기 추정
    │
    ▼ error_patterns.json 조회
    │  → 유사 논문 존재? → 해당 설정 우선 시도
    │  → 없으면 FL/design_type 기반 추정
    │
    ▼ HypothesisLoop (최대 20개 후보)
    │  → res=20 병렬 실행 (색분리 방향 체크)
    │  → 상위 3개 → res=50
    │  → 오차 ≤5%? → 완료
    │         > 5%? → 추가 탐색 (Bayesian or grid)
    │
    ▼ 결과 저장
       → error_patterns 업데이트 (학습)
       → meep-kb examples 저장
       → 3패널 플롯 + HTML 보고서
```

---

## 구현 우선순위

| 우선순위 | 컴포넌트 | 설명 |
|---------|---------|------|
| 1 | `hypothesis_generator.py` | 5개 변수 조합 생성 + 메타데이터 필터 |
| 2 | `quick_validator.py` | res=20 색분리 방향 체크 |
| 3 | `hypothesis_loop.py` | 전체 탐색 루프 오케스트레이터 |
| 4 | `pattern_learner.py` | 성공 설정 → DB 업데이트 |
| 5 | SimServer 병렬화 | 20개 후보를 동시 실행 |
