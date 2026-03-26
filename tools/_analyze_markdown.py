#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""마크다운 혼재 코드 상세 분석"""
import sqlite3
import re
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'knowledge.db')
conn = sqlite3.connect(DB_PATH, timeout=30)

rows = conn.execute('SELECT id, original_code, error_type FROM sim_errors_v2 WHERE fix_worked=0 AND original_code IS NOT NULL').fetchall()

def classify_markdown(code):
    if not code: return None
    reasons = []
    for line in code.split('\n'):
        s = line.strip()
        if s.startswith('```'):
            reasons.append('backtick_block')
        if re.match(r'^(In|Out)\s*\[\s*\d*\s*\]:', s):
            reasons.append('jupyter_cell')
        if re.match(r'^#{1,6}\s+\S', s):
            reasons.append('md_header')
        if '# [MD]' in line:
            reasons.append('[MD]_tag')
    return list(set(reasons)) if reasons else None

mixed_details = []
for r in rows:
    reasons = classify_markdown(r[1])
    if reasons:
        mixed_details.append((r[0], r[2], reasons, r[1]))

print(f'fix_worked=0 전체: {len(rows)}건')
print(f'마크다운 혼재: {len(mixed_details)}건')

# 이유 분류
from collections import Counter
reason_counts = Counter()
for id_, et, reasons, code in mixed_details:
    for r in reasons:
        reason_counts[r] += 1
print(f'\n이유별 분포:')
for reason, count in reason_counts.most_common():
    print(f'  {reason}: {count}건')

# 샘플 출력 (각 타입 별로)
print('\n--- backtick_block 샘플 ---')
for id_, et, reasons, code in mixed_details:
    if 'backtick_block' in reasons:
        print(f'ID {id_} ({et}):')
        print(code[:500])
        print('...')
        break

print('\n--- md_header 샘플 ---')
for id_, et, reasons, code in mixed_details:
    if 'md_header' in reasons:
        print(f'ID {id_} ({et}):')
        print(code[:500])
        print('...')
        break

print('\n--- [MD]_tag 샘플 ---')
for id_, et, reasons, code in mixed_details:
    if '[MD]_tag' in reasons:
        print(f'ID {id_} ({et}):')
        print(code[:500])
        print('...')
        break

print('\n--- jupyter_cell 샘플 ---')
for id_, et, reasons, code in mixed_details:
    if 'jupyter_cell' in reasons:
        print(f'ID {id_} ({et}):')
        print(code[:500])
        print('...')
        break

conn.close()
