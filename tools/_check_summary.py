import json
data = json.load(open('autosim/run_summary.json'))
errors = [x for x in data if x.get('status') in ('error', 'import_error', 'timeout')]
print(f'총 {len(data)}개 패턴, 오류 {len(errors)}개')
for e in errors[:10]:
    pat = e['pattern']
    st = e['status']
    err = str(e.get('error', ''))[:100]
    print(f'  - {pat}: {st} | {err}')
