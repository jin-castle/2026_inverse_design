# PhotonAgent > General LLM: 이론적 근거 및 실험 설계
> "왜 meep-kb가 Claude/GPT보다 MEEP 질문에 더 나은 답변을 생성할 수 있는가"

---

## 1. 이론적 프레임워크 (Information-Theoretic View)

### 1.1 문제 정의

MEEP 질문 q에 대해 정답 a*를 생성할 확률을 비교한다.

**General LLM (Parametric Only):**
```
P_LLM(a | q) ∝ exp( s(q, a; θ) )
```
- θ: 학습된 고정 파라미터
- s: 질문-답변 적합도 점수
- 문제: MEEP 관련 학습 데이터가 전체 학습 데이터의 극히 일부 → θ에 MEEP 지식이 희소하게 인코딩

**RAG 기반 PhotonAgent:**
```
P_RAG(a | q, D) = Σ_d P(a | q, d; θ) · P(d | q; φ)
```
- D: 검증된 MEEP 지식베이스
- φ: 검색 모델 파라미터
- d: 검색된 관련 문서

**핵심 이점:**
```
P_RAG(a* | q, D) >> P_LLM(a* | q)  when  ∃d ∈ D s.t. P(a* | q, d) → 1
```
DB에 검증된 정답 코드 d*가 있으면, 올바른 답변 생성 확률이 1에 수렴한다.

---

### 1.2 정보 이론 관점

**Mutual Information 분석:**

질문 q와 정답 a* 사이의 상호정보량:
```
I(a*; q) = H(a*) - H(a* | q)
```

General LLM의 경우 MEEP 특화 정보의 엔트로피:
```
H_LLM(a_MEEP | q) ≈ H_LLM(a_general | q) + ε_MEEP
```
여기서 ε_MEEP > 0: MEEP 특화 불확실성 (할루시네이션 확률)

RAG의 경우:
```
H_RAG(a_MEEP | q, D) < H_RAG(a_MEEP | q)  [조건부 엔트로피 감소]
H_RAG(a_MEEP | q, D) << H_LLM(a_MEEP | q)  [DB 조건화로 불확실성 대폭 감소]
```

**직관적 해석:**
- LLM: "이 API가 맞을 것 같은데..." (불확실)
- PhotonAgent: "이 코드는 실제로 실행된 것이다" (확실)

---

### 1.3 Code Correctness의 수학적 우위

MEEP API 호출 정확도를 모델링한다.

API 호출 a = f(args)의 정확성 P(correct):

**LLM 생성 코드:**
```
P_LLM(correct API call) = P(right function) × P(right args | right function)
                        = p_f × p_a
```
- p_f ≈ 0.85 (함수명은 잘 맞춤)
- p_a ≈ 0.60 (인자 조합은 자주 틀림, 예: eig_band=0 vs 1)
- **P_LLM ≈ 0.51**

**PhotonAgent (DB에 검증 코드 존재 시):**
```
P_RAG(correct API call | d*) = 1.0  (실행 검증된 코드)
P_RAG(correct API call | no match) = P_LLM = 0.51
P_RAG(correct API call) = P(d* retrieved) × 1.0 + (1 - P(d* retrieved)) × 0.51
```

검색 성능 P(d* retrieved) = 0.7 (현재 추정) → **P_RAG ≈ 0.85**

**N번의 API 호출이 모두 올바를 확률 (k=10개 API 호출 가정):**
```
P_LLM(all k correct)  = 0.51^10 ≈ 0.001  (0.1%)
P_RAG(all k correct)  = 0.85^10 ≈ 0.197  (19.7%)
```
→ **완전히 실행 가능한 코드 생성 확률: RAG가 LLM 대비 ~200배 높음**

---

## 2. 도메인 특화 지식 우위 (Knowledge Specificity)

### 2.1 Jin의 연구 환경 특화

일반 LLM이 모르는 것들:
```python
# General LLM이 생성할 가능성:
resolution = 20  # 임의의 값

# PhotonAgent (Jin의 verified 코드 기반):
resolution = 50  # SOI 220nm에서 수렴 확인된 값
# Si: n=3.48, SiO2: n=1.44 @ 1550nm
# PML: 1.0μm minimum, SiO2 extends to mp.inf
# MPI: -np 10 (local), -np 128 (SimServer)
```

이 정보는 공개된 인터넷에 없다. Jin의 실제 시뮬레이션에서만 나온다.

### 2.2 Specificity Score 정의

```
Specificity(answer) = |{domain-specific correct facts}| / |{total facts in answer}|

Specificity_LLM(MEEP answer) ≈ 0.40  (절반은 generic photonics, 일부 틀림)
Specificity_RAG(MEEP answer) ≈ 0.85  (DB의 Jin 코드 기반)
```

---

## 3. 실험 설계

### 3.1 벤치마크 테스트셋 구성

**N=50 MEEP 질문 (카테고리별):**

| 카테고리 | 문항 수 | 예시 |
|---------|---------|------|
| Error Debug | 15 | "adjoint 실행 중 NaN FOM", "eig_band 오류" |
| Code Generation | 15 | "DFT field plot", "EigenModeSource TE0 설정" |
| Concept Explanation | 10 | "PML이 뭐야", "adjoint gradient 원리" |
| Parameter Selection | 10 | "resolution 얼마로 해야 해", "PML 두께" |

**Ground Truth 생성:**
- 각 질문에 대해 실제 MEEP에서 실행 검증된 코드 답안 준비
- Jin이 직접 검토하여 정답 레이블링

### 3.2 평가 지표 (Metrics)

**M1: Code Execution Rate (CER)**
```
CER = (실행 오류 없는 코드 블록 수) / (전체 코드 블록 수)
측정: Docker MEEP 환경에서 자동 실행
기준: exit code == 0
```

**M2: API Accuracy (AA)**
```
AA = (올바른 MEEP API 호출 수) / (전체 MEEP API 호출 수)
측정: AST 파싱으로 함수명+인자 추출 후 공식 문서와 비교
```

**M3: Parameter Correctness (PC)**
```
PC = (SOI 플랫폼에 맞는 파라미터 수) / (전체 수치 파라미터 수)
예: resolution=50 ✓, n_Si=3.48 ✓, wavelength=1.55 ✓
측정: 정규식으로 수치 추출 후 허용 범위와 비교
```

**M4: Hallucination Rate (HR)**
```
HR = (사실과 다른 기술적 주장 수) / (전체 기술적 주장 수)
측정: 전문가(Jin) 수동 검토
낮을수록 좋음
```

**M5: Solution Completeness (SC)**
```
SC = ROUGE-L(generated_answer, ground_truth)
또는 LLM-as-Judge: "이 답변이 질문을 완전히 해결하는가?" (1-5점)
```

### 3.3 비교 대상

| 시스템 | 설명 |
|--------|------|
| **PhotonAgent** | meep-kb RAG + Sonnet |
| Claude Sonnet | API 직접 호출, 동일 질문 |
| GPT-4o | OpenAI API, 동일 질문 |
| meep-kb (Haiku, 이전) | 개선 전 베이스라인 |

### 3.4 실험 절차

```python
# 자동화 평가 스크립트 구조
for question in benchmark_questions:
    # 1. 각 시스템에서 답변 생성
    answers = {
        "photonagent": meep_kb_api(question),
        "claude":      claude_api(question),
        "gpt4o":       gpt4_api(question),
    }
    
    # 2. 코드 블록 추출
    for system, answer in answers.items():
        code_blocks = extract_code_blocks(answer)
        
        # 3. 자동 실행 테스트
        for code in code_blocks:
            result = docker_exec_meep(code)
            CER[system].append(result.success)
        
        # 4. API 정확도 체크
        api_calls = extract_meep_api_calls(answer)
        for call in api_calls:
            AA[system].append(verify_api_call(call))
    
    # 5. 수동 평가 (Jin)
    HR[system] = human_eval_hallucination(answers)
```

---

## 4. 예상 결과 및 가설

### 4.1 정량적 예측

| 지표 | PhotonAgent | Claude Sonnet | GPT-4o |
|------|-------------|---------------|--------|
| CER | **0.75+** | 0.35 | 0.40 |
| AA | **0.85+** | 0.70 | 0.68 |
| PC | **0.90+** | 0.45 | 0.43 |
| HR | **0.05-** | 0.25 | 0.28 |
| SC | **4.0+/5** | 3.2/5 | 3.1/5 |

### 4.2 PhotonAgent가 우세할 것으로 예상되는 이유

1. **CER**: DB에 실행 검증된 코드 → 직접 재사용
2. **PC**: Jin의 SOI 220nm 파라미터가 DB에 이미 저장됨
3. **HR**: DB 기반 grounding → 할루시네이션 억제

### 4.3 일반 LLM이 우세할 수 있는 경우

- DB에 없는 새로운 MEEP 기능 (최신 버전 API)
- 매우 일반적인 Python/numpy 질문
- 추상적 개념 설명 (수학적 유도)

→ **PhotonAgent의 한계이자 DB 확장의 필요성**

---

## 5. Self-Improving 메커니즘: 시간에 따른 우위 증가

```
t=0: PhotonAgent ≈ General LLM (DB 부족)
t=1: PhotonAgent > General LLM (패턴 축적)
t=∞: PhotonAgent >> General LLM (검증 코드 완전 커버리지)
```

**수식:**
```
Advantage(t) = f(|D_t|, quality(D_t), P(d* retrieved))
             ≈ α × log(|D_t|) + β × quality(D_t)
```

일반 LLM의 MEEP 지식은 학습 후 고정(static).
PhotonAgent의 D_t는 Jin이 연구를 진행할수록 계속 증가(dynamic).

**장기적으로 PhotonAgent는 Jin의 연구 결과를 축적하여, 세상 어떤 LLM도 가지지 못한 Jin-specific MEEP knowledge base를 보유하게 된다.**

---

## 6. 논문화 가능성

이 실험 설계는 다음 논문 주제로 발전 가능:

**제목 후보:**
- "Domain-Specific RAG Outperforms General LLMs in Photonic Simulation Debugging: A MEEP Case Study"
- "PhotonAgent: A Self-Improving AI System for Automated Photonic Device Design and Debugging"

**투고 대상:** CLEO 2026, ACS Photonics, Optics Express (툴/소프트웨어 섹션)
