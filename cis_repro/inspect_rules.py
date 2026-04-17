import json
from collections import Counter

with open('C:/Users/user/projects/meep-kb/cis_repro/error_rules.json', encoding='utf-8') as f:
    data = json.load(f)

rules = data['CIS_ERROR_RULES']
print(f"총 규칙 수: {len(rules)}")
print()

cats = Counter(r['category'] for r in rules)
print("카테고리별:")
for cat, cnt in sorted(cats.items()):
    print(f"  {cat}: {cnt}개")

print()
for r in rules:
    eid = r['error_id']
    cat = r['category']
    pri = r['priority']
    det = r['detect_type']
    sym = r['symptom'][:60]
    print(f"  [{r['id']}] {cat}/{eid}  (priority={pri}, detect={det})")
    print(f"    >> {sym}")
