"""
/api/diagnose 품질 평가 스크립트
20개 eval case로 정확도, 커버리지, 응답 시간을 측정한다.
"""
import json
import time
import sqlite3
import urllib.request
import urllib.error
import sys
import os

API_URL = "http://localhost:8765/api/diagnose"
DB_PATH = "C:/Users/user/projects/meep-kb/db/knowledge.db"
REPORT_PATH = os.path.join(os.path.dirname(__file__), "eval_report.json")


# ─── 사전 정의 10개 케이스 ───────────────────────────────────────────────────
# (error_type, code_snippet, error_msg, expected_keywords_in_solution)
EVAL_CASES_PREDEFINED = [
    (
        "EigenMode",
        "src = mp.EigenmodeSource(..., eig_band=0)",
        "meep: EigenmodeSource: cannot find mode 0",
        ["eig_band", "1"],
    ),
    (
        "Divergence",
        "sim = mp.Simulation(resolution=2, boundary_layers=[mp.PML(0.1)])\nsim.run(until=500)",
        "Simulation diverged at t=42. Fields contain NaN",
        ["resolution", "PML"],
    ),
    (
        "MPIError",
        "import sys\ntry:\n    sim.run(until=100)\n    sys.exit(0)\nexcept:\n    sys.exit(1)",
        "MPIError: MPI_Barrier called after MPI_FINALIZE",
        ["sys.exit", "MPI", "rank"],
    ),
    (
        "PML",
        "flux = sim.add_flux(1.0, 0, 1, mp.FluxRegion(center=mp.Vector3(4.9)))\n# cell_x=10, pml=1.0",
        "T = 1.42 (>100%)",
        ["PML", "FluxRegion", "monitor"],
    ),
    (
        "Adjoint",
        "opt = mpa.OptimizationProblem(...)\nopt.forward_run()\nopt.adjoint_run()",
        "AttributeError: 'Simulation' object has no attribute 'reset_'",
        ["reset_meep", "adjoint", "changed_materials"],
    ),
    (
        "ImportError",
        "import meep.adjoint as mpa\nmat = mpa.MaterialGrid(...)",
        "AttributeError: module 'meep.adjoint' has no attribute 'MaterialGrid'",
        ["MaterialGrid", "mp.MaterialGrid", "1.28"],
    ),
    (
        "NumericalError",
        "sim = mp.Simulation(resolution=50)\nsim.run(mp.stop_when_fields_decayed(50, mp.Ez, pt, 1e-3))",
        "meep: harminv: Too many poles",
        ["harminv", "fwidth", "resolution"],
    ),
    (
        "General",
        "src = mp.EigenmodeSource(..., eig_parity=mp.ODD_Y+mp.EVEN_Z)",
        "T = 0.0 (no transmission)",
        ["eig_parity", "TE", "ODD_Z", "EVEN_Y"],
    ),
    (
        "MPI_deadlock",
        "while True:\n    sim.run(until=50)\n    data = sim.get_array(mp.Ez)",
        "Process hung indefinitely after 300s",
        ["while", "collective", "MPI", "barrier"],
    ),
    (
        "PML",
        "sim = mp.Simulation(cell_size=mp.Vector3(10,10), boundary_layers=[mp.PML(0.1)])\n# wavelength=1.55",
        "Reflection artifacts visible in field plot",
        ["PML", "wavelength", "thickness"],
    ),
]


def load_db_cases():
    """DB에서 추가 10개 케이스를 동적으로 로드한다."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    cases = []

    # sim_errors에서 에러 유형별 대표 케이스 추출
    target_types = [
        ("Divergence", ["resolution", "PML", "NaN"]),
        ("MPIError", ["MPI", "sys.exit", "rank"]),
        ("EigenMode", ["eig_band", "force_complex"]),
        ("Adjoint", ["reset_meep", "adjoint"]),
        ("ValueError", ["boundary", "cell"]),
        ("RuntimeError", ["meep", "simulation"]),
        ("AttributeError", ["meep", "version"]),
        ("ImportError", ["import", "module"]),
        ("PML", ["PML", "thickness", "wavelength"]),
        ("Harminv", ["harminv", "fwidth"]),
    ]

    for error_type, keywords in target_types:
        c.execute(
            """
            SELECT error_type, error_message, fix_description
            FROM sim_errors
            WHERE error_type = ?
              AND fix_worked = 1
              AND error_message IS NOT NULL
              AND error_message != ''
            ORDER BY id DESC
            LIMIT 1
        """,
            (error_type,),
        )
        row = c.fetchone()
        if row:
            etype, emsg, fix_desc = row
            # error_message를 짧게 자르기
            emsg_short = emsg[:200] if emsg else ""
            cases.append((etype, f"# {etype} 관련 코드", emsg_short, keywords))
        if len(cases) >= 10:
            break

    # 부족하면 Generic 케이스 추가
    while len(cases) < 10:
        cases.append((
            "General",
            "sim = mp.Simulation()\nsim.run(until=100)",
            "meep: simulation error",
            ["meep", "simulation"],
        ))

    conn.close()
    return cases


def call_diagnose(code: str, error: str) -> tuple[dict | None, float]:
    """API 호출, (response_dict, elapsed_ms) 반환"""
    payload = json.dumps({"code": code, "error": error, "n": 5}).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = (time.time() - t0) * 1000
            return data, elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.time() - t0) * 1000
        body = e.read().decode("utf-8")
        print(f"  [HTTP {e.code}] {body[:200]}", file=sys.stderr)
        return None, elapsed
    except Exception as ex:
        elapsed = (time.time() - t0) * 1000
        print(f"  [ERROR] {ex}", file=sys.stderr)
        return None, elapsed


def extract_metrics(resp: dict | None, expected_keywords: list[str]) -> dict:
    """응답에서 평가 지표 추출"""
    if resp is None:
        return {
            "top1_score": 0.0,
            "has_solution": False,
            "solution_covers_keyword": False,
            "db_sufficient": False,
            "mode": "error",
            "has_physics_cause": False,
            "has_root_cause_chain": False,
            "n_suggestions": 0,
        }

    suggestions = resp.get("suggestions", [])
    if not suggestions:
        return {
            "top1_score": 0.0,
            "has_solution": False,
            "solution_covers_keyword": False,
            "db_sufficient": False,
            "mode": "no_match",
            "has_physics_cause": False,
            "has_root_cause_chain": False,
            "n_suggestions": 0,
        }

    top1 = suggestions[0]
    score = float(top1.get("score", 0.0))

    # solution 필드: solution 또는 cause 또는 title
    solution_text = " ".join(filter(None, [
        top1.get("solution", ""),
        top1.get("cause", ""),
        top1.get("title", ""),
        top1.get("code", ""),
    ])).lower()

    # 전체 suggestions에서 keyword 검색
    all_text = " ".join([
        " ".join(filter(None, [
            s.get("solution", ""),
            s.get("cause", ""),
            s.get("title", ""),
        ])).lower()
        for s in suggestions
    ])

    has_solution = bool(top1.get("solution") or top1.get("cause"))
    covers_keyword = any(kw.lower() in all_text for kw in expected_keywords)

    # mode 판단 (source 기반)
    source = top1.get("source", "")
    if "sim_errors" in source or "live_run" in source or "verified_fix" in source:
        mode = "db_only"
        db_sufficient = True
    elif source in ("github", "errors", "pattern"):
        mode = "db_only"
        db_sufficient = True
    elif score >= 0.5:
        mode = "db_only_low_confidence"
        db_sufficient = False
    else:
        mode = "no_match"
        db_sufficient = False

    # v2 필드 체크 (모든 suggestions에서)
    has_physics_cause = any(s.get("physics_cause") for s in suggestions)
    has_root_cause_chain = any(s.get("root_cause_chain") for s in suggestions)

    return {
        "top1_score": round(score, 4),
        "has_solution": has_solution,
        "solution_covers_keyword": covers_keyword,
        "db_sufficient": db_sufficient,
        "mode": mode,
        "has_physics_cause": has_physics_cause,
        "has_root_cause_chain": has_root_cause_chain,
        "n_suggestions": len(suggestions),
    }


def get_db_coverage() -> dict:
    """sim_errors_v2 에러 유형별 fix_worked 커버리지"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # sim_errors 커버리지
    c.execute("""
        SELECT error_type,
               COUNT(*) as total,
               SUM(CASE WHEN fix_worked=1 THEN 1 ELSE 0 END) as fixed
        FROM sim_errors
        GROUP BY error_type
        ORDER BY total DESC
    """)
    sim_errors_cov = {}
    for row in c.fetchall():
        etype, total, fixed = row
        rate = f"{int(fixed/total*100)}%" if total > 0 else "0%"
        sim_errors_cov[etype or "Unknown"] = {"total": total, "fixed": fixed or 0, "rate": rate}

    # sim_errors_v2 커버리지
    c.execute("""
        SELECT error_type,
               COUNT(*) as total,
               SUM(CASE WHEN fix_worked=1 THEN 1 ELSE 0 END) as fixed
        FROM sim_errors_v2
        GROUP BY error_type
        ORDER BY total DESC
    """)
    sim_errors_v2_cov = {}
    for row in c.fetchall():
        etype, total, fixed = row
        rate = f"{int(fixed/total*100)}%" if total > 0 else "0%"
        sim_errors_v2_cov[etype or "Unknown"] = {"total": total, "fixed": fixed or 0, "rate": rate}

    conn.close()
    return {"sim_errors": sim_errors_cov, "sim_errors_v2": sim_errors_v2_cov}


def run_eval():
    print("=== /api/diagnose 품질 평가 시작 ===\n")

    # DB에서 추가 케이스 로드
    print("DB 기반 추가 케이스 로드 중...")
    db_cases = load_db_cases()
    all_cases = EVAL_CASES_PREDEFINED + db_cases
    print(f"총 케이스: {len(all_cases)}개\n")

    results = []
    for i, (error_type, code, error_msg, keywords) in enumerate(all_cases, 1):
        print(f"[{i:02d}/{len(all_cases)}] {error_type}: {error_msg[:60]}...")
        resp, elapsed = call_diagnose(code, error_msg)
        metrics = extract_metrics(resp, keywords)
        metrics["response_time_ms"] = round(elapsed, 1)

        result = {
            "case_id": i,
            "error_type": error_type,
            "error_msg": error_msg[:100],
            "expected_keywords": keywords,
            **metrics,
        }

        # 간단 상태 출력
        kw_status = "OK" if metrics["solution_covers_keyword"] else "NG"
        sol_status = "OK" if metrics["has_solution"] else "NG"
        print(f"     score={metrics['top1_score']:.2f} | sol={sol_status} | kw={kw_status} | mode={metrics['mode']} | {elapsed:.0f}ms")

        results.append(result)

    # ─── 리포트 계산 ──────────────────────────────────────────────────────────
    n = len(results)
    n_solution = sum(1 for r in results if r["has_solution"])
    n_keyword = sum(1 for r in results if r["solution_covers_keyword"])
    n_db_only = sum(1 for r in results if r["db_sufficient"])
    n_physics = sum(1 for r in results if r["has_physics_cause"])
    n_root_chain = sum(1 for r in results if r["has_root_cause_chain"])

    scores = [r["top1_score"] for r in results]
    avg_score = sum(scores) / n if n > 0 else 0.0
    n_high = sum(1 for s in scores if s >= 0.90)
    n_mid = sum(1 for s in scores if 0.65 <= s < 0.90)
    n_low = sum(1 for s in scores if s < 0.65)

    times = [r["response_time_ms"] for r in results]
    avg_time = sum(times) / n if n > 0 else 0.0
    max_time = max(times) if times else 0.0

    # 에러 유형별 keyword 매칭률
    by_type = {}
    for r in results:
        etype = r["error_type"]
        if etype not in by_type:
            by_type[etype] = {"total": 0, "keyword_match": 0}
        by_type[etype]["total"] += 1
        if r["solution_covers_keyword"]:
            by_type[etype]["keyword_match"] += 1

    type_coverage = {}
    for etype, stat in by_type.items():
        pct = int(stat["keyword_match"] / stat["total"] * 100) if stat["total"] > 0 else 0
        type_coverage[etype] = f"{pct}% ({stat['keyword_match']}/{stat['total']})"

    # 개선 필요 케이스 (score < 0.65 또는 keyword 미매칭)
    needs_improvement = [
        r for r in results
        if r["top1_score"] < 0.65 or not r["solution_covers_keyword"]
    ]

    # DB 커버리지
    db_coverage = get_db_coverage()

    # 종합 점수 계산 (100점 만점)
    # solution 포함률 30점 + keyword 매칭률 30점 + DB자충족률 20점 + 응답시간 20점
    score_solution = int(n_solution / n * 30)
    score_keyword = int(n_keyword / n * 30)
    score_db = int(n_db_only / n * 20)
    score_time = 20 if avg_time < 500 else (10 if avg_time < 1000 else 0)
    total_score = score_solution + score_keyword + score_db + score_time

    # ─── 리포트 출력 ──────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("=== /api/diagnose 품질 평가 리포트 ===")
    print(f"총 평가 케이스: {n}개")
    print()
    print("[정확도]")
    print(f"  solution 포함률:        {n_solution}/{n} ({int(n_solution/n*100)}%)")
    print(f"  keyword 매칭률:         {n_keyword}/{n} ({int(n_keyword/n*100)}%)")
    print(f"  DB 자충족률(db_only):   {n_db_only}/{n} ({int(n_db_only/n*100)}%)")
    print(f"  physics_cause 포함률:   {n_physics}/{n} ({int(n_physics/n*100)}%)")
    print(f"  root_cause_chain 포함률:{n_root_chain}/{n} ({int(n_root_chain/n*100)}%)")
    print()
    print("[점수 분포]")
    print(f"  top1_score 평균: {avg_score:.2f}")
    print(f"  top1_score ≥0.90: {n_high}건 ({int(n_high/n*100)}%) ← live_run/verified_fix")
    print(f"  top1_score ≥0.65: {n_mid}건 ({int(n_mid/n*100)}%) ← github")
    print(f"  top1_score <0.65: {n_low}건 ({int(n_low/n*100)}%) ← 미매칭")
    print()
    print("[응답 시간]")
    print(f"  평균: {avg_time:.0f}ms")
    print(f"  최대: {max_time:.0f}ms")
    print()
    print("[에러 유형별 커버리지]")
    for etype, cov in type_coverage.items():
        print(f"  {etype:20s}: {cov}")
    print()
    print("[개선 필요 케이스]")
    if needs_improvement:
        for r in needs_improvement[:10]:
            reasons = []
            if r["top1_score"] < 0.65:
                reasons.append("score 낮음")
            if not r["solution_covers_keyword"]:
                reasons.append("keyword 미매칭")
            print(f"  case {r['case_id']:02d} ({r['error_type']}): score={r['top1_score']:.2f}, {', '.join(reasons)}")
    else:
        print("  없음 (모두 통과)")
    print()
    print("[DB 커버리지 - sim_errors (총 고정 비율)]")
    for etype, stat in list(db_coverage["sim_errors"].items())[:10]:
        print(f"  {etype:20s}: total={stat['total']:3d}, fixed={stat['fixed']:3d}, rate={stat['rate']}")
    print()
    print("[DB 커버리지 - sim_errors_v2 (physics_cause 포함)]")
    for etype, stat in db_coverage["sim_errors_v2"].items():
        print(f"  {etype:20s}: total={stat['total']:3d}, fixed={stat['fixed']:3d}, rate={stat['rate']}")
    print()
    print(f"=== 종합 점수: {total_score}/100 ===")
    print(f"    (solution:{score_solution}/30 + keyword:{score_keyword}/30 + db:{score_db}/20 + time:{score_time}/20)")
    print("=" * 50)

    # ─── JSON 저장 ────────────────────────────────────────────────────────────
    report = {
        "eval_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_cases": n,
        "accuracy": {
            "n_solution": n_solution,
            "n_keyword": n_keyword,
            "n_db_only": n_db_only,
            "n_physics_cause": n_physics,
            "n_root_cause_chain": n_root_chain,
            "solution_rate": round(n_solution / n, 3),
            "keyword_rate": round(n_keyword / n, 3),
            "db_sufficient_rate": round(n_db_only / n, 3),
            "physics_cause_rate": round(n_physics / n, 3),
        },
        "score_distribution": {
            "avg": round(avg_score, 4),
            "n_high_ge_0_90": n_high,
            "n_mid_ge_0_65": n_mid,
            "n_low_lt_0_65": n_low,
        },
        "response_time": {
            "avg_ms": round(avg_time, 1),
            "max_ms": round(max_time, 1),
        },
        "type_coverage": type_coverage,
        "needs_improvement": [
            {"case_id": r["case_id"], "error_type": r["error_type"],
             "top1_score": r["top1_score"], "has_solution": r["has_solution"],
             "solution_covers_keyword": r["solution_covers_keyword"]}
            for r in needs_improvement
        ],
        "db_coverage": db_coverage,
        "total_score": total_score,
        "score_breakdown": {
            "solution": score_solution,
            "keyword": score_keyword,
            "db_sufficient": score_db,
            "response_time": score_time,
        },
        "cases": results,
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n리포트 저장: {REPORT_PATH}")

    return report


if __name__ == "__main__":
    run_eval()
