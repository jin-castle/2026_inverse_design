#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PHASE 1: sim_errors_v2 현황 파악"""
import sqlite3
import sys
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'knowledge.db')

conn = sqlite3.connect(DB_PATH, timeout=30)

# sim_errors_v2 현황
total = conn.execute("SELECT COUNT(*) FROM sim_errors_v2").fetchone()[0]
has_code = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE original_code IS NOT NULL AND LENGTH(original_code) > 50").fetchone()[0]
fix1 = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=1").fetchone()[0]
fix0 = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=0").fetchone()[0]
fix_null = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked IS NULL").fetchone()[0]

print(f"=== sim_errors_v2 현황 ===")
print(f"전체: {total}건")
print(f"코드있음(>50자): {has_code}건")
print(f"fix_worked=1: {fix1}건")
print(f"fix_worked=0: {fix0}건")
print(f"fix_worked=NULL: {fix_null}건")

# error_type 분포
print("\n=== error_type 분포 (상위 10) ===")
rows = conn.execute("""
    SELECT error_type, COUNT(*) as cnt 
    FROM sim_errors_v2 
    GROUP BY error_type 
    ORDER BY cnt DESC 
    LIMIT 10
""").fetchall()
for r in rows:
    print(f"  {r[0]}: {r[1]}건")

# source 분포
print("\n=== source 분포 ===")
rows = conn.execute("""
    SELECT source, COUNT(*) as cnt 
    FROM sim_errors_v2 
    GROUP BY source 
    ORDER BY cnt DESC
""").fetchall()
for r in rows:
    print(f"  {r[0] or 'NULL'}: {r[1]}건")

# physics_cause 채워진 것
phys = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE physics_cause IS NOT NULL AND LENGTH(physics_cause) > 10").fetchone()[0]
print(f"\n=== physics_cause 채워짐: {phys}건 ===")

# examples 테이블 현황
try:
    ex_total = conn.execute("SELECT COUNT(*) FROM examples").fetchone()[0]
    ex_has_code = conn.execute("SELECT COUNT(*) FROM examples WHERE code IS NOT NULL AND LENGTH(code) > 50").fetchone()[0]
    print(f"\n=== examples 테이블 ===")
    print(f"전체: {ex_total}건, 코드있음: {ex_has_code}건")
except Exception as e:
    print(f"\nexamples 테이블 없음: {e}")

# live_runs 테이블 현황
try:
    lr_total = conn.execute("SELECT COUNT(*) FROM live_runs").fetchone()[0]
    print(f"\n=== live_runs 테이블 ===")
    print(f"전체: {lr_total}건")
except Exception as e:
    print(f"\nlive_runs 테이블 없음: {e}")

conn.close()
print("\n=== 감사 완료 ===")
