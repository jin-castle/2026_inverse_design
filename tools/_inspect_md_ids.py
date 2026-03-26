#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""md_header 패턴 상세 조사 - 진짜 마크다운인지 Python 주석인지"""
import sqlite3
import re
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'knowledge.db')
conn = sqlite3.connect(DB_PATH, timeout=30)

rows = conn.execute('SELECT id, original_code, error_type FROM sim_errors_v2 WHERE fix_worked=0 AND original_code IS NOT NULL').fetchall()

def is_markdown_mixed(code):
    if not code: return False
    for line in code.split('\n'):
        s = line.strip()
        if s.startswith('```'): return True
        if re.match(r'^(In|Out)\s*\[\s*\d*\s*\]:', s): return True
        if re.match(r'^#{1,6}\s+\S', s): return True
    return False

def has_real_markdown_header(code):
    """진짜 마크다운 헤더 (## 두개 이상 # 인 것들) vs Python 단일 # 주석 구분"""
    if not code: return False
    for line in code.split('\n'):
        s = line.strip()
        # ## 이상: 확실히 마크다운
        if re.match(r'^#{2,6}\s+\S', s): return True
        # # 하나: Python 주석일 가능성 높음 - 내용 보고 판단
        # 마크다운 헤더는 보통 대문자로 시작하는 단어/제목
        # Python 주석은 보통 소문자나 설명
    return False

mixed = [(r[0], r[2], r[1]) for r in rows if is_markdown_mixed(r[1])]
real_md = [(id_, et, code) for id_, et, code in mixed if has_real_markdown_header(code)]
only_single_hash = [(id_, et, code) for id_, et, code in mixed if not has_real_markdown_header(code)]

print(f'마크다운 혼재 전체: {len(mixed)}건')
print(f'진짜 ## 헤더 포함: {len(real_md)}건')
print(f'단일 # 만 있음: {len(only_single_hash)}건')

print(f'\n--- 단일 # 만 있는 샘플 (첫 5개) ---')
for id_, et, code in only_single_hash[:5]:
    # 마크다운 헤더처럼 감지된 라인 찾기
    bad_lines = []
    for line in code.split('\n'):
        s = line.strip()
        if re.match(r'^#{1,6}\s+\S', s):
            bad_lines.append(s[:80])
    print(f'ID {id_} ({et}): 감지된 줄 = {bad_lines[:3]}')
    
print(f'\n--- 진짜 마크다운 ## 헤더 (첫 5개) ---')
for id_, et, code in real_md[:5]:
    print(f'\nID {id_} ({et}):')
    print(code[:400])
    print('...')

conn.close()
