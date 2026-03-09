import json, random
from pathlib import Path
from collections import Counter

lines = Path('finetune_data/train.jsonl').read_text(encoding='utf-8').strip().split('\n')
records = [json.loads(l) for l in lines if l.strip()]

# 문제 데이터 분류
issues = {
    'output_english_only': [],  # output이 영어만
    'output_too_short': [],     # output < 50자
    'output_no_solution': [],   # "## 해결" 없는 진단 데이터
    'input_legume': [],         # MEEP 아닌 legume 데이터
    'output_is_question': [],   # output이 답변이 아니라 질문
    'good': [],
}

for r in records:
    out = r['output'].strip()
    inp = r['input'].strip()
    
    # MEEP 아닌 라이브러리
    if 'legume' in inp.lower() and 'meep' not in inp.lower():
        issues['input_legume'].append(r)
        continue
    
    # output 너무 짧음
    if len(out) < 50:
        issues['output_too_short'].append(r)
        continue
    
    # output이 영어만 (한국어 없음) + 진단 데이터
    has_korean = any('\uac00' <= c <= '\ud7a3' for c in out)
    is_diagnose = '에러' in inp or 'error' in inp.lower() or 'traceback' in inp.lower()
    if is_diagnose and not has_korean:
        issues['output_english_only'].append(r)
        continue
    
    # 진단인데 실제 해결책이 없는 것 (GitHub issue 토론)
    if is_diagnose and '## 해결' not in out and len(out) < 200:
        issues['output_no_solution'].append(r)
        continue
    
    issues['good'].append(r)

print('=== 데이터 품질 분류 ===')
for k, v in issues.items():
    print(f'  {k}: {len(v)}개')

print()
print('=== 문제 샘플 ===')

print('\n[영어만 있는 output (진단 데이터)]')
for r in issues['output_english_only'][:2]:
    print(f'  input: {r["input"][:80]}')
    print(f'  output: {r["output"][:100]}')
    print()

print('[legume 등 비MEEP 데이터]')
for r in issues['input_legume'][:2]:
    print(f'  input: {r["input"][:100]}')
    print(f'  output: {r["output"][:60]}')
    print()

print(f'\n=== 결론 ===')
good = len(issues['good'])
total = len(records)
print(f'실제 품질 좋은 데이터: {good}/{total} ({good/total*100:.0f}%)')
print(f'제거해야 할 데이터: {total-good}개')
print(f'정제 후 예상 데이터: {good}개')
