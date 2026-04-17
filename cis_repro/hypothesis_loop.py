"""
Hypothesis Loop — 자동 파라미터 탐색
=====================================
새 논문이 들어오면:
1. FL/design_type 등 메타데이터로 후보 설정 생성 (≤20개)
2. res=20으로 색분리 방향 빠른 체크
3. 생존한 상위 후보만 res=50 실행
4. 오차 ≤5% 달성 시 → error_patterns DB 업데이트

사용법:
    python hypothesis_loop.py --params results/NewPaper/params.json
    python hypothesis_loop.py --params results/NewPaper/params.json --target-err 10
"""
import sys, re, json, time, subprocess, argparse, itertools
from pathlib import Path
from datetime import datetime

BASE    = Path(__file__).parent
DB_PATH = BASE.parent / "db" / "knowledge.db"
DOCKER  = "meep-pilot-worker"
sys.path.insert(0, str(BASE))

from corrected_codegen import build_corrected_code, fast_check_docker
from detector import classify_all, auto_fix_loop

ERROR_PATTERNS = json.loads((BASE / "error_patterns.json").read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════
# 1. 메타데이터 기반 후보 생성
# ══════════════════════════════════════════════════════════════

def generate_candidates(params: dict) -> list[dict]:
    """
    FL, design_type, n_material 등에서 유력한 설정 조합 생성
    총 후보: 8~20개 (전체 64개 중 필터링)

    [2026-04-10] 추가 변수:
    - bayer_config: Bayer 4분면 R 위치 (논문마다 다름)
    - n_material_offset: 굴절률 미세 조정
    """
    FL = params.get("FL_thickness", 2.0)
    dt = params.get("design_type", "discrete_pillar")

    # --- stop_decay 후보: FL 길이 기준 ---
    if FL >= 3.5:
        decays = ["1e-8"]
    elif FL >= 2.0:
        decays = ["1e-8", "1e-6"]
    else:
        decays = ["1e-6", "1e-4"]

    # --- cover_glass ---
    covers = [True, False] if dt == "sparse" else [True]

    # --- SiPD material ---
    sipd_opts = ["SiO2", "Air"] if dt == "sparse" else ["Air"]

    # --- source_count ---
    src_counts = [2]

    # --- [신규] bayer_config: R 픽셀 위치 ---
    # "standard": R(-x,-y) Gr(-x,+y) B(+x,+y) Gb(+x,-y)  ← Single2022 등
    # "sma":      R(-x,+y) Gr(-x,-y) B(+x,-y) Gb(+x,+y)  ← SMA 원본
    # 기존 error_patterns에 있으면 그것 우선
    pid = params.get("paper_id", "")
    existing_bayer = ERROR_PATTERNS.get("paper_specific", {}).get(pid, {}) \
                                    .get("overrides", {}).get("bayer_config")
    if existing_bayer:
        bayer_configs = [existing_bayer]
    elif dt == "sparse":
        bayer_configs = ["standard", "sma"]  # sparse는 두 배치 모두 시도
    else:
        bayer_configs = ["standard"]

    candidates = []
    for decay, cover, sipd, src, bayer in itertools.product(
            decays, covers, sipd_opts, src_counts, bayer_configs):
        ref_opts = ["with_cover", "air"] if cover else ["air"]
        for ref in ref_opts:
            candidates.append({
                "stop_decay":    decay,
                "cover_glass":   cover,
                "ref_sim_type":  ref,
                "source_count":  src,
                "sipd_material": sipd,
                "bayer_config":  bayer,
            })

    # 중복 제거
    seen = set()
    unique = []
    for c in candidates:
        key = tuple(sorted(c.items()))
        if key not in seen:
            seen.add(key)
            unique.append(c)

    # error_patterns에 기존 성공 케이스 있으면 맨 앞에 추가
    pid = params.get("paper_id", "")
    existing = ERROR_PATTERNS.get("paper_specific", {}).get(pid, {}).get("overrides")
    if existing:
        print(f"  [HypLoop] '{pid}' 기존 설정 발견 → 우선 시도")
        unique.insert(0, {
            "stop_decay":    existing.get("stop_decay", "1e-6"),
            "cover_glass":   existing.get("cover_glass", True),
            "ref_sim_type":  existing.get("ref_sim_type", "air"),
            "source_count":  existing.get("source_count", 2),
            "sipd_material": existing.get("sipd_material", "Air"),
            "_source": "existing_pattern",
        })

    return unique


# ══════════════════════════════════════════════════════════════
# 2. 코드 생성 + Docker 실행
# ══════════════════════════════════════════════════════════════

def run_candidate(params: dict, candidate: dict, res: int,
                  cid: int, out_dir: Path, timeout=600) -> dict | None:
    """후보 설정으로 MEEP 실행 → 효율 반환"""
    # params에 override 주입
    p = {**params, **candidate}
    pid = params["paper_id"]

    # 코드 생성
    code = build_corrected_code(p, pid)

    # detector 사전 검사
    issues = classify_all(code, "", {})
    if issues:
        code, _ = auto_fix_loop(code)

    # resolution 교체
    code = re.sub(r'\bresolution\s*=\s*\d+', f"resolution = {res}", code, count=1)

    # 파일 저장
    suffix = f"_c{cid:02d}_res{res}"
    script = out_dir / f"hyp{suffix}.py"
    script.write_text(code, encoding="utf-8")

    # Docker 실행
    remote = f"/tmp/hyp_{pid}{suffix}.py"
    rlog   = f"/tmp/hyp_{pid}{suffix}.log"
    subprocess.run(["docker","cp",str(script),f"{DOCKER}:{remote}"], capture_output=True)

    r = subprocess.run(
        ["docker","exec",DOCKER,"bash","-c",
         f"mpirun -np 4 --allow-run-as-root python {remote} > {rlog} 2>&1"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout
    )

    # 결과 파일 수집
    subprocess.run(
        ["docker","exec",DOCKER,"bash","-c", f"cat {rlog}"],
        stdout=open(out_dir / f"hyp{suffix}.log", "w", encoding="utf-8"),
        stderr=subprocess.DEVNULL
    )

    log = (out_dir / f"hyp{suffix}.log").read_text(encoding="utf-8", errors="replace")
    m = re.search(r'\[Result\] R=([\d.]+) G=([\d.]+) B=([\d.]+)', log)
    e = re.findall(r'Elapsed run time = ([\d.]+)', log)

    if m:
        return {
            "R": float(m.group(1)),
            "G": float(m.group(2)),
            "B": float(m.group(3)),
            "elapsed": float(e[0]) if e else None,
        }
    return None


def calc_error(eff: dict, target: dict) -> float:
    """논문 target과의 평균 오차 (%)"""
    if not eff or not target:
        return 999.0
    errs = [abs(eff[ch]-target[ch])/target[ch]*100
            for ch in ["R","G","B"] if ch in target and ch in eff]
    return round(sum(errs)/len(errs), 1) if errs else 999.0


def color_direction_ok(eff: dict, min_each=0.10) -> bool:
    """모든 채널이 최소값 이상 & 색분리가 있는가"""
    if not eff: return False
    vals = [eff.get("R",0), eff.get("G",0), eff.get("B",0)]
    if any(v < min_each for v in vals): return False
    # 색분리: 최대-최소 > 0.05
    return max(vals) - min(vals) > 0.05


# ══════════════════════════════════════════════════════════════
# 3. Hypothesis Loop 메인
# ══════════════════════════════════════════════════════════════

def run_hypothesis_loop(params: dict, target_err: float = 5.0,
                        max_candidates: int = 20) -> dict | None:
    pid     = params["paper_id"]
    target  = params.get("target_efficiency", {})
    out_dir = BASE / "results" / pid / "hyp"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*65}")
    print(f"Hypothesis Loop: {pid}")
    print(f"  target_err ≤ {target_err}%  |  max_candidates = {max_candidates}")
    print(f"  target: {target}")
    print(f"{'='*65}")

    t_start = time.time()

    # 1. 후보 생성
    candidates = generate_candidates(params)[:max_candidates]
    print(f"\n[Phase 1] {len(candidates)}개 후보 생성")
    for i, c in enumerate(candidates):
        src = c.pop("_source", "generated")
        print(f"  C{i:02d}: decay={c['stop_decay']} cover={c['cover_glass']} "
              f"ref={c['ref_sim_type']} sipd={c['sipd_material']}  ({src})")

    # 2. res=20 빠른 검증
    print(f"\n[Phase 2] res=20 빠른 검증 ({len(candidates)}개 순차 실행)")
    survivors = []

    for i, cand in enumerate(candidates):
        print(f"  C{i:02d} 실행... ", end="", flush=True)
        eff = run_candidate(params, cand, res=20, cid=i, out_dir=out_dir,
                            timeout=600)
        if eff:
            ok = color_direction_ok(eff)
            err = calc_error(eff, target)
            score = eff["R"] + eff["G"] + eff["B"]
            status = "[OK]" if ok else "[NG]"
            print(f"R={eff['R']:.3f} G={eff['G']:.3f} B={eff['B']:.3f}  err={err:.1f}%  {status}")
            if ok:
                survivors.append({
                    "candidate": cand, "eff20": eff,
                    "err20": err, "score": score
                })
        else:
            print("[실행실패]")

        # 오차 5% 이내면 이미 성공 (res=20으로도)
        if eff and calc_error(eff, target) <= target_err:
            print(f"\n  [조기 완료] C{i:02d}에서 오차 {calc_error(eff,target)}% 달성!")
            survivors = [{"candidate": cand, "eff20": eff,
                          "err20": calc_error(eff, target), "score": score}]
            break

    if not survivors:
        print("\n  [실패] 색분리 방향을 만족하는 후보 없음 → 수동 확인 필요")
        return None

    # 상위 정렬
    survivors.sort(key=lambda x: (x["err20"], -x["score"]))
    print(f"\n  생존 후보: {len(survivors)}개 (상위 3개 → res=50)")

    # 3. 상위 3개 res=50 최종 실행
    print(f"\n[Phase 3] res=50 최종 실행 (상위 {min(3,len(survivors))}개)")
    best_result = None

    for rank, surv in enumerate(survivors[:3]):
        cand = surv["candidate"]
        print(f"\n  [rank {rank+1}] decay={cand['stop_decay']} cover={cand['cover_glass']} "
              f"ref={cand['ref_sim_type']}")
        print(f"    res=20: R={surv['eff20']['R']:.3f} G={surv['eff20']['G']:.3f} "
              f"B={surv['eff20']['B']:.3f}  err={surv['err20']:.1f}%")

        final_res = params.get("resolution", 50)
        print(f"    res={final_res} 실행 중...", end="", flush=True)
        eff50 = run_candidate(params, cand, res=final_res,
                              cid=100+rank, out_dir=out_dir, timeout=10800)

        if eff50:
            err50 = calc_error(eff50, target)
            print(f"\n    R={eff50['R']:.3f} G={eff50['G']:.3f} B={eff50['B']:.3f}  err={err50:.1f}%")

            result = {
                "paper_id": pid,
                "candidate": cand,
                "eff20": surv["eff20"], "err20": surv["err20"],
                "eff_final": eff50, "err_final": err50,
                "final_res": final_res,
                "elapsed_total": round(time.time() - t_start, 1),
                "target_met": err50 <= target_err,
            }

            if err50 <= target_err:
                print(f"\n  [SUCCESS] 오차 {err50}% ≤ {target_err}% 달성!")
                best_result = result
                break
            elif best_result is None or err50 < best_result["err_final"]:
                best_result = result
        else:
            print(" [실패]")

    # 4. 결과 저장 + error_patterns 업데이트
    if best_result:
        _save_result(best_result, params, out_dir)
        _update_error_patterns(best_result, params)

    return best_result


def _save_result(result: dict, params: dict, out_dir: Path):
    """결과 JSON + 요약 출력"""
    pid = params["paper_id"]
    out_path = BASE / "results" / pid / f"{pid}_hyp_result.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'='*65}")
    print(f"최종 결과: {pid}")
    eff = result["eff_final"]
    print(f"  R={eff['R']:.3f}  G={eff['G']:.3f}  B={eff['B']:.3f}")
    print(f"  오차: {result['err_final']:.1f}%  ({'SUCCESS ✓' if result['target_met'] else 'PARTIAL'})")
    print(f"  소요: {result['elapsed_total']}초")
    print(f"  최적 설정: {result['candidate']}")
    print(f"  저장: {out_path}")
    print(f"{'='*65}")


def _update_error_patterns(result: dict, params: dict):
    """성공/실패 설정을 error_patterns.json에 저장 → 다음 논문에 활용"""
    ep  = json.loads((BASE / "error_patterns.json").read_text(encoding="utf-8"))
    pid = params["paper_id"]
    FL  = params.get("FL_thickness", 2.0)
    dt  = params.get("design_type", "discrete_pillar")
    cand = result["candidate"]
    err  = result["err_final"]

    # 논문별 설정 저장
    ep["paper_specific"][pid] = {
        "paper_title": params.get("paper_title", pid),
        "auto_discovered": True,
        "discovery_date": datetime.now().isoformat(),
        "final_error_pct": err,
        "confirmed_errors": [],
        "overrides": cand,
    }

    # 글로벌 규칙 강화
    # FL ≥ 3.5μm → stop_decay 1e-8이 성공했으면 규칙 업데이트
    if FL >= 3.5 and cand.get("stop_decay") == "1e-8":
        for rule in ep["global_rules"]:
            if rule["id"] == "GP-001":
                rule["verified_cases"].append(f"{pid}: FL={FL}μm → 1e-8 성공")

    (BASE / "error_patterns.json").write_text(
        json.dumps(ep, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [학습] error_patterns.json 업데이트 완료 ({pid})")

    # meep-kb DB에도 저장
    try:
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        cur  = conn.cursor()
        now  = datetime.now().isoformat()
        doc  = json.dumps(ep["paper_specific"][pid], ensure_ascii=False)
        cur.execute("SELECT id FROM docs WHERE url=?", (f"hyp_{pid}",))
        if cur.fetchone():
            cur.execute("UPDATE docs SET content=? WHERE url=?", (doc, f"hyp_{pid}"))
        else:
            cur.execute("INSERT INTO docs (section,content,url,simulator) VALUES (?,?,?,?)",
                        (f"HypLoop Result: {pid}", doc, f"hyp_{pid}", "meep"))
        conn.commit(); conn.close()
        print(f"  [KB] meep-kb DB 업데이트 완료")
    except Exception as e:
        print(f"  [KB] 저장 실패(무시): {e}")


# ══════════════════════════════════════════════════════════════
# 4. CLI
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Hypothesis Loop — 자동 파라미터 탐색")
    ap.add_argument("--params",      required=True, help="params.json 경로")
    ap.add_argument("--target-err",  type=float, default=5.0, help="목표 오차 (%) [default:5]")
    ap.add_argument("--max-cand",    type=int, default=20, help="최대 후보 수 [default:20]")
    ap.add_argument("--dry-run",     action="store_true", help="후보만 출력, 실행 없음")
    args = ap.parse_args()

    params = json.loads(Path(args.params).read_text(encoding="utf-8"))

    if args.dry_run:
        candidates = generate_candidates(params)
        print(f"후보 {len(candidates)}개 (dry-run):")
        for i, c in enumerate(candidates):
            print(f"  C{i:02d}: {c}")
    else:
        result = run_hypothesis_loop(
            params,
            target_err=args.target_err,
            max_candidates=args.max_cand
        )
        if result:
            sys.exit(0 if result["target_met"] else 1)
        else:
            sys.exit(2)
