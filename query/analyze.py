#!/usr/bin/env python3
"""MEEP-KB 전체 분석 및 보고서 생성"""

import sqlite3, re
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

DB      = Path(__file__).parent.parent / "db" / "knowledge.db"
OUT_DIR = Path(__file__).parent.parent / "reports"
OUT_DIR.mkdir(exist_ok=True)

conn = sqlite3.connect(DB, timeout=30)

# ── 기본 통계 ──────────────────────────────────────────────────
n_err   = conn.execute("SELECT COUNT(*) FROM errors").fetchone()[0]
n_ex    = conn.execute("SELECT COUNT(*) FROM examples").fetchone()[0]
n_docs  = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
n_solved= conn.execute(
    "SELECT COUNT(*) FROM errors WHERE solution != '' AND solution IS NOT NULL"
).fetchone()[0]

cats = conn.execute(
    "SELECT category, COUNT(*) FROM errors GROUP BY category ORDER BY 2 DESC"
).fetchall()

srcs = conn.execute(
    "SELECT source_type, COUNT(*) FROM errors GROUP BY source_type ORDER BY 2 DESC"
).fetchall()

# ── 키워드 빈도 분석 ───────────────────────────────────────────
rows = conn.execute(
    "SELECT error_msg FROM errors WHERE source_type='github_issue'"
).fetchall()

kw_cnt = Counter()
for (msg,) in rows:
    words = re.findall(r"[A-Z][a-zA-Z_]{3,25}Error|[A-Z][a-zA-Z_]{3,25}Exception", msg)
    kw_cnt.update(words)

# ── 카테고리별 대표 에러 샘플 ──────────────────────────────────
cat_samples = {}
for (cat,) in conn.execute("SELECT DISTINCT category FROM errors ORDER BY 1").fetchall():
    rows_c = conn.execute(
        "SELECT error_msg, solution FROM errors WHERE category=? ORDER BY verified DESC LIMIT 5", (cat,)
    ).fetchall()
    cat_samples[cat or "general"] = rows_c

# ── 해결책 있는 에러 Top 20 ────────────────────────────────────
solved_top = conn.execute("""
    SELECT error_msg, category, solution, source_url
    FROM errors
    WHERE solution != '' AND solution IS NOT NULL
    ORDER BY verified DESC, id DESC
    LIMIT 30
""").fetchall()

# ── 문서 시뮬레이터별 ─────────────────────────────────────────
doc_sims = conn.execute(
    "SELECT simulator, COUNT(*) FROM docs GROUP BY simulator ORDER BY 2 DESC"
).fetchall()

conn.close()

# ── 보고서 작성 ───────────────────────────────────────────────
now = datetime.now().strftime("%Y-%m-%d %H:%M")
report = f"""\
# MEEP-KB 분석 보고서

**생성일시:** {now}  
**DB:** `db/knowledge.db`

---

## 1. 전체 현황

| 테이블 | 건수 | 비고 |
|--------|------|------|
| **errors** | {n_err}건 | 해결책 보유: {n_solved}건 ({n_solved*100//max(n_err,1)}%) |
| **docs** | {n_docs}건 | 공식 문서 + GitHub 이슈 Q&A |
| **examples** | {n_ex}건 | 연구자 코드 예제 |

---

## 2. 에러 카테고리 분포

| 카테고리 | 건수 | 비율 | 설명 |
|---------|------|------|------|
"""

CAT_DESC = {
    "install":    "패키지 설치/빌드 오류",
    "cfwdm":      "Jin의 CFWDM 실험 로그",
    "convergence":"수렴/발산/NaN 오류",
    "general":    "일반 에러",
    "geometry":   "구조/형상 정의 오류",
    "monitor":    "Flux/Field 모니터 오류",
    "source":     "Source 정의 오류",
    "mpi":        "MPI 병렬 오류",
    "adjoint":    "Adjoint 최적화 오류",
    "runtime":    "런타임 충돌/메모리",
    "legume":     "legume GME 오류",
    "mpb":        "MPB 밴드 계산 오류",
}

for cat, n in cats:
    pct  = n * 100 // max(n_err, 1)
    bar  = "█" * (pct // 5) + "░" * (20 - pct // 5)
    desc = CAT_DESC.get(cat or "general", "")
    report += f"| `{cat or '?':<13}` | {n:>4}건 | {pct:>3}% `{bar}` | {desc} |\n"

report += f"""
---

## 3. 데이터 소스별

| 소스 | 건수 |
|------|------|
"""
for src, n in srcs:
    report += f"| `{src or '?'}` | {n}건 |\n"

report += f"""
---

## 4. 자주 등장하는 에러 타입 Top 15

(GitHub 이슈에서 추출한 Python Exception 클래스명 기준)

| 순위 | 에러 타입 | 등장 횟수 |
|------|----------|----------|
"""
for i, (kw, cnt) in enumerate(kw_cnt.most_common(15), 1):
    report += f"| {i:>2} | `{kw}` | {cnt}회 |\n"

report += """
---

## 5. 카테고리별 대표 에러 & 해결책

"""

for cat, samples in cat_samples.items():
    report += f"### {cat.upper()}\n\n"
    for msg, sol in samples:
        report += f"**에러:** `{msg[:100]}`  \n"
        if sol:
            report += f"**해결:** {sol[:200]}  \n"
        report += "\n"

report += """---

## 6. 문서 수집 현황

| 시뮬레이터 | 문서 청크 수 |
|-----------|------------|
"""
for sim, n in doc_sims:
    report += f"| `{sim or '?'}` | {n}건 |\n"

report += f"""
---

## 7. 에러 해결 가이드 (즉시 활용 가능 Top 10)

"""
for i, (msg, cat, sol, url) in enumerate(solved_top[:10], 1):
    report += f"### {i}. `{msg[:80]}`\n"
    report += f"- **카테고리:** `{cat}`\n"
    report += f"- **해결책:** {sol[:300]}\n"
    if url:
        report += f"- **참고:** {url}\n"
    report += "\n"

report += """---

## 8. 검색 사용법

```bash
cd C:\\Users\\user\\projects\\meep-kb

# 에러 메시지로 검색
python query/search.py "Courant factor"
python query/search.py "EigenModeSource" --type errors
python query/search.py "adjoint gradient" --type examples

# 전체 통계
python query/search.py --stats
```

---

## 9. 향후 개선 사항

- [ ] GitHub 이슈 수집 완료 (현재 진행 중, ~3,000건 목표)
- [ ] 연구자 코드 수집 (Step 3) — zlin-opt, stanfordnqp, fancompute 등
- [ ] 이슈 댓글 수집으로 해결책 품질 향상
- [ ] 벡터 DB (ChromaDB/Faiss) 연동으로 의미론적 검색 추가
- [ ] `.claude/skills/meep-simulation/` 자동 업데이트 스케줄링

---

_포비 자동 생성 — MEEP-KB v0.1_
"""

out_path = OUT_DIR / "meep_kb_report.md"
out_path.write_text(report, encoding="utf-8")
print(report)
print(f"\n✅ 보고서 저장: {out_path}")
