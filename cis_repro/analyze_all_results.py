"""전체 8개 논문 결과 + agent 수정 로그 종합 분석"""
import json, re
from pathlib import Path

BASE = Path(__file__).parent / "results"

# 기존 결과 (Single2022, Pixel2022_auto)
existing = {
    "Single2022": {
        "design": "discrete_pillar", "material": "TiO2", "n": 2.3,
        "res50": {"R": 0.709, "G": 0.457, "B": 0.729},
        "target": {"R": 0.70, "G": 0.60, "B": 0.65},
        "t_sec": 508,
        "agent_fixes": ["MasterOnly_Missing"],
    },
    "Pixel2022": {
        "design": "discrete_pillar", "material": "SiN", "n": 2.0,
        "res20": {"R": 0.625, "G": 0.532, "B": 0.564},
        "res50": {"R": 0.554, "G": 0.508, "B": 0.556},
        "target": {"R": 0.55, "G": 0.52, "B": 0.50},
        "t_sec": 2793,
        "agent_fixes": ["MasterOnly_Missing"],
    },
}

# 새 6개 논문 로그 파싱
new_papers = {
    "RGBIR2025":    {"design":"discrete_pillar","material":"TiO2","n":2.5,"target":{"R":0.50,"G":0.40,"B":0.50}},
    "SMA2023":      {"design":"sparse","material":"SiN","n":2.02,"target":{"R":0.45,"G":0.35,"B":0.40}},
    "Simplest2023": {"design":"cylinder","material":"Nb2O5","n":2.32,"target":{"R":0.60,"G":0.55,"B":0.55}},
    "Freeform2022": {"design":"materialgrid","material":"SiN","n":1.92,"target":{"R":0.45,"G":0.45,"B":0.45}},
    "Multilayer2022":{"design":"materialgrid","material":"SiN","n":2.02,"target":{"R":0.50,"G":0.50,"B":0.50}},
    "SingleLayer2022":{"design":"materialgrid","material":"SiN","n":2.1,"target":{"R":0.45,"G":0.40,"B":0.45}},
}

def parse_log(pid, res):
    log_path = BASE / pid / f"run_{pid}_res{res}.log"
    if not log_path.exists():
        return None, None
    txt = log_path.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'\[Result\] R=([\d.]+) G=([\d.]+) B=([\d.]+)', txt)
    e = re.findall(r'Elapsed run time = ([\d.]+)', txt)
    if m:
        return {"R":float(m.group(1)),"G":float(m.group(2)),"B":float(m.group(3))}, float(e[0]) if e else None
    return None, None

def get_agent_log(pid):
    lpath = BASE / pid / f"{pid}_agent_log.json"
    if lpath.exists():
        return json.loads(lpath.read_text(encoding='utf-8', errors='replace'))
    return []

results = {}
for pid, info in new_papers.items():
    eff20, t20   = parse_log(pid, 20)
    eff50, t50   = parse_log(pid, 50)
    eff100, t100 = parse_log(pid, 100)
    eff_final = eff100 or eff50 or eff20
    t_final   = t100 or t50 or t20
    alog = get_agent_log(pid)
    fixes = [e.get("rule_id","?") for e in alog if "fix" in e.get("step","")]
    results[pid] = {**info, "res20":eff20, "res_final":eff_final, "t_sec":t_final, "agent_fixes":fixes}

print("=" * 75)
print("CIS Color Router 8개 논문 재현 결과 — 완전 요약")
print("=" * 75)

print(f"\n{'논문':<18} {'설계':>14} {'재료':>8} {'res20_R':>8} {'final_R':>8} {'tgt_R':>7} {'오차':>7} {'agent 수정'}")
print("─" * 75)

all_rows = []

# 기존 결과
for pid, info in existing.items():
    r20 = info.get("res20",{}).get("R","—")
    rf  = info.get("res50",{}).get("R","—")
    tgt = info["target"]["R"]
    err = abs(rf-tgt)/tgt*100 if isinstance(rf,float) else None
    fixes = info.get("agent_fixes",[])
    row = {"pid":pid,"design":info["design"],"mat":info["material"],"n":info["n"],
           "res20":info.get("res20"),"final":info.get("res50"),
           "target":info["target"],"err":err,"fixes":fixes,"t":info.get("t_sec")}
    all_rows.append(row)
    r20_str = f"{r20:.3f}" if isinstance(r20,float) else "—"
    rf_str  = f"{rf:.3f}"  if isinstance(rf,float)  else "—"
    err_str = f"{err:.1f}%" if err is not None else "—"
    print(f"  {pid:<16} {info['design']:>14} {info['material']:>8} {r20_str:>8} {rf_str:>8} {tgt:>7.3f} {err_str:>7}  {fixes}")

# 새 결과
for pid, info in results.items():
    rf  = (info.get("res_final") or {}).get("R")
    r20 = (info.get("res20")    or {}).get("R")
    tgt = info["target"]["R"]
    err = abs(rf-tgt)/tgt*100 if isinstance(rf,float) else None
    row = {"pid":pid,"design":info["design"],"mat":info["material"],"n":info["n"],
           "res20":info.get("res20"),"final":info.get("res_final"),
           "target":info["target"],"err":err,"fixes":info.get("agent_fixes",[]),"t":info.get("t_sec")}
    all_rows.append(row)
    r20_str = f"{r20:.3f}" if isinstance(r20,float) else "—"
    rf_str  = f"{rf:.3f}"  if isinstance(rf,float)  else "—"
    err_str = f"{err:.1f}%" if err is not None else "—"
    print(f"  {pid:<16} {info['design']:>14} {info['material']:>8} {r20_str:>8} {rf_str:>8} {tgt:>7.3f} {err_str:>7}  {info['agent_fixes']}")

# 오차 계산 가능한 것들 평균
valid_errs = [r["err"] for r in all_rows if r["err"] is not None]
print(f"\n  전체 평균 오차: {sum(valid_errs)/len(valid_errs):.1f}% ({len(valid_errs)}/{len(all_rows)}개)")

# Agent 수정 통계
print("\n" + "="*75)
print("Agent 수정 사항 상세")
print("="*75)
for row in all_rows:
    pid   = row["pid"]
    fixes = row["fixes"]
    alog  = get_agent_log(pid)
    print(f"\n  [{pid}]")
    if not alog:
        print("    (agent 로그 없음 — 기존 재현)")
        continue
    for ev in alog:
        step = ev.get("step","")
        if "fix" in step or "precheck" in step or "check" in step:
            if step == "precheck_clean":
                print(f"    사전검사: 이슈 없음")
            elif "autofix" in step:
                rid = ev.get("rule_id","?")
                changed = ev.get("changed_lines",[])
                print(f"    자동수정: {rid}")
                for c in changed[:3]:
                    print(f"      line {c['line']}: {c['before'][:50]} → {c['after'][:50]}")
            elif "runtime" in step:
                rid = ev.get("rule_ids",["?"])
                err = ev.get("trigger_error","")[:60]
                changed = ev.get("changed_lines",[])
                print(f"    런타임 수정: {rid}  (트리거: {err})")
                for c in changed[:3]:
                    print(f"      line {c['line']}: {c['before'][:50]} → {c['after'][:50]}")
            elif "fast_check" in step:
                result = ev.get("result","?")
                print(f"    fast-check: {result}")
            elif "res" in step:
                eff = ev.get("eff")
                t   = ev.get("elapsed")
                if eff:
                    print(f"    {step}: R={eff['R']:.3f} G={eff['G']:.3f} B={eff['B']:.3f}  ({t:.0f}s)")
