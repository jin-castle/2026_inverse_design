"""
detect_pattern 우선순위 문제 분석 + error_rules.json 수정
문제: BUG-03~06에서 RefNorm_Missing이 먼저 매칭됨 (load_minus_flux_data 없어서)
원인: 베이스라인 코드에 참조 시뮬레이션이 없음 → 모든 코드에서 RefNorm_Missing 탐지
해결: (1) detect_type을 더 정교하게, (2) code_check 패턴 정밀화, (3) 순서 보정
"""
import json, re
from pathlib import Path

RULES_PATH = Path("C:/Users/user/projects/meep-kb/cis_repro/error_rules.json")

with open(RULES_PATH, encoding='utf-8') as f:
    data = json.load(f)

rules = data["CIS_ERROR_RULES"]

print("=== 탐지 패턴 분석 ===\n")

# 검증용 코드 스니펫들
test_codes = {
    "PML_AllDirections":    "pml_layers = [mp.PML(Lpml)]",
    "Matplotlib_Display":   "import matplotlib\n# agg removed",
    "Resolution_Too_Low":   "resolution = 2",
    "Pillar_Coord_Inversion": "px = round(-N/2*w + i*w + w/2, 2)\n py = round(N/2*w - j*w - w/2, 2)",
    "RefNorm_Missing":      "sim.run(until_after_sources=...)",  # 정상 코드 (참조 시뮬 없음)
}

for name, code_snippet in test_codes.items():
    print(f"[{name}]")
    matches = []
    for rule in sorted(rules, key=lambda r: r["priority"]):
        pat = rule["detect_pattern"]
        det = rule["detect_type"]
        if "code" in det:
            if det == "code_missing" and pat not in code_snippet:
                matches.append(rule)
            elif det == "code_missing_or_true" and (pat not in code_snippet or f"{pat}=True" in code_snippet):
                matches.append(rule)
            elif det == "regex" and re.search(pat, code_snippet):
                matches.append(rule)
            elif det == "code_check" and re.search(pat, code_snippet):
                matches.append(rule)
    print(f"  매칭: {[r['error_id'] for r in matches[:3]]}")
    print()

# ─── 수정 사항 적용 ───────────────────────────────────────────────────────────
print("\n=== error_rules.json 패턴 수정 ===\n")

fixes = {
    # PML_AllDirections: 더 정밀한 정규식 (mp.PML(숫자) or mp.PML(변수) without direction)
    "CIS-BC-003": {
        "detect_pattern": r"mp\.PML\(\w+\)(?!\s*,\s*direction)",
        "detect_type": "regex",
        "comment": "mp.PML(x) 뒤에 direction= 없는 경우만 탐지"
    },
    # Matplotlib_Display: stderr에서 탐지 (실행 시 나타남) + code 체크 추가
    "CIS-ENV-001": {
        "detect_pattern": r"_tkinter|cannot connect to X|No module named.*display",
        "detect_type": "stderr",
        "comment": "실행 stderr에서 탐지. 사전 체크는 별도 code_check 규칙으로."
    },
    # Resolution_Too_Low: 정확한 패턴 (resolution = 숫자 < 20)
    "CIS-NUM-001": {
        "detect_pattern": r"resolution\s*=\s*([1-9]|1[0-9])\b",
        "detect_type": "regex",
        "comment": "resolution 1~19일 때만 탐지 (fast-check용 5는 제외 로직 별도)"
    },
    # Pillar_Coord_Inversion: i/j 혼용 패턴
    "CIS-GEO-004": {
        "detect_pattern": r"px\s*=.*[^j]\*w.*\+.*w/2.*\n.*py\s*=.*[^i]\*w",
        "detect_type": "regex",
        "comment": "px에 i가 쓰이고 py에 j가 쓰이는 반전 패턴"
    },
    # RefNorm_Missing: code_missing에서 더 구체적인 키워드로
    "CIS-EFF-003": {
        "detect_pattern": "load_minus_flux_data",
        "detect_type": "code_missing",
        "comment": "효율 계산 코드가 있는데 load_minus_flux_data 없는 경우만. 검증 코드에 tran_flux_p 포함 여부도 확인.",
        "priority": 3  # 우선순위 낮춤
    },
}

for rule_id, patch in fixes.items():
    for rule in rules:
        if rule["id"] == rule_id:
            old_pat = rule["detect_pattern"]
            rule["detect_pattern"] = patch["detect_pattern"]
            rule["detect_type"] = patch["detect_type"]
            if "priority" in patch:
                rule["priority"] = patch["priority"]
            print(f"  [{rule_id}] {rule['error_id']}")
            print(f"    OLD: {old_pat}")
            print(f"    NEW: {patch['detect_pattern']}")
            print(f"    WHY: {patch['comment']}")
            print()

# Matplotlib Agg 누락 사전 체크 규칙 추가
new_rule = {
    "id": "CIS-ENV-003",
    "category": "ENVIRONMENT",
    "error_id": "Matplotlib_Agg_Missing",
    "detect_pattern": r'matplotlib\.use\("Agg"\)|matplotlib\.use\(\'Agg\'\)',
    "detect_type": "code_missing_regex",
    "symptom": "plt.show() 호출 시 Docker에서 X server 오류 발생 예방",
    "root_cause": "matplotlib.use('Agg')가 없으면 plt.show() 시 GUI backend 시도",
    "auto_fix": "matplotlib.use('Agg')를 import matplotlib 바로 다음에 추가",
    "fix_code": "import matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.pyplot as plt",
    "priority": 1,
    "verified": True
}

# 중복 방지
if not any(r["id"] == "CIS-ENV-003" for r in rules):
    rules.append(new_rule)
    print(f"  [추가] CIS-ENV-003 Matplotlib_Agg_Missing")

data["CIS_ERROR_RULES"] = rules

with open(RULES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\n  저장 완료: {RULES_PATH}")
print(f"  총 규칙 수: {len(rules)}")
