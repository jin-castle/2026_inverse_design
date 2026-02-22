#!/usr/bin/env python3
"""
MEEP-KB 통합 지능형 검색 에이전트 (Hybrid RAG)

사용자가 애매한 질문을 해도 의도를 파악하고 최적 검색 방식을 자동 선택합니다.
DB 결과가 충분하면 직출력, 부족하면 Claude Generation으로 전환.

사용법:
  python search_agent.py "EigenModeSource 쓸 때 뭔가 이상함"
  python search_agent.py "adjoint 돌리다가 죽었어"
  python search_agent.py "slabs 어떻게 설정해야 해?"
  python search_agent.py "my simulation blows up after a few steps"
  python search_agent.py "adjoint랑 MPI 관계가 뭐야"
  python search_agent.py "포토닉 크리스탈 예제"
  python search_agent.py "adjoint gradient" --n 5
  python search_agent.py "발산" --verbose
"""

import sys, argparse, time
from pathlib import Path

# 에이전트 모듈 경로 추가
BASE = Path(__file__).parent
sys.path.insert(0, str(BASE / "agent"))
sys.path.insert(0, str(BASE / "query"))

from intent_analyzer  import analyze
from search_router    import route
from search_executor  import execute
from coverage_checker import check_coverage
from generator        import generate

SOURCE_ICONS = {
    "keyword": "🔑",
    "vector":  "🔍",
    "graph":   "🕸️",
}
TYPE_ICONS = {
    "ERROR":   "🔴",
    "EXAMPLE": "🟢",
    "DOC":     "📄",
}

HALLUCINATION_BOX = """
╔══════════════════════════════════════════════════════════╗
║  ⚠️  AI 생성 답변 — 환각(Hallucination) 주의             ║
║  이 답변은 Claude AI가 생성했습니다.                     ║
║  DB에 없는 내용이 포함될 수 있으며 부정확할 수 있습니다. ║
║  중요한 내용은 공식 MEEP 문서 또는 GitHub Issues에서     ║
║  직접 확인하세요.                                        ║
║  📖 https://meep.readthedocs.io                         ║
╚══════════════════════════════════════════════════════════╝"""


def print_result(r: dict, rank: int):
    src   = SOURCE_ICONS.get(r["source"], "•")
    ticon = TYPE_ICONS.get(r["type"], "•")
    pct   = int(r["score"] * 100)
    bar   = "█" * (pct // 10) + "░" * (10 - pct // 10)
    warn  = " ⚠️" if r["score"] < 0.50 else ""

    print(f"\n{rank}. {ticon}[{r['type']}] {src}[{r['source']}]  {pct}%{warn}  {bar}")
    print(f"   {r['title']}")

    if r["type"] == "ERROR":
        if r.get("cause"):    print(f"   원인: {r['cause'][:150]}")
        if r.get("solution"): print(f"   ✅ 해결: {r['solution'][:200]}")
    elif r["type"] == "EXAMPLE":
        if r.get("code"):
            snippet = r["code"][:200].strip().replace("\n", "\n   ")
            print(f"   ```python\n   {snippet}\n   ```")
    elif r["type"] == "DOC":
        if r.get("cause"):    print(f"   {r['cause'][:180]}...")

    if r.get("url"): print(f"   🔗 {r['url']}")


def print_generation_result(gen: dict, db_results: list):
    """LLM 생성 결과 출력 (경고 포함)"""
    print(HALLUCINATION_BOX)
    print()
    print("🤖 [LLM 생성 답변]")
    print("─" * 60)
    print(gen["answer"])
    print("─" * 60)

    if db_results:
        print(f"\n📚 참고 DB 자료 ({gen['sources_used']}건):")
        for i, r in enumerate(db_results, 1):
            ticon = TYPE_ICONS.get(r["type"], "•")
            url_str = f"  🔗 {r['url']}" if r.get("url") else ""
            print(f"  {i}. {ticon} {r['title']}{url_str}")


def main():
    parser = argparse.ArgumentParser(
        description="MEEP-KB 통합 지능형 검색 에이전트 (Hybrid RAG)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python search_agent.py "EigenModeSource 쓸 때 뭔가 이상함"
  python search_agent.py "adjoint 돌리다가 죽었어"
  python search_agent.py "slabs 어떻게 설정해야 해?"
  python search_agent.py "my simulation blows up after a few steps"
  python search_agent.py "발산" --verbose
  python search_agent.py "adjoint gradient" --n 7
  python search_agent.py "adjoint가 뭐야" --no-llm
        """
    )
    parser.add_argument("query", help="자연어 검색어 (한국어/영어 모두 가능)")
    parser.add_argument("--n",       type=int, default=5, help="결과 수 (기본 5)")
    parser.add_argument("--verbose", action="store_true", help="의도 분석 + 라우팅 과정 출력")
    parser.add_argument("--no-llm",  action="store_true", help="LLM 없이 heuristic + DB 직출력만 사용")
    args = parser.parse_args()

    t_start = time.time()

    print(f"\n{'='*60}")
    print(f"🤖 MEEP-KB 검색 에이전트 (Hybrid RAG)")
    print(f"{'='*60}")
    print(f"📝 쿼리: \"{args.query}\"")

    # ── Stage 1: Intent Analysis ──────────────────────────────────────────────
    print("\n⏳ [1/4] 의도 분석 중...")
    intent = analyze(
        args.query,
        use_llm=not args.no_llm,
        verbose=args.verbose
    )

    intent_labels = {
        "error_debug":  "🔴 에러/오류 해결",
        "code_example": "🟢 코드 예제 탐색",
        "concept_map":  "🕸️  개념 관계 탐색",
        "doc_lookup":   "📄 문서 참조",
        "unknown":      "❓ 전방위 탐색",
    }
    label = intent_labels.get(intent["intent"], intent["intent"])
    print(f"   의도: {label}  |  언어: {intent['lang']}  |  신뢰도: {intent['confidence']:.0%}")
    if args.verbose:
        print(f"   이유: {intent.get('reason', '')}")
        print(f"   키워드: {intent.get('keywords', [])}")

    # ── Stage 2: Routing ─────────────────────────────────────────────────────
    plan = route(intent, n=args.n)
    method_str = " + ".join([f"{SOURCE_ICONS.get(m,'•')}{m}" for m in plan.methods])
    print(f"\n⏳ [2/4] 검색 방식 결정: {method_str}")
    if args.verbose:
        print(f"   이유: {plan.rationale}")
        print(f"   범위: {plan.db_types}")

    # ── Stage 3: Execute ─────────────────────────────────────────────────────
    print(f"\n⏳ [3/4] 검색 실행 중...")
    results = execute(plan, args.query, intent)

    # ── Stage 4: Coverage Check + Conditional Generation ─────────────────────
    coverage = check_coverage(intent, results)

    if args.verbose:
        print(f"\n   Coverage: sufficient={coverage['sufficient']}, "
              f"use_generation={coverage['use_generation']}")
        print(f"   이유: {coverage['reason']}")

    t_elapsed = time.time() - t_start

    # ── 결과 출력 ─────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")

    if coverage["use_generation"] and not args.no_llm:
        # LLM 생성 모드
        print(f"🤖 모드: LLM 생성 (Generation)  — {coverage['reason']}")
        print(f"{'='*60}")

        print("\n⏳ [4/4] Claude가 답변 생성 중...")
        gen = generate(args.query, intent, results)

        print(f"\n{'='*60}")
        print(f"📊 생성 완료  ({time.time() - t_start:.1f}초)")
        print(f"{'='*60}")

        print_generation_result(gen, results)

    else:
        # DB 직출력 모드
        mode_reason = "DB 직출력 (--no-llm)" if args.no_llm else f"DB 직출력 — {coverage['reason']}"
        print(f"🔍 모드: {mode_reason}")
        print(f"📊 결과: {len(results)}건  ({t_elapsed:.1f}초)")
        print(f"{'='*60}")

        if not results:
            print("\n❌ 결과 없음. 더 짧은 키워드로 다시 시도해보세요.")
            print("💡 예: python search_agent.py \"EigenModeSource\" --n 5")
            return

        for i, r in enumerate(results, 1):
            print_result(r, i)

        print(f"\n{'='*60}")
        print(f"검색 방식: {method_str}  |  소요시간: {t_elapsed:.1f}초")

        # 낮은 유사도 경고
        low_score_count = sum(1 for r in results if r["score"] < 0.50)
        if low_score_count > len(results) // 2:
            print(f"⚠️  결과 {low_score_count}건이 유사도 50% 미만입니다.")
            print("   더 구체적인 키워드나 영어 용어로 검색하면 품질이 올라갑니다.")

    print()


if __name__ == "__main__":
    main()
