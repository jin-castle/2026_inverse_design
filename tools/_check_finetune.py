import json, random
from pathlib import Path

lines = Path('finetune_data/train.jsonl').read_text(encoding='utf-8').strip().split('\n')
records = [json.loads(l) for l in lines if l.strip()]
print(f'train 총 {len(records)}개')

# 길이 분포
lengths_in = [len(r['input']) for r in records]
lengths_out = [len(r['output']) for r in records]
total = [a+b for a,b in zip(lengths_in, lengths_out)]

print(f'input 평균: {sum(lengths_in)/len(lengths_in):.0f}자')
print(f'output 평균: {sum(lengths_out)/len(lengths_out):.0f}자')
print(f'너무 짧은 output(<50자): {sum(1 for l in lengths_out if l < 50)}개')
print(f'output 없음: {sum(1 for r in records if not r["output"].strip())}개')
print()

# output 품질 체크
has_meep = sum(1 for r in records if any(k in r['output'] for k in ['meep','mp.','simulation','Simulation']))
has_code = sum(1 for r in records if '```' in r['output'])
has_korean = sum(1 for r in records if any('\uac00' <= c <= '\ud7a3' for c in r['output']))
no_solution = sum(1 for r in records if len(r['output'].strip()) < 30)

print('output 품질:')
print(f'  MEEP 키워드 포함: {has_meep}/{len(records)} ({has_meep/len(records)*100:.0f}%)')
print(f'  코드 블록 포함: {has_code}/{len(records)} ({has_code/len(records)*100:.0f}%)')
print(f'  한국어 포함: {has_korean}/{len(records)} ({has_korean/len(records)*100:.0f}%)')
print(f'  너무 짧음(<30자): {no_solution}개')
print()

# 랜덤 샘플
random.seed(42)
samples = random.sample(records, 5)
for i, r in enumerate(samples):
    print(f'--- 샘플 {i+1} ---')
    inp = r['input'][:150].replace('\n', ' ')
    out = r['output'][:150].replace('\n', ' ')
    print(f'  input: {inp}')
    print(f'  output: {out}')
    print()
