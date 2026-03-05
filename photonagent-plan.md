# PhotonAgent 고도화 계획
> 목표: 일반 Claude/GPT보다 MEEP 특화 답변이 뛰어난 AI Agent

---

## 핵심 전략: "경험 축적형 지식베이스"

일반 LLM은 인터넷 전체를 학습했지만 MEEP 코드를 실제로 실행해본 적이 없다.
PhotonAgent는 **실제 실행 결과 + 검증된 코드 + 에러-해결 쌍**을 축적하여 이를 넘는다.

```
일반 LLM:  인터넷 텍스트 → 패턴 매칭 → 답변 (검증 안 됨)
PhotonAgent: 실행된 코드 DB + 검증된 패턴 → 합성 → 답변 (실제 동작 보장)
```

---

## Phase 1: Knowledge Base 강화 (2~3주) ← 즉각 효과

### 1-1. Pattern DB 채우기 [최우선]

현재 patterns 테이블 0건 → 이게 가장 큰 문제.

**채워야 할 패턴 목록 (우선순위순):**

| 패턴 이름 | 설명 | 난이도 |
|-----------|------|--------|
| `plot_dft_field` | DFT field 플롯 전체 흐름 | 중 |
| `adjoint_setup` | OptimizationProblem 기본 세팅 | 상 |
| `eigenmode_source` | EigenModeSource 올바른 설정 | 중 |
| `pml_boundary` | PML 두께/위치 설정 패턴 | 하 |
| `convergence_check` | resolution 수렴 테스트 패턴 | 중 |
| `mpi_parallel_run` | MPI 병렬 실행 패턴 | 하 |
| `near_far_field` | 근-원거리장 변환 패턴 | 상 |
| `mode_converter_taper` | 모드 컨버터 테이퍼 설계 | 상 |
| `adjoint_callback_plot` | 최적화 중 field 시각화 | 상 |
| `3d_simulation_setup` | 3D SOI 기본 세팅 | 상 |

**패턴 스키마 (patterns 테이블):**
```sql
id, pattern_name, description, code_snippet, use_case,
tags, verified(bool), source, created_at
```

**검증된 코드 기준:** 실제 MEEP에서 에러 없이 실행된 코드만 등록.

### 1-2. 기존 DB 품질 개선

- **Examples**: 현재 601건 중 실제 실행 가능한 것만 `verified=True` 태깅
- **Errors**: cause/solution 비어있는 항목 채우기 (현재 상당수 null)
- **Docs**: MEEP 1.28 기준으로 outdated 문서 갱신

### 1-3. 크롤링 대상 추가

```
현재: MEEP ReadTheDocs + GitHub Issues
추가할 것:
  - MEEP GitHub Discussions (실전 Q&A 다수)
  - MEEP GitHub examples/ 폴더 전체
  - NanoComp 그룹 논문 supplementary code
  - Ab-Initio 포럼 아카이브
```

---

## Phase 2: Generator 고도화 (1~2주) ← 답변 품질 직결

### 2-1. LLM 업그레이드

```python
# 현재
model="claude-haiku-4-5"  # 저렴하지만 합성 능력 한계

# 변경
model="claude-sonnet-4-5"  # 복잡한 합성 가능, 비용 증가
# 단, 복잡한 질문(intent=concept_map, 복합 질문)에만 적용
# 단순 에러 검색(intent=error_debug)은 haiku 유지 → 비용 최적화
```

### 2-2. 합성형 프롬프트로 교체

```python
# 현재 프롬프트 방식: "DB 결과 요약해"
# 문제: 각 자료를 나열만 함, 통합 답변 없음

# 새 프롬프트 방식: "Tutorial 작성해"
SYSTEM_NEW = """당신은 MEEP 전문 튜터입니다.

[답변 형식 - 반드시 준수]
1. 개념 설명 (2-3문장)
2. 핵심 코드 (완전히 실행 가능한 형태)
3. 단계별 설명
4. 주의사항/흔한 실수 (DB의 error 자료 활용)
5. 참고 자료

[핵심 원칙]
- DB에 있는 검증된 코드만 사용
- DB에 없는 내용은 "(미검증)" 명시
- 에러 자료에서 흔한 실수를 반드시 포함
- Pattern 자료가 있으면 우선 사용"""
```

### 2-3. 멀티소스 합성 로직

```python
def build_context_structured(db_results):
    """타입별로 분리해서 LLM에게 역할 부여"""
    patterns  = [r for r in db_results if r['type'] == 'PATTERN']
    examples  = [r for r in db_results if r['type'] == 'EXAMPLE']
    errors    = [r for r in db_results if r['type'] == 'ERROR']
    docs      = [r for r in db_results if r['type'] == 'DOC']

    context = ""
    if patterns:
        context += "=== 검증된 패턴 (최우선 참고) ===\n"
        for p in patterns:
            context += f"[패턴] {p['title']}\n"
            context += f"설명: {p['cause']}\n"
            context += f"코드:\n```python\n{p['code']}\n```\n\n"

    if examples:
        context += "=== 실제 코드 예제 ===\n"
        for e in examples:
            context += f"[예제] {e['title']}\n```python\n{e['code'][:400]}\n```\n\n"

    if errors:
        context += "=== 흔한 에러 & 해결책 ===\n"
        for err in errors:
            context += f"⚠ {err['title']}\n"
            context += f"  원인: {err['cause']}\n"
            context += f"  해결: {err['solution']}\n\n"

    return context
```

### 2-4. 답변 품질 평가 루프

```python
# 답변 생성 후 자동 검증
def validate_answer(answer, db_results):
    checks = {
        "has_code": "```python" in answer,
        "has_explanation": len(answer) > 300,
        "cites_sources": any(f"[자료 {i}]" in answer for i in range(1,7)),
        "has_warnings": any(w in answer for w in ["주의", "⚠", "NOTE"]),
    }
    score = sum(checks.values()) / len(checks)
    # score < 0.6이면 재생성 (max 2회)
    return score, checks
```

---

## Phase 3: PhotonAgent Core (3~4주) ← 진짜 차별화

### 전체 아키텍처

```
사용자 질문
    ↓
[Intent Analyzer] → 코드 생성 요청인지 판단
    ↓
[Code Generator] → DB 패턴 기반 코드 생성
    ↓
[Execution Engine] → Docker에서 실제 실행
    ↓
[Error Detector] → 에러 발생 시
    ↓
[Auto Debugger] → meep-kb DB에서 해결책 검색 + 코드 수정
    ↓
[Re-execute] → 수정 코드 재실행 (최대 3회)
    ↓
[Human Feedback] → 최종 결과 + 피드백 수집
    ↓
[KB Updater] → 성공한 코드/에러쌍 → DB 자동 축적
```

### 3-1. 실행 엔진

```python
# api/execution_engine.py
import subprocess, tempfile, os

class MeepExecutor:
    """Docker 컨테이너에서 MEEP 코드 안전 실행"""

    TIMEOUT = 300  # 5분 타임아웃

    def run(self, code: str) -> dict:
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
            f.write(code.encode())
            tmp_path = f.name

        try:
            result = subprocess.run(
                ["docker", "exec", "meep-pilot-worker",
                 "conda", "run", "-n", "pmp", "python", tmp_path],
                capture_output=True, text=True,
                timeout=self.TIMEOUT
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stderr": "TIMEOUT", "stdout": ""}
        finally:
            os.unlink(tmp_path)
```

### 3-2. 자동 디버거

```python
class AutoDebugger:
    """에러 → KB 검색 → 코드 수정 → 재실행"""

    MAX_RETRIES = 3

    def debug_loop(self, code: str, error: str, query: str) -> dict:
        for attempt in range(self.MAX_RETRIES):
            # 1. 에러로 KB 검색
            solutions = search_kb(error, types=["errors", "patterns"])

            # 2. 수정된 코드 생성
            fixed_code = generate_fix(code, error, solutions)

            # 3. 재실행
            result = MeepExecutor().run(fixed_code)

            if result["success"]:
                return {
                    "success": True,
                    "code": fixed_code,
                    "attempts": attempt + 1,
                    "fixes_applied": solutions
                }

            # 다음 시도를 위해 에러 갱신
            error = result["stderr"]

        return {"success": False, "attempts": self.MAX_RETRIES}
```

### 3-3. KB 자동 축적

```python
# 성공한 코드 + 에러 쌍 → 자동으로 patterns/errors DB에 추가
class KBUpdater:
    def record_success(self, query, code, execution_result):
        """실행 성공한 코드 → patterns 테이블에 추가"""
        pattern = {
            "pattern_name": extract_pattern_name(query),
            "description": query,
            "code_snippet": code,
            "use_case": query,
            "verified": True,
            "source": "auto_generated"
        }
        insert_pattern(pattern)

    def record_error_fix(self, error_msg, fixed_code, solution):
        """에러 + 해결책 쌍 → errors 테이블에 추가"""
        # 다음에 같은 에러 나왔을 때 바로 해결
        insert_error(error_msg, solution, fixed_code)
```

---

## Phase 4: 평가 시스템 (1주)

### Claude/GPT 대비 우위 측정

```python
BENCHMARK_QUESTIONS = [
    "adjoint DFT field plot하는 방법",
    "EigenModeSource로 TE0 모드 입력하는 법",
    "시뮬레이션 발산 디버깅",
    "3D SOI 220nm 기본 구조 설정",
    "adjoint gradient NaN 에러 해결",
    # ... 20개
]

def evaluate(question):
    meep_kb_answer = call_meep_kb(question)
    claude_answer  = call_claude(question)

    scores = {
        "code_correctness": run_code_test(meep_kb_answer),  # 실제 실행 여부
        "specificity": measure_meep_specificity(meep_kb_answer),  # MEEP 특화도
        "completeness": measure_completeness(meep_kb_answer),     # 완성도
    }
    return scores
```

**meep-kb가 이기는 조건:**
- `code_correctness`: 실제 실행 가능한 코드 → Claude는 검증 안 됨
- `specificity`: Jin의 실제 프로젝트 파라미터(SOI 220nm, 1550nm) 반영
- `completeness`: 에러 DB 기반 주의사항 포함

---

## 실행 로드맵

| 기간 | 작업 | 예상 효과 |
|------|------|-----------|
| **1주차** | Pattern DB 10개 직접 작성 + 검증 | DFT/adjoint 질문 답변 품질 즉각 향상 |
| **2주차** | Generator 프롬프트 교체 + Sonnet 전환 | 답변 구조화 개선 |
| **3주차** | 크롤러 확장 (Discussions + examples/) | KB 규모 2배 |
| **4주차** | 실행 엔진 MVP | 코드 자동 검증 시작 |
| **5~6주차** | 자동 디버거 + KB 축적 루프 | Self-improving 시작 |
| **7주차** | 벤치마크 vs Claude/GPT | 우위 측정 |

---

## 가장 먼저 할 것 (이번 주)

**Pattern DB 10개 수동 작성이 ROI 최고.**

`plot_dft_field` 패턴 하나만 잘 만들어도 위 DFT field plot 질문에서 Claude를 이길 수 있음.
패턴은 실제 Jin이 MEEP 돌린 코드에서 검증된 것을 발췌하는 게 가장 좋음.

```bash
# patterns 테이블 확인
docker exec meep-kb-meep-kb-1 python -c "
import sqlite3
conn = sqlite3.connect('/app/db/knowledge.db')
print(conn.execute('SELECT COUNT(*) FROM patterns').fetchone())
print(conn.execute('PRAGMA table_info(patterns)').fetchall())
"
```
