import json
data = json.load(open('autosim/run_summary.json'))
from collections import Counter
statuses = Counter(x.get('status') for x in data)
print('상태별 집계:', dict(statuses))
print('총 패턴 수:', len(data))

# 패턴 디렉토리와 비교
import os
patterns_dir = 'autosim/patterns'
pattern_files = [f[:-3] for f in os.listdir(patterns_dir) if f.endswith('.py')]
print('패턴 파일 수:', len(pattern_files))

# run_summary에 없는 패턴들
in_summary = set(x['pattern'] for x in data)
not_run = set(pattern_files) - in_summary
print('아직 실행 안 된 패턴 수:', len(not_run))
for p in sorted(not_run)[:5]:
    print(' ', p)
