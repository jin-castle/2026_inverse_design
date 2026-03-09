# MEEP 특화 LLM Fine-tuning 계획
> meep-kb 데이터를 활용해 MEEP 에러 진단에 특화된 LLM 만들기

---

## 1. Fine-tuning이 뭔가 — 개념부터

### 일반 LLM vs Fine-tuned LLM
```
일반 LLM (Claude, GPT, Llama)
└── "세상 모든 것"을 알지만 MEEP 세부 에러엔 약함
    예: eig_band=0 버그를 정확히 모름, 출력 형식 제멋대로

Fine-tuned MEEP LLM
└── "MEEP 에러 진단"에만 특화
    예: eig_band=0 → 즉시 "1부터 시작해야 함" 정확한 답변
        출력 형식: 항상 에러타입 / 원인 / 수정코드 형태로 통일
```

### 학습 단계 비유
```
Pre-training  → 중학교: 언어 자체를 배움 (Claude가 이미 한 것)
Fine-tuning   → 대학원: MEEP 논문만 파고들어 전문가가 됨  ← 지금 목표
RLHF          → 인턴십: 사람 피드백으로 더 정확해짐 (선택)
```

---

## 2. 어떤 모델을 Fine-tuning 할 것인가

### 옵션 A: 오픈소스 (권장 — 완전 제어 가능)
| 모델 | 파라미터 | 필요 VRAM | 추천 이유 |
|------|---------|---------|---------|
| **Llama 3.2 3B** | 3B | 8GB | 가벼움, 로컬 실행 가능 |
| **Qwen2.5-Coder-7B** | 7B | 16GB | 코드에 특화 ← **최우선 추천** |
| **DeepSeek-Coder-7B** | 7B | 16GB | 코드 특화, 저렴 |
| Llama 3.1 8B | 8B | 20GB | 범용 성능 좋음 |

### 옵션 B: API 기반 (쉽지만 비용 발생)
| 서비스 | 장점 | 단점 |
|--------|------|------|
| OpenAI Fine-tuning | API로 간단 | gpt-4o-mini만 가능, 데이터 외부 전송 |
| Anthropic Fine-tuning | Claude 품질 | 현재 제한적 공개 |
| Together.ai | 오픈소스 모델 API 파인튜닝 | 비용 |

**Jin 환경 추천: Qwen2.5-Coder-7B** (SimServer 128코어 + A100 GPU 있으면 가능)

---

## 3. Fine-tuning 방법론 — LoRA/QLoRA (필수 이해)

### 왜 LoRA인가?
```
Full Fine-tuning: 전체 70억 파라미터 모두 업데이트
→ A100 GPU 여러 장 필요, 수백 GB 메모리, 너무 비쌈

LoRA (Low-Rank Adaptation): 
→ 전체 파라미터는 그대로 두고 "작은 어댑터"만 학습
→ 실제 학습 파라미터: 전체의 0.1~1% 수준
→ 16GB GPU 1장으로도 가능, 100배 저렴
```

### LoRA 작동 원리 (간단히)
```python
# 기존 가중치 행렬 W (7B 파라미터 중 일부, 예: 4096 x 4096)
W_original = [고정, 변경 안 함]

# LoRA 어댑터: 작은 두 행렬의 곱
# A: 4096 x 8 (rank=8)
# B: 8 x 4096
# 실제 업데이트 = W + A×B  (학습하는 건 A, B만)

# 결과: 전체 파라미터 0.05%만 학습 → 90%+ 성능 유지
```

### QLoRA = LoRA + 양자화
```
QLoRA = 모델을 4bit로 압축(양자화) + LoRA 적용
→ 7B 모델을 5GB VRAM으로 학습 가능
→ SimServer에서 실행 가능한 현실적 방법
```

---

## 4. 학습 데이터 구축 — 가장 중요한 단계

### 데이터 형식: "Instruction-Following" 형식
```json
{
  "instruction": "다음 MEEP 코드에서 발생한 에러를 진단하고 수정 방법을 알려주세요.",
  "input": "코드:\n```python\nsources = [mp.EigenModeSource(..., eig_band=0)]\n```\n에러:\nEfficiency > 100% detected",
  "output": "## 에러 진단\n**에러 타입**: EigenMode 설정 오류\n**원인**: eig_band=0은 잘못됨. MEEP에서 모드 번호는 1부터 시작합니다.\n\n## 수정 코드\n```python\nsources = [mp.EigenModeSource(..., eig_band=1)]  # TE0 = band 1\n```\n\n## 설명\nMEEP의 EigenModeSource는 1-indexed입니다. band=0 사용 시 정의되지 않은 모드를 참조해 에너지 비보존이 발생합니다."
}
```

### meep-kb에서 데이터 추출 방법

#### 소스 1: sim_errors 테이블 (현재 255개)
```python
# tools/export_finetune_data.py
SELECT error_message, context, fix_description, fix_applied, root_cause
FROM sim_errors WHERE fix_worked=1
# → instruction-following 형식으로 변환
```

#### 소스 2: errors 테이블 GitHub Issues (596개)
```python
# error_msg(제목) + cause(질문) + solution(해답) 쌍
# 이미 에러-해결 형식으로 완벽한 학습 데이터
```

#### 소스 3: examples 테이블 (611개 코드 예제)
```python
# "이 MEEP 코드가 하는 일을 설명하라" 형식
# description_ko + code → instruction 쌍
```

#### 소스 4: typee_err + typee_fixed 파일들 (50개+)
```
typee_err_336.txt  → 에러 메시지
typee_fixed_336.py → 수정된 코드
→ 완벽한 before-after 쌍
```

#### 소스 5: 합성 데이터 생성 (Claude로 자동 생성)
```python
# 알려진 에러 패턴 10개로 → 변형된 예시 100개 생성
# 같은 eig_band 오류지만 다른 코드 구조로 표현
→ 데이터 다양성 확보
```

### 목표 데이터셋 규모
| 단계 | 데이터 수 | 예상 성능 |
|------|---------|---------|
| 최소 | 500개 | 기본 MEEP 용어/형식 학습 |
| 권장 | 2,000개 | 주요 에러 패턴 커버 |
| 목표 | 5,000개+ | 전문가 수준 진단 |

---

## 5. 학습 파이프라인 단계별 상세

### Step 1: 환경 준비 (SimServer에서)
```bash
# SimServer (166.104.35.108) 접속
ssh user@166.104.35.108

# 환경 확인
nvidia-smi  # GPU 확인 (A100 있으면 최적)
python --version  # Python 3.10+

# 패키지 설치
pip install transformers datasets peft trl bitsandbytes accelerate
pip install wandb  # 학습 모니터링 (선택)
```

### Step 2: 데이터 준비
```bash
# meep-kb에서 데이터 내보내기
python tools/export_finetune_data.py \
  --db db/knowledge.db \
  --output finetune_data/meep_dataset.jsonl \
  --min_solution_len 50

# 결과: finetune_data/meep_dataset.jsonl
# 형식: {"instruction": ..., "input": ..., "output": ...}

# 데이터 검증
python tools/validate_finetune_data.py finetune_data/meep_dataset.jsonl
# → 중복 제거, 길이 필터, 품질 검사
```

### Step 3: 학습 스크립트 실행
```bash
# QLoRA Fine-tuning (권장)
python finetune/train_qlora.py \
  --base_model Qwen/Qwen2.5-Coder-7B-Instruct \
  --data finetune_data/meep_dataset.jsonl \
  --output_dir models/meep-coder-v1 \
  --num_epochs 3 \
  --batch_size 4 \
  --lora_rank 16 \
  --lora_alpha 32 \
  --max_seq_length 2048 \
  --bf16 True

# 학습 시간 예상:
# 2000개 데이터 x 3 epoch = A100 1장 기준 약 2~4시간
```

### Step 4: 평가
```bash
# MEEP 전용 벤치마크 테스트
python finetune/evaluate.py \
  --model models/meep-coder-v1 \
  --test_data finetune_data/test_set.jsonl

# 평가 지표:
# - 에러 타입 분류 정확도
# - 수정 코드의 Python 문법 유효성
# - 사람 평가 (해결책이 실제로 도움이 됐는가)
```

### Step 5: 배포
```bash
# 모델을 meep-kb API에 통합
# api/main.py의 LLM 폴백 부분을 로컬 모델로 교체

# Ollama로 서빙 (가장 간단)
ollama create meep-coder -f finetune/Modelfile
ollama serve  # port 11434

# FastAPI에서 호출
import ollama
response = ollama.chat(model='meep-coder', messages=[...])
```

---

## 6. 핵심 파일 구조 (구현 대상)

```
meep-kb/
├── finetune/
│   ├── train_qlora.py         ← QLoRA 학습 메인 스크립트
│   ├── evaluate.py            ← 평가 스크립트
│   ├── Modelfile              ← Ollama 배포용
│   └── config/
│       └── lora_config.yaml   ← LoRA 하이퍼파라미터
└── tools/
    ├── export_finetune_data.py ← DB → JSONL 변환
    ├── validate_finetune_data.py
    └── augment_data.py        ← Claude로 합성 데이터 생성
```

---

## 7. 실용적 비용/시간 예상

### 시나리오 A: SimServer GPU 사용 (최우선)
```
조건: NVIDIA A100 80GB 1장 (SimServer에 있는 경우)
데이터: 2,000개
모델: Qwen2.5-Coder-7B QLoRA

학습 시간: 2~4시간
비용: 전기세만 (사실상 무료)
결과: MEEP 에러 진단 전용 모델
```

### 시나리오 B: Google Colab Pro
```
비용: 월 $10 (Colab Pro)
A100 40GB 세션: 최대 24시간
학습 시간: 3~6시간
→ 1회성 실험에 적합
```

### 시나리오 C: Together.ai API
```
Llama-3.1-8B fine-tuning
비용: $1~3 / 1M 토큰
2000개 데이터 ≈ $5~15
→ GPU 없을 때 대안
```

---

## 8. 기대 효과

### Before (현재)
- 진단 응답: LLM이 일반적인 추측 → 부정확
- 포맷: 매번 다른 형식으로 출력
- 속도: API 호출 비용 + 지연 발생

### After (Fine-tuning 후)
- 진단 응답: MEEP-specific 정확한 답변
- 포맷: 항상 "에러타입/원인/수정코드" 구조
- 속도: 로컬 실행 → 0.5초 이내 응답
- 오프라인 작동: 인터넷 없어도 진단 가능
- 지속 성장: 시뮬레이션 쌓일수록 재학습으로 더 정확해짐

---

## 9. 즉시 시작 가능한 작업 순서

### Phase 0 (오늘): 데이터 수출 스크립트
```
→ tools/export_finetune_data.py 작성
→ 현재 DB에서 뽑을 수 있는 데이터 수 파악
```

### Phase 1 (이번 주): 데이터 품질 개선
```
→ typee_err + typee_fixed 파일 전부 sim_errors 추가 (50개+)
→ Claude로 합성 데이터 500개 생성
→ 최종 학습 데이터셋: 1,000~2,000개 준비
```

### Phase 2 (다음 주): 학습 실행
```
→ SimServer GPU 확인 (nvidia-smi)
→ QLoRA 학습 스크립트 실행
→ 결과 평가
```

### Phase 3: 통합
```
→ meep-kb API에 로컬 모델 통합
→ LLM 폴백 비용 0원 달성
→ 재학습 주기 설정 (월 1회)
```

---

## 참고 자료

- **LoRA 원논문**: https://arxiv.org/abs/2106.09685
- **QLoRA 원논문**: https://arxiv.org/abs/2305.14314  
- **Hugging Face TRL**: https://github.com/huggingface/trl (가장 쉬운 구현)
- **Unsloth**: https://github.com/unslothai/unsloth (2배 빠른 QLoRA)
- **Qwen2.5-Coder**: https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct
