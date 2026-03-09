"""
MEEP-KB 코드+에러 진단 엔진
============================
1단계: 에러 패턴 파싱 → DB 검색 (keyword + vector)
2단계: DB 매칭 충분하면 → DB 기반 수정 제안
3단계: DB 매칭 부족 시  → LLM 분석 (폴백)

DB FIRST 원칙: meep-kb 지식베이스를 최대한 활용
"""
import re, os, sqlite3
from pathlib import Path
from typing import Optional

BASE = Path(os.environ.get("APP_DIR", Path(__file__).parent.parent))
DB_PATH = BASE / "db/knowledge.db"

# ─── 에러 패턴 정규식 ─────────────────────────────────────────────────────────
ERROR_PATTERNS = [
    # Python 기본
    (r"AttributeError: '?(\w+)'? object has no attribute '(\w+)'",
     "AttributeError", "객체 속성 없음"),
    (r"TypeError: (.*)", "TypeError", "타입 오류"),
    (r"ValueError: (.*)", "ValueError", "값 오류"),
    (r"ImportError: No module named '([^']+)'",
     "ImportError", "모듈 없음"),
    (r"ModuleNotFoundError: No module named '([^']+)'",
     "ImportError", "모듈 없음"),
    (r"RuntimeError: (.*)", "RuntimeError", "런타임 오류"),
    (r"MemoryError", "MemoryError", "메모리 부족"),
    (r"KeyboardInterrupt", "KeyboardInterrupt", "사용자 중단"),
    # MEEP 특화
    (r"meep\.MeepError: (.*)", "MeepError", "MEEP 오류"),
    (r"changed_materials|reset_meep", "AdjointBug", "adjoint 재설정 버그"),
    (r"Simulation diverged|diverged", "Divergence", "시뮬레이션 발산"),
    (r"NaN|nan|inf|Inf", "NumericalError", "수치 불안정"),
    (r"MPIError|mpi4py|MPI", "MPIError", "MPI 병렬화 오류"),
    (r"EigenModeSource|eigenmode", "EigenMode", "고유모드 소스 오류"),
    (r"PML|perfectly matched layer", "PML", "PML 경계 오류"),
    (r"adjoint|OptimizationProblem", "Adjoint", "adjoint 최적화 오류"),
    (r"Harminv|harminv", "Harminv", "Harminv 오류"),
    (r"(out of memory|OOM|CUDA out)", "OOM", "메모리 부족"),
    (r"segmentation fault|Segmentation", "SegFault", "세그폴트"),
    (r"nlopt|NLopt", "NLopt", "NLopt 최적화 오류"),
]


def parse_error(code: str, error: str) -> dict:
    """에러 메시지에서 에러 타입 및 키워드 추출"""
    combined = error + " " + code
    detected = []

    for pattern, err_type, description in ERROR_PATTERNS:
        m = re.search(pattern, combined, re.IGNORECASE)
        if m:
            detected.append({
                "type":        err_type,
                "description": description,
                "matched":     m.group(0)[:100],
                "groups":      m.groups() if m.groups() else [],
            })

    # 에러 메시지에서 핵심 줄 추출 (Traceback 마지막 줄)
    error_lines = [l.strip() for l in error.split("\n") if l.strip()]
    last_error = ""
    for line in reversed(error_lines):
        if not line.startswith("File ") and not line.startswith("Traceback"):
            last_error = line
            break

    # 코드에서 MEEP 관련 키워드 추출
    meep_keywords = re.findall(
        r'\b(mp\.\w+|meep\.\w+|EigenModeSource|OptimizationProblem|'
        r'adjoint|ModeMonitor|FluxRegion|Simulation|PML|Vector3|'
        r'Harminv|add_flux|run_until|force_complex_fields)\b',
        code
    )

    return {
        "detected_types": detected,
        "primary_type":   detected[0]["type"] if detected else "Unknown",
        "last_error_line": last_error,
        "meep_keywords":   list(set(meep_keywords))[:10],
    }


def search_db(error_info: dict, code: str, error: str, n: int = 5) -> list:
    """SQLite DB에서 에러 패턴 검색 (FTS + LIKE 혼합)"""
    results = []
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.row_factory = sqlite3.Row

        # 검색 키워드 구성
        kws = set()
        for t in error_info["detected_types"]:
            kws.add(t["type"])
            kws.add(t["description"])
        kws.update(error_info["meep_keywords"][:5])
        if error_info["last_error_line"]:
            words = re.findall(r'\b[A-Za-z]\w+\b', error_info["last_error_line"])
            kws.update(words[:5])
        # 불필요한 단어 제거
        kws -= {"", "None", "True", "False", "the", "a", "an", "and", "or", "in", "is", "to"}

        # ── 1. errors FTS 검색 (빠른 전문 검색) ──────────────────────────────
        fts_kws = [kw for kw in kws if len(kw) > 3][:5]
        for kw in fts_kws:
            try:
                rows = conn.execute("""
                    SELECT e.id, e.error_msg, e.category, e.cause, e.solution,
                           e.source_url, 'error' as rtype
                    FROM errors_fts ft
                    JOIN errors e ON e.id = ft.rowid
                    WHERE errors_fts MATCH ?
                    LIMIT 4
                """, (kw,)).fetchall()
                for row in rows:
                    sol = (row["solution"] or "").strip()
                    if sol:  # solution 있는 것만
                        results.append({
                            "type":     "error",
                            "title":    row["error_msg"] or row["category"] or "MEEP 오류",
                            "cause":    row["cause"] or "",
                            "solution": sol,
                            "url":      row["source_url"] or "",
                            "score":    0.75,
                            "source":   "kb_fts",
                        })
            except Exception:
                pass

        # ── 2. errors LIKE 검색 (FTS가 못 잡는 케이스 보완) ─────────────────
        for kw in list(kws)[:6]:
            if len(kw) < 4:
                continue
            try:
                rows = conn.execute("""
                    SELECT error_msg, category, cause, solution, source_url
                    FROM errors
                    WHERE (cause LIKE ? OR solution LIKE ? OR error_msg LIKE ?)
                      AND solution IS NOT NULL AND solution != ''
                    LIMIT 3
                """, (f"%{kw}%", f"%{kw}%", f"%{kw}%")).fetchall()
                for row in rows:
                    results.append({
                        "type":     "error",
                        "title":    row["error_msg"] or row["category"] or "MEEP 오류",
                        "cause":    row["cause"] or "",
                        "solution": row["solution"] or "",
                        "url":      row["source_url"] or "",
                        "score":    0.65,
                        "source":   "kb_sqlite",
                    })
            except Exception:
                pass

        # ── 3. sim_errors 테이블 검색 (검증된 오류-해결쌍) ──────────────────
        try:
            primary_type = error_info.get("primary_type", "")
            if primary_type and primary_type != "Unknown":
                rows = conn.execute("""
                    SELECT error_type, error_message, fix_description, fixed_code,
                           fix_applied, root_cause, context, pattern_name, fix_worked,
                           source
                    FROM sim_errors
                    WHERE error_type = ? OR error_message LIKE ?
                    ORDER BY fix_worked DESC
                    LIMIT 4
                """, (primary_type, f"%{primary_type}%")).fetchall()
                for row in rows:
                    fix_worked = row["fix_worked"] or 0
                    verified_tag = "검증됨" if fix_worked else "참고용"
                    fix_text = row["fix_description"] or row["fix_applied"] or row["root_cause"] or ""
                    fix_code = row["fixed_code"] or ""
                    results.append({
                        "type":     "sim_error",
                        "title":    f"[{verified_tag}] {row['error_type']}: {(row['error_message'] or '')[:60]}",
                        "cause":    row["error_message"] or row["context"] or "",
                        "solution": fix_text[:400],
                        "code":     fix_code[:400],
                        "url":      "",
                        "score":    0.85 if fix_worked else 0.68,
                        "source":   "sim_errors",
                    })
        except Exception:
            pass

        # ── 4. examples 테이블 검색 (MEEP 함수 기반) ─────────────────────────
        for kw in error_info["meep_keywords"][:5]:
            try:
                rows = conn.execute("""
                    SELECT title, code, description, source_repo
                    FROM examples
                    WHERE code LIKE ? OR description LIKE ? OR title LIKE ?
                    LIMIT 2
                """, (f"%{kw}%", f"%{kw}%", f"%{kw}%")).fetchall()
                for row in rows:
                    results.append({
                        "type":        "example",
                        "title":       row["title"] or "MEEP 예제",
                        "code":        (row["code"] or "")[:400],
                        "description": row["description"] or "",
                        "url":         row["source_repo"] or "",
                        "score":       0.55,
                        "source":      "kb_sqlite",
                    })
            except Exception:
                pass

        conn.close()
    except Exception as e:
        pass

    # 중복 제거 + 점수 정렬
    seen = set()
    unique = []
    for r in results:
        key = r.get("title", "") + r.get("cause", "")[:50]
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:n]


def search_vector(query: str, n: int = 3, model=None, client=None) -> list:
    """ChromaDB 벡터 검색 (캐시에서 모델/클라이언트 주입)"""
    if not model or not client:
        return []
    try:
        embedding = model.encode([query])[0].tolist()
        collection = client.get_collection("meep_kb")
        res = collection.query(query_embeddings=[embedding], n_results=n)
        results = []
        if res and res["documents"]:
            for i, doc in enumerate(res["documents"][0]):
                meta = res["metadatas"][0][i] if res.get("metadatas") else {}
                dist = res["distances"][0][i] if res.get("distances") else 1.0
                score = max(0, 1.0 - dist)
                if score >= 0.25:
                    results.append({
                        "type":     meta.get("type", "unknown"),
                        "title":    meta.get("title", ""),
                        "cause":    meta.get("cause", ""),
                        "solution": doc[:500],
                        "url":      meta.get("url", ""),
                        "score":    round(score, 3),
                        "source":   "kb_vector",
                    })
        return results
    except Exception:
        return []


def extract_physics_context(code: str) -> dict:
    """MEEP 코드에서 물리적 파라미터 자동 추출"""
    ctx = {}

    # resolution
    m = re.search(r'resolution\s*=\s*([\d.]+)', code)
    if m: ctx["resolution"] = float(m.group(1))

    # cell size
    m = re.search(r'cell_size\s*=\s*mp\.Vector3\(([^)]+)\)', code)
    if m: ctx["cell_size"] = m.group(1).strip()

    # PML thickness
    m = re.search(r'PML\s*\(\s*([\d.]+)', code)
    if m: ctx["pml_thickness"] = float(m.group(1))

    # frequency / wavelength
    m = re.search(r'fcen\s*=\s*([\d.]+)', code)
    if m: ctx["fcen"] = float(m.group(1))
    m = re.search(r'wavelength\s*=\s*([\d.]+)', code)
    if m: ctx["wavelength"] = float(m.group(1))

    # dt / courant
    m = re.search(r'courant\s*=\s*([\d.]+)', code)
    if m: ctx["courant"] = float(m.group(1))

    # source bandwidth
    m = re.search(r'fwidth\s*=\s*([\d.eE+\-]+)', code)
    if m: ctx["fwidth"] = m.group(1)

    # geometry materials
    materials = re.findall(r'mp\.(Medium|silicon|SiO2|air|vacuum|glass)\b', code, re.IGNORECASE)
    if materials: ctx["materials"] = list(set(materials))

    # epsilon
    epsilons = re.findall(r'epsilon\s*=\s*([\d.]+)', code)
    if epsilons: ctx["epsilons"] = [float(e) for e in epsilons[:3]]

    # MPI / num_chunks
    if 'num_chunks' in code or 'split_chunks' in code:
        ctx["uses_mpi"] = True

    # adjoint
    if 'OptimizationProblem' in code or 'adjoint' in code.lower():
        ctx["uses_adjoint"] = True

    # symmetry
    if 'Symmetry' in code or 'Mirror' in code:
        ctx["uses_symmetry"] = True

    return ctx


def build_physics_diagnosis_prompt(code: str, error: str,
                                   error_info: dict, db_results: list,
                                   phys_ctx: dict) -> str:
    """MEEP 물리 도메인에 특화된 진단 프롬프트 생성"""

    # ── DB 지식 컨텍스트 ──────────────────────────────────────────────────────
    db_section = ""
    if db_results:
        db_section = "\n\n## meep-kb 지식베이스 관련 항목\n"
        for i, r in enumerate(db_results[:3]):
            db_section += f"\n### [{i+1}] {r.get('title','')}"
            if r.get("cause"):
                db_section += f"\n- **원인**: {r['cause'][:300]}"
            if r.get("solution"):
                db_section += f"\n- **해결책**: {r['solution'][:300]}"
            if r.get("code"):
                db_section += f"\n```python\n{r['code'][:400]}\n```"
        db_section += "\n\n**위 DB 지식을 최우선으로 활용하고, DB에 없는 경우만 추론하세요.**"

    # ── 물리 파라미터 컨텍스트 ───────────────────────────────────────────────
    phys_section = ""
    if phys_ctx:
        phys_section = "\n\n## 코드에서 추출된 물리 파라미터\n"
        if "resolution" in phys_ctx:
            res = phys_ctx["resolution"]
            # 수치 안정성 힌트
            courant = phys_ctx.get("courant", 0.5)
            phys_section += f"- resolution={res} (dt≈{courant/(res*2):.4f} MEEP units)\n"
        if "cell_size" in phys_ctx:
            phys_section += f"- cell_size: {phys_ctx['cell_size']}\n"
        if "pml_thickness" in phys_ctx:
            pml = phys_ctx["pml_thickness"]
            res = phys_ctx.get("resolution", 0)
            if res > 0:
                pml_cells = pml * res
                hint = "⚠️ PML 셀 수 부족 (<8)" if pml_cells < 8 else "✅ PML 충분"
                phys_section += f"- PML={pml} ({pml_cells:.0f}셀, {hint})\n"
        if "fcen" in phys_ctx:
            phys_section += f"- 중심주파수 fcen={phys_ctx['fcen']}\n"
        if "fwidth" in phys_ctx:
            phys_section += f"- 소스 대역폭 fwidth={phys_ctx['fwidth']}\n"
        if "epsilons" in phys_ctx:
            phys_section += f"- 유전율 ε={phys_ctx['epsilons']}\n"
        if phys_ctx.get("uses_adjoint"):
            phys_section += "- ⚡ Adjoint 최적화 사용\n"

    # ── 에러 타입별 물리 힌트 ────────────────────────────────────────────────
    err_hints = {
        "Divergence": """
**수치 발산 체크리스트:**
1. Courant 조건: dt < dx/(c√D) — resolution 낮으면 dt 자동 증가로 발산
2. PML이 너무 얇거나 (권장: 파장의 1~2배), 또는 소스가 PML 내부에 위치
3. 고유전율 재료(ε>20)에서 resolution 부족 시 발산
4. `force_complex_fields=True` 미설정 시 특정 모드에서 불안정
5. `decay_by` 조건 대신 고정 시간(`until`)으로 발산 전에 종료 고려""",

        "AdjointBug": """
**Adjoint 버그 체크리스트 (pmp130 환경 알려진 이슈):**
1. `optimization_problem.py` L552 `reset_meep()` 호출이 `changed_materials` 충돌 유발
2. 해결: L552를 주석 처리 (`# self.reset_meep()`)
3. 또는 MEEP 1.31.0+ 사용 (버그 수정됨)
4. `update_design()` 후 `prepare_forward_run()` 중복 호출 여부 확인""",

        "EigenMode": """
**EigenModeSource 체크리스트:**
1. `eig_parity`가 구조 대칭과 일치하는지 확인 (EVEN_Y+ODD_Z for TE, ODD_Y+EVEN_Z for TM)
2. `eig_kpoint` 방향이 전파 방향과 일치해야 함
3. 소스 크기(`size`)가 도파관보다 충분히 크게 (최소 셀 높이의 70% 이상)
4. `resolution`이 최소 파장/재료굴절률의 8배 이상 권장
5. 소스 위치가 균일한 재료 영역에 있어야 함 (경계면 근처 금지)""",

        "NumericalError": """
**수치 불안정 체크리스트:**
1. NaN: 보통 발산의 전조 — resolution 증가 또는 Courant 감소
2. Inf: PML 흡수 실패 — PML 두께 증가 또는 위치 조정
3. 복소 모드에서 실수 필드 사용 시 → `force_complex_fields=True`
4. 재료 분산(dispersive) 모델 파라미터 범위 초과 여부 확인""",

        "MPIError": """
**MPI 병렬화 체크리스트:**
1. `num_chunks` > 코어 수: 불균형 분할로 OOM 유발 가능
2. `mpi4py` 버전 MPICH/OpenMPI 버전 불일치
3. 큰 배열 gather 시 rank 0 메모리 부족 → `meep.Simulation.get_array()` 분산 처리
4. `mp.quiet(True)` 설정으로 출력 중복 방지""",
    }

    primary_type = error_info.get("primary_type", "")
    physics_hint = ""
    for err_type, hint in err_hints.items():
        if err_type.lower() in primary_type.lower():
            physics_hint = f"\n\n## 물리/수치 진단 가이드\n{hint}"
            break

    return f"""당신은 MEEP FDTD 시뮬레이션 + Photonics inverse design 전문가입니다.
일반적인 Python 디버거가 아닌, **MEEP API와 전자기 물리 법칙을 깊이 이해한** 관점으로 분석하세요.
{db_section}{phys_section}{physics_hint}

## 제출된 코드
```python
{code[:3000]}
```

## 에러 메시지
```
{error[:1500]}
```

## 요청 형식 (반드시 이 구조로 답하세요)

### 🔍 근본 원인
[MEEP/물리 관점에서 에러의 근본 원인을 1~3문장으로 설명. 
단순히 "속성이 없다"가 아니라 왜 그 API가 그렇게 동작하는지 설명]

### ⚡ 물리적 해석
[이 에러가 시뮬레이션 물리에 미치는 영향. 예: "PML이 얇으면 반사파가 생겨 결과가 부정확해짐"]

### 🔧 수정 코드
```python
# 변경된 부분만 표시. 주석으로 변경 이유 명시
# 이전: xxx
# 이후: yyy (이유: ...)
```

### ✅ 검증 방법
[수정 후 올바르게 동작하는지 확인하는 방법 1~2가지]

**DB 지식이 있으면 우선 활용하고, 없을 때만 물리적 추론으로 보완하세요.**"""


def llm_diagnose(code: str, error: str, db_results: list,
                 error_info: dict = None) -> dict:
    """MEEP 물리 도메인 특화 LLM 진단 (DB 결과 + 물리 컨텍스트 활용)"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"available": False, "reason": "ANTHROPIC_API_KEY 없음"}

    if error_info is None:
        error_info = {}

    # 물리 파라미터 추출
    phys_ctx = extract_physics_context(code)

    # 특화 프롬프트 생성
    prompt = build_physics_diagnosis_prompt(
        code, error, error_info, db_results, phys_ctx
    )

    try:
        import urllib.request, json
        body = json.dumps({
            "model": "claude-haiku-4-5",
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        )
        with urllib.request.urlopen(req, timeout=45) as r:
            data = json.loads(r.read())
            text = data["content"][0]["text"]
            return {
                "available": True,
                "answer": text,
                "physics_context": phys_ctx,
            }
    except Exception as e:
        return {"available": False, "reason": str(e)}


def diagnose(code: str, error: str, n: int = 5,
             model=None, client=None) -> dict:
    """
    메인 진단 함수
    Returns:
        {
          "error_info": {...},
          "db_results": [...],
          "db_sufficient": bool,
          "llm_result": {...} | None,
          "mode": "db_only" | "db+llm" | "llm_only",
          "suggestions": [...],  # 최종 수정 제안 목록
        }
    """
    # 1. 에러 파싱
    error_info = parse_error(code, error)

    # 2. DB 검색 (keyword)
    db_results = search_db(error_info, code, error, n=n)

    # 3. 벡터 검색 (ChromaDB, 가능한 경우)
    query = f"{error_info['primary_type']} {error_info['last_error_line']} {' '.join(error_info['meep_keywords'][:3])}"
    vec_results = search_vector(query.strip(), n=3, model=model, client=client)

    # 통합 + 중복 제거
    all_results = db_results + [r for r in vec_results
                                if r.get("title") not in {x.get("title") for x in db_results}]
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    all_results = all_results[:n]

    # 4. DB 충분성 판단
    top_score = all_results[0]["score"] if all_results else 0
    db_sufficient = top_score >= 0.55 and len(all_results) >= 1

    # 5. LLM 폴백 결정
    llm_result = None
    if not db_sufficient:
        llm_result = llm_diagnose(code, error, all_results, error_info=error_info)

    # 6. 최종 제안 목록 구성
    suggestions = []
    for r in all_results[:3]:
        s = {
            "source":  r.get("source", "kb"),
            "title":   r.get("title", ""),
            "score":   r.get("score", 0),
            "type":    r.get("type", ""),
        }
        if r.get("cause"):
            s["cause"]    = r["cause"]
        if r.get("solution"):
            s["solution"] = r["solution"]
        if r.get("code"):
            s["code"]     = r["code"]
        if r.get("url"):
            s["url"]      = r["url"]
        suggestions.append(s)

    mode = "db_only" if db_sufficient else ("db+llm" if llm_result and llm_result.get("available") else "db_only_low_confidence")

    return {
        "error_info":      error_info,
        "db_results":      all_results,
        "db_sufficient":   db_sufficient,
        "top_score":       round(top_score, 3),
        "llm_result":      llm_result,
        "mode":            mode,
        "suggestions":     suggestions,
        "physics_context": (llm_result or {}).get("physics_context", {}),
    }
