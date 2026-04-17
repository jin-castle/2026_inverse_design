import sys, json
sys.stdout.reconfigure(encoding='utf-8')
d = json.loads(open('tests/regression_result_latest.json', encoding='utf-8').read())
print('Pass rate:', d['passed'], '/', d['total'], '=', round(d['pass_rate']*100,1), '%')
print()
print('Category results:')
for cat, res in d['category_results'].items():
    p = res['pass']; t = res['total']
    print(f'  {cat}: {p}/{t}')
print()
print('Test details:')
for r in d['results']:
    status = 'PASS' if r['passed'] else 'FAIL'
    score = r.get('score', 0)
    top = str(r.get('top_result','?'))[:50]
    print(f'  [{status}] {r["id"]} score={score:.2f} | {top}')
    if not r['passed']:
        miss = r.get('missing_keywords', [])
        fp   = r.get('false_positives', [])
        if miss: print(f'         Missing: {miss}')
        if fp:   print(f'         FalsePos: {fp}')
