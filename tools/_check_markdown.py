#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PHASE 3-1: 마크다운 혼재 코드 파악"""
import sqlite3
import re
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'knowledge.db')
conn = sqlite3.connect(DB_PATH, timeout=30)

rows = conn.execute('SELECT id, original_code FROM sim_errors_v2 WHERE fix_worked=0 AND original_code IS NOT NULL').fetchall()

def is_markdown_mixed(code):
    if not code: return False
    for line in code.split('\n'):
        s = line.strip()
        if s.startswith('```'): return True
        if re.match(r'^(In|Out)\s*\[\s*\d*\s*\]:', s): return True
        if re.match(r'^#{1,6}\s+\S', s): return True
    return False

mixed = [(r[0], r[1]) for r in rows if is_markdown_mixed(r[1])]
print(f'fix_worked=0 전체: {len(rows)}건')
print(f'마크다운 혼재: {len(mixed)}건')

for id_, code in mixed[:3]:
    print(f'\n--- ID {id_} ---')
    print(code[:400])
    print('...')

conn.close()
