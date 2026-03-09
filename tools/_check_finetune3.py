import json
from pathlib import Path

lines = Path('finetune_data/train.jsonl').read_text(encoding='utf-8').strip().split('\n')
records = [json.loads(l) for l in lines if l.strip()]

# output이 50자 미만인 것들 자세히 보기
short_outputs = [r for r in records if len(r['output'].strip()) < 50]
print(f'output < 50자: {len(short_outputs)}개')
print()
for r in short_outputs[:5]:
    print(f'  output({len(r["output"])}자): [{r["output"].strip()}]')
    print(f'  input: {r["input"][:80]}')
    print()

# 분포: 50~100자 사이
mid = [r for r in records if 50 <= len(r['output'].strip()) < 100]
print(f'output 50~100자: {len(mid)}개')
for r in mid[:3]:
    print(f'  output: [{r["output"].strip()}]')
