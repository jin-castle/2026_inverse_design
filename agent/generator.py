#!/usr/bin/env python3
"""
Generator — DB 기반 Grounded RAG 답변 생성

원칙:
- 주의사항 + 검증된 코드가 메인 (파이프라인 컨텍스트는 보조)
- DB에 있는 내용만 사용 (할루시네이션 최소화)
- 항상 한국어로 답변
- 답변 하단에 참조 출처 인용 + 다음 단계 미리보기
- DB에 없는 내용은 절대 지어내지 않음

v2: pipeline_category / pipeline_stage 컨텍스트 + next step preview 추가
"""

import os
import sqlite3

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FEEDBACK_DB: str = ""   # startup에서 주입

# 모든 의도에 Sonnet 사용
INTENT_MODEL_MAP = {
    "error_debug":  "claude-sonnet-4-5",
    "concept_map":  "claude-sonnet-4-5",
    "code_example": "claude-sonnet-4-5",
    "doc_lookup":   "claude-sonnet-4-5",
    "unknown":      "claude-sonnet-4-5",
}


# ── 피드백 기반 Few-shot 예시 조회 ─────────────────────────────────────────────
def _get_feedback_examples(query: str, n: int = 3) -> list:
    """
    feedback.db에서 도움된 Q&A 쌍을 조회.
    - helpful=1 (도움됨) + answer_text 있는 것만
    - 쿼리 키워드 겹침으로 유사도 필터
    - 결과: [{"query": ..., "answer": ...}, ...]
    """
    if not FEEDBACK_DB:
        return []
    try:
        conn = sqlite3.connect(FEEDBACK_DB, timeout=5)
        rows = conn.execute(
            """SELECT query, answer_text FROM feedback
               WHERE helpful = 1
                 AND answer_text != ''
                 AND length(answer_text) > 100
               ORDER BY id DESC
               LIMIT 100"""
        ).fetchall()
        conn.close()
    except Exception:
        return []

    if not rows:
        return []

    # 키워드 겹침 기반 간단 유사도
    query_words = set(query.lower().split())
    scored = []
    for q_text, a_text in rows:
        row_words = set(q_text.lower().split())
        overlap = len(query_words & row_words)
        if overlap >= 1:
            scored.append((overlap, q_text, a_text))

    # 겹침 많은 순으로 정렬
    scored.sort(reverse=True)

    # 중복 질문 제거 (앞 30자 기준)
    seen_q = set()
    result = []
    for _, q, a in scored[:n * 3]:
        key = q[:30]
        if key not in seen_q:
            seen_q.add(key)
            result.append({"query": q, "answer": a[:600]})
        if len(result) >= n:
            break

    return result


def _build_fewshot_block(examples: list) -> str:
    """Few-shot 예시를 프롬프트 블록으로 변환"""
    if not examples:
        return ""
    lines = ["=== 이전에 도움이 됐던 답변 사례 (참고용) ==="]
    for i, ex in enumerate(examples, 1):
        lines.append(f"\n[사례 {i}] 질문: {ex['query']}")
        lines.append(f"답변 요약: {ex['answer'][:400]}")
    lines.append("=" * 40)
    return "\n".join(lines)


def _build_context(db_results: list) -> str:
    """DB 결과를 LLM 컨텍스트 문자열로 변환 — PATTERN 우선, 타입별 구조화"""
    if not db_results:
        return ""

    # 타입별 분리 (PATTERN 최우선)
    patterns  = [r for r in db_results if r.get("type") == "PATTERN"]
    examples  = [r for r in db_results if r.get("type") == "EXAMPLE"]
    errors    = [r for r in db_results if r.get("type") == "ERROR"]
    docs      = [r for r in db_results if r.get("type") == "DOC"]
    ordered   = patterns + examples + errors + docs

    lines = []
    for i, r in enumerate(ordered[:7], 1):
        rtype  = r.get("type", "?")
        title  = r.get("title", "")
        score  = r.get("score", 0)
        cause  = r.get("cause", "").strip()
        sol    = r.get("solution", "").strip()
        code   = r.get("code", "").strip()
        url    = r.get("url", "")
        cat    = r.get("category", "").strip()

        lines.append(f"[자료 {i}] [{rtype}] {title} (유사도: {score:.2f})")

        if rtype == "PATTERN":
            if cause:
                lines.append(f"  • 설명: {cause[:500]}")
            if cat:
                lines.append(f"  • 용도: {cat[:200]}")
            if code:
                lines.append(f"  • 검증된 코드:\n```python\n{code[:600].strip()}\n```")
        elif rtype == "ERROR":
            if cause:
                lines.append(f"  • 원인: {cause[:400]}")
            if sol:
                lines.append(f"  • 해결: {sol[:400]}")
            if code:
                lines.append(f"  • 코드:\n```python\n{code[:300].strip()}\n```")
        elif rtype == "EXAMPLE":
            if cause:
                lines.append(f"  • 설명: {cause[:300]}")
            if code:
                lines.append(f"  • 코드:\n```python\n{code[:500].strip()}\n```")
        elif rtype == "DOC":
            if cause:
                lines.append(f"  • 내용: {cause[:400]}")

        if url:
            lines.append(f"  • 출처: {url}")
        lines.append("")

    return "\n".join(lines)


# ── 파이프라인 prerequisite 정의 ──────────────────────────────────────────────
# (category, stage_idx) -> prerequisite 체크리스트
_PREREQUISITES = {
    ("env_setup",     0): [],
    ("geometry",      0): ["Cat.1 — resolution, cell_size, PML, 재료 정의"],
    ("design_region", 0): ["Cat.1 — resolution, cell_size, PML 정의",
                            "Cat.2 — geometry + 레이아웃 플롯 확인"],
    ("sim_setup",     0): ["Cat.1 — resolution, cell_size, PML 정의",
                            "Cat.2 — geometry 구성",
                            "Cat.3 — MaterialGrid, DesignRegion 정의"],
    ("inv_loop",      0): ["Cat.1 — resolution, cell_size, PML 정의",
                            "Cat.2 — geometry 구성",
                            "Cat.3 — MaterialGrid, DesignRegion 정의",
                            "Cat.4 — EigenModeSource, 모니터 정의"],
    ("inv_loop",      1): ["Cat.1 — resolution, cell_size, PML 정의",
                            "Cat.2 — geometry + 레이아웃 플롯",
                            "Cat.3 — MaterialGrid, DesignRegion 정의",
                            "Cat.4 — EigenModeSource, 모니터, OptimizationProblem 정의"],
    ("inv_loop",      2): ["Cat.1~4 완료",
                            "Stage 5-1 — Forward Sim 실행 (opt([x0]) 또는 sim.run() 완료)"],
    ("inv_loop",      3): ["Cat.1~4 완료",
                            "Stage 5-1 — Forward Sim 실행",
                            "Stage 5-2 — Adjoint Sim 실행 (grad 반환 확인)"],
    ("inv_loop",      4): ["Cat.1~4 완료",
                            "Stage 5-1~3 완료 (gradient 정상 수렴 확인)"],
    ("inv_loop",      5): ["Cat.1~4 완료",
                            "Stage 5-1~4 완료 (beta 충분히 증가된 상태)"],
    ("output",        0): ["Cat.1~4 완료",
                            "Stage 5-1~5 완료 (최적화 루프 종료)"],
}

# ── 다음 단계 미리보기 템플릿 ──────────────────────────────────────────────────
_NEXT_STEP_PREVIEW = {
    ("env_setup",     0): (
        "Category 2 — 지오메트리 구성",
        "환경 설정이 완료되었다면 이제 waveguide, photonic crystal rod 등 구조체를 "
        "mp.Block / mp.Cylinder로 정의할 차례입니다. "
        "geometry 리스트를 구성한 뒤 sim.init_sim() + sim.plot2D()로 레이아웃을 "
        "반드시 시각 확인하세요. 다음 질문은 '지오메트리 설정' 또는 'plot2D 사용법'으로 이어가세요."
    ),
    ("geometry",      0): (
        "Category 3 — 디자인 영역 설정",
        "구조체 레이아웃이 확인되었다면 최적화 가능한 영역을 설정할 차례입니다. "
        "mp.MaterialGrid(Nx, Ny, mp.air, silicon, grid_type='U_MEAN')로 설계 변수를 정의하고, "
        "mpa.DesignRegion으로 등록합니다. Nx = int(design_len * resolution)으로 해상도와 일치시키는 것이 핵심입니다. "
        "다음 질문은 'MaterialGrid 설정' 또는 'DesignRegion 정의'로 이어가세요."
    ),
    ("design_region", 0): (
        "Category 4 — 시뮬레이션 설정",
        "디자인 영역이 준비되었다면 이제 빛의 입력과 출력 측정을 설정할 차례입니다. "
        "mp.EigenModeSource로 원하는 모드를 주입하고 mpa.EigenmodeCoefficient로 "
        "출력 포트의 투과율을 측정합니다. eig_band는 반드시 1부터 시작해야 합니다(0 금지). "
        "다음 질문은 'EigenModeSource 설정' 또는 '모드 모니터 추가'로 이어가세요."
    ),
    ("sim_setup",     0): (
        "Category 5 — 역설계 루프",
        "소스와 모니터가 준비되었다면 mpa.OptimizationProblem을 생성하고 "
        "역설계 루프에 진입할 수 있습니다. "
        "objective_functions에 npa.abs(coeff)**2 형태의 함수를 등록하고, "
        "opt([x0]) 한 번 호출로 forward + adjoint가 동시에 실행됩니다. "
        "다음 질문은 'OptimizationProblem 설정' 또는 'forward simulation 실행'으로 이어가세요."
    ),
    ("inv_loop",      0): (
        "Stage 5-1 — Forward Simulation",
        "Cat.1~4가 모두 준비되었다면 이제 역설계 루프에 진입할 수 있습니다. "
        "mpa.OptimizationProblem을 생성하고 opt([x0])를 호출하면 "
        "forward + adjoint 시뮬레이션이 자동으로 순서대로 실행됩니다. "
        "첫 번째로 forward simulation 결과(FOM, DFT 필드)를 확인하며 시작하세요. "
        "다음 질문은 'forward simulation 실행' 또는 'OptimizationProblem 설정'으로 이어가세요."
    ),
    ("inv_loop",      1): (
        "Stage 5-2 — Adjoint Simulation",
        "Forward simulation 결과에서 원하는 포트로 필드가 전파되는 것이 확인되었다면 "
        "adjoint 단계로 넘어갈 수 있습니다. "
        "Adjoint는 각 출력 포트 위치에 mp.Source를 배치해 역방향으로 전파시키는 방식이며, "
        "opt([x0]) 호출 시 자동으로 실행됩니다. "
        "다음 질문은 '어드조인트 필드 플롯' 또는 'adjoint source 설정'으로 이어가세요."
    ),
    ("inv_loop",      2): (
        "Stage 5-3 — Gradient 계산",
        "Adjoint simulation이 완료되었다면 이제 gradient 맵을 확인할 차례입니다. "
        "opt([x0]) 반환값인 grad[0]를 Nx x Ny로 reshape하면 "
        "각 설계 변수의 민감도(sensitivity) 맵을 얻을 수 있습니다. "
        "빨간 영역은 Si를 추가하면 FOM이 개선되고, 파란 영역은 제거하면 개선됩니다. "
        "다음 질문은 'gradient 맵 플롯' 또는 'sensitivity 시각화'로 이어가세요."
    ),
    ("inv_loop",      3): (
        "Stage 5-4 — Beta Scheduling",
        "Gradient가 안정적으로 수렴하고 있다면 이진화를 위한 beta 증가를 시작할 수 있습니다. "
        "beta=2에서 시작해 10 iteration마다 2배씩 올려 128까지 점진적으로 증가시킵니다. "
        "너무 빠르게 올리면 FOM이 발산하므로 수렴 곡선을 보면서 조절하세요. "
        "다음 질문은 'beta 스케줄링' 또는 'tanh projection 설정'으로 이어가세요."
    ),
    ("inv_loop",      4): (
        "Stage 5-5 — Filter / Binarization",
        "Beta가 충분히 높아져 구조가 이진화에 가까워졌다면 "
        "제조 가능성 제약을 위한 conic filter를 적용할 수 있습니다. "
        "minimum feature size(예: 100nm)를 design grid 픽셀 수로 변환해 radius를 설정합니다. "
        "최종 binary ratio가 90% 이상이면 수렴 완료로 판단합니다. "
        "다음 질문은 'conic filter 설정' 또는 'minimum length scale'으로 이어가세요."
    ),
    ("inv_loop",      5): (
        "Category 6 — 결과물 출력",
        "최적화가 완료되었다면 수렴 플롯, 최종 구조, history.json을 저장할 차례입니다. "
        "모든 저장 코드는 mp.am_master() 블록 안에서 실행해야 MPI 환경에서 안전합니다. "
        "최종 검증은 최적화 resolution보다 2배 높은 resolution으로 재시뮬레이션하는 것을 권장합니다. "
        "다음 질문은 'convergence plot' 또는 'results 저장'으로 이어가세요."
    ),
    ("output",        0): (
        None,
        "최적화 및 결과물 저장이 완료되었습니다. "
        "필요하다면 더 높은 resolution으로 검증 시뮬레이션을 진행하거나, "
        "3D 시뮬레이션으로 z-leakage를 확인하는 것을 권장합니다."
    ),
}

# ── 카테고리/단계 표시 이름 ────────────────────────────────────────────────────
_CATEGORY_DISPLAY = {
    "env_setup":     "Category 1 — 시뮬레이션 환경 설정",
    "geometry":      "Category 2 — 지오메트리 구성",
    "design_region": "Category 3 — 디자인 영역 설정",
    "sim_setup":     "Category 4 — 시뮬레이션 설정",
    "inv_loop":      "Category 5 — 역설계 루프",
    "output":        "Category 6 — 결과물 출력",
}
_STAGE_DISPLAY = {
    1: "Stage 5-1 — Forward Simulation",
    2: "Stage 5-2 — Adjoint Simulation",
    3: "Stage 5-3 — Gradient 계산",
    4: "Stage 5-4 — Beta Scheduling",
    5: "Stage 5-5 — Filter / Binarization",
}


def _build_pipeline_header(intent: dict) -> str:
    """답변 상단: 파이프라인 위치 + 사전 확인사항 (pipeline_hit일 때만)"""
    if not intent.get("pipeline_hit"):
        return ""

    cat   = intent.get("pipeline_category")
    sidx  = intent.get("pipeline_stage_idx", 0)
    key   = (cat, sidx)

    cat_label   = _CATEGORY_DISPLAY.get(cat, cat or "")
    stage_label = _STAGE_DISPLAY.get(sidx, "") if sidx > 0 else ""

    # 위치 표시
    if stage_label:
        location = f"📍 [{cat_label} > {stage_label}]"
    else:
        location = f"📍 [{cat_label}]"

    prereqs = _PREREQUISITES.get(key, [])
    if not prereqs:
        return f"{location}\n\n"

    lines = [location, "", "⚠️ 사전 확인사항 (아래 항목이 완료되어야 이 단계가 의미 있습니다)"]
    for p in prereqs:
        lines.append(f"  - {p}")
    lines.append("")
    return "\n".join(lines) + "\n"


def _build_next_step_footer(intent: dict) -> str:
    """답변 하단: 다음 단계 미리보기 한 문단 (pipeline_hit일 때만)"""
    if not intent.get("pipeline_hit"):
        return ""

    cat  = intent.get("pipeline_category")
    sidx = intent.get("pipeline_stage_idx", 0)
    key  = (cat, sidx)

    preview = _NEXT_STEP_PREVIEW.get(key)
    if not preview:
        return ""

    next_label, next_text = preview
    if next_label:
        return f"\n---\n⏭️ **다음 단계 미리보기: {next_label}**\n\n{next_text}\n"
    else:
        return f"\n---\n✅ **{next_text}**\n"


def _build_citations(db_results: list) -> str:
    """하단 인용 섹션 생성"""
    if not db_results:
        return ""

    lines = ["---", "📚 **참조 자료**\n"]
    for i, r in enumerate(db_results[:6], 1):
        title = r.get("title", "(제목 없음)")
        url   = r.get("url", "")
        rtype = r.get("type", "")
        score = r.get("score", 0)

        if url:
            lines.append(f"[{i}] [{rtype}] [{title}]({url}) — 유사도 {score:.2f}")
        else:
            lines.append(f"[{i}] [{rtype}] {title} — 유사도 {score:.2f}")

    return "\n".join(lines)


def generate(query: str, intent: dict, db_results: list) -> dict:
    """
    Grounded RAG 방식으로 답변 생성.
    DB 결과에만 기반하며, 없는 내용은 "DB에 없음"으로 명시.
    pipeline_hit이면 상단 prerequisite + 하단 next step preview 추가.
    """
    context         = _build_context(db_results)
    citations       = _build_citations(db_results)
    pipeline_header = _build_pipeline_header(intent)
    pipeline_footer = _build_next_step_footer(intent)
    intent_type     = intent.get("intent", "unknown")
    has_db          = bool(db_results)

    # ── 의도별 모델 선택 ───────────────────────────────────────────────────
    model = INTENT_MODEL_MAP.get(intent_type, "claude-sonnet-4-5")

    # ── 파이프라인 컨텍스트 블록 (system prompt 보조) ─────────────────────
    pipeline_ctx = ""
    if intent.get("pipeline_hit"):
        cat   = intent.get("pipeline_category", "")
        sidx  = intent.get("pipeline_stage_idx", 0)
        clabel = _CATEGORY_DISPLAY.get(cat, cat)
        slabel = _STAGE_DISPLAY.get(sidx, "") if sidx > 0 else ""
        loc    = f"{clabel} > {slabel}" if slabel else clabel
        pipeline_ctx = f"\n[파이프라인 위치: {loc}]\n주의: 주의사항과 검증된 코드 제공이 메인. 파이프라인 컨텍스트는 보조 참고용.\n"

    # ── 의도별 시스템 프롬프트 ────────────────────────────────────────────
    if intent_type == "error_debug":
        system_prompt = f"""You are an expert MEEP debugger. Your job is to analyze errors and produce corrected, runnable code.
{pipeline_ctx}
[Answer Format — strictly follow]
## 1. 에러 분석
- 에러 원인을 정확히 짚어라 (1-3줄)
- DB의 관련 에러 사례 인용 ([자료 N])

## 2. 수정 방법
- 무엇을 어떻게 바꿔야 하는지 bullet로 명시

## 3. 수정된 코드
- 반드시 완전히 실행 가능한 코드를 ```python 블록으로 제공
- 수정된 줄에 # FIXED: 주석 추가
- 코드가 DB에 없으면 "(미검증 — 실행 확인 필요)" 표시

## 4. 추가 주의사항
- 같은 맥락에서 발생할 수 있는 다른 에러 예방법

[Rules]
- Reason in English internally, output in Korean
- Always produce corrected code — never just describe the fix
- Keep API names, variable names, error messages in English"""
    else:
        system_prompt = f"""You are an expert MEEP (MIT Electromagnetic Equation Propagation) simulation tutor.
You answer based on verified code patterns and DB references.
{pipeline_ctx}
[Answer Format — strictly follow]
1. 핵심 개념 설명 (2-3문장)
2. 단계별 구현 방법 (DB의 PATTERN/EXAMPLE 코드 우선)
3. 완전히 실행 가능한 코드 블록 (```python) — 주의사항 주석 포함
4. 흔한 실수 / 주의사항 (DB ERROR 자료 활용)
5. 참고 자료

[Rules]
- Reason in English internally, output final answer in Korean
- 주의사항과 검증된 코드가 메인 콘텐츠 (파이프라인 안내는 하단에 자동 추가됨)
- Use only verified code from DB; mark unverified as "(미검증 — 공식 문서 확인)"
- Cite as [자료 N]
- PATTERN entries take priority — show full code
- Be thorough enough that user can apply immediately"""

    # ── 피드백 few-shot 예시 조회 ──────────────────────────────────────────
    fewshot_examples = _get_feedback_examples(query, n=2)
    fewshot_block    = _build_fewshot_block(fewshot_examples)

    # ── 사용자 프롬프트 ────────────────────────────────────────────────────
    if intent_type == "error_debug":
        if has_db:
            user_prompt = f"""아래 DB에서 찾은 관련 에러 사례와 해결책을 참고해서 수정된 코드를 생성하세요.

=== DB 검색 결과 ===
{context}
====================
{fewshot_block + chr(10) if fewshot_block else ""}
에러/질문: {query}

중요:
- 에러 원인 분석 후 반드시 수정된 전체 코드를 제공하세요.
- 코드에 없는 부분은 플레이스홀더(# ... existing code ...)로 표시하세요.
- DB에 해결책 코드가 있으면 그것을 우선 사용하세요.
"""
        else:
            user_prompt = f"""MEEP DB에서 정확한 에러 사례를 찾지 못했습니다.
{fewshot_block + chr(10) if fewshot_block else ""}
에러/질문: {query}

DB에 없는 경우라도:
1. 에러 원인을 분석하고
2. 일반적인 MEEP 지식으로 수정된 코드를 제안하세요.
3. "(미검증 — 실행 확인 필요)" 를 코드 위에 명시하세요.
"""
    else:
        if has_db:
            user_prompt = f"""아래 MEEP DB 검색 결과를 참고해서 질문에 답하세요.

=== DB 검색 결과 ===
{context}
====================
{fewshot_block + chr(10) if fewshot_block else ""}
질문: {query}

- DB 자료 번호([자료 1], [자료 2] 등)를 인용하며 설명하세요.
- 코드 예제가 있으면 반드시 포함하세요.
- DB에 없는 내용은 "(DB에 없음)"으로 표시하세요.
{"- 이전 도움 사례를 참고해 더 실용적으로 답하세요." if fewshot_block else ""}
"""
        else:
            user_prompt = f"""MEEP DB에서 관련 자료를 찾지 못했습니다.
{fewshot_block + chr(10) if fewshot_block else ""}
질문: {query}

DB에 관련 정보가 없다는 것을 명확히 알리고,
일반적인 MEEP 지식으로 도움이 될 내용만 안내하세요.
불확실한 내용은 "(확인 필요)" 표시를 하세요.
"""

    # ── Claude API 호출 ────────────────────────────────────────────────────
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        msg = client.messages.create(
            model=model,
            max_tokens=2500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        answer_body = msg.content[0].text.strip()

    except Exception as e:
        answer_body = (
            f"❌ LLM 생성 실패: {e}\n\n"
            "DB 검색 결과를 직접 참고하세요."
        )

    # ── 최종 답변 조립 ────────────────────────────────────────────────────
    # 구조: [pipeline_header] + [answer_body] + [citations] + [pipeline_footer]
    parts = []
    if pipeline_header:
        parts.append(pipeline_header)
    parts.append(answer_body)
    if citations:
        parts.append(f"\n{citations}")
    if pipeline_footer:
        parts.append(pipeline_footer)

    answer = "\n".join(parts)

    hallucination_warning = not has_db  # DB 없을 때만 경고

    return {
        "answer": answer,
        "sources_used": len(db_results),
        "is_db_grounded": has_db,
        "hallucination_warning": hallucination_warning,
        "pipeline_category":  intent.get("pipeline_category"),
        "pipeline_stage":     intent.get("pipeline_stage"),
        "warning_message": (
            "DB 결과가 없어 일반 지식으로 답변했습니다. 공식 MEEP 문서에서 확인하세요."
            if hallucination_warning else None
        ),
    }


if __name__ == "__main__":
    test_results = [
        {
            "source": "vector", "type": "ERROR", "score": 0.82,
            "title": "adjoint simulation segfault",
            "cause": "MPI + adjoint 동시 사용 시 메모리 오류가 발생합니다.",
            "solution": "meep.Simulation 생성 전 mp.quiet(True)를 호출하세요.",
            "url": "https://github.com/NanoComp/meep/issues/123",
            "code": "mp.quiet(True)\nsim = mp.Simulation(...)"
        }
    ]
    result = generate(
        query="adjoint 돌리다가 죽었어",
        intent={"intent": "error_debug", "lang": "ko"},
        db_results=test_results
    )
    print(result["answer"])
